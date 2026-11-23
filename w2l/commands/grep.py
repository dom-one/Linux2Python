"""grep：在文件或目录中搜索匹配模式的行（GNU grep 风格子集）。

默认使用基本正则（BRE），与 GNU grep 一致；-E 切换为扩展正则（ERE）。
文件编码按文本可信度择优判定，GBK 文件在英文 Windows 上也能正确检索。
退出码遵循 GNU 约定：0 有命中、1 无命中、2 出错。

-j/--jobs 是本项目的扩展选项（GNU grep 没有，ugrep 的 --jobs 是同一思路）：
把文件列表切成连续片段分给多个工作进程，只改速度不改结果，
输出与串行逐字节一致。细节见 README 的「分片并行搜索」。
"""

from __future__ import annotations

import argparse
import io
import os
import re
from pathlib import Path
from typing import IO, Iterable, Iterator

from ..context import RunContext
from ..encoding import (
    SNIFF_SIZE as _SNIFF_SIZE,
    candidate_encodings as _candidate_encodings,
    decode_sample as _decode_sample,
    detect_encoding as _detect_encoding,
    text_score as _text_score,
)
from ..entry import command_prog
from ..errors import UsageError
from ..parallel import map_ordered, resolve_jobs, split_evenly
from ..registry import command

# 文件数少于这个数时 --jobs 仍走串行：起进程的开销大于并行收益。
_PARALLEL_MIN_FILES = 32
# 切片数按进程数的这个倍数来定：比进程数多，工作进程才能动态领活
# （快的进程多干几片），而 imap 仍然按输入顺序返回结果，输出顺序不受影响。
_CHUNKS_PER_JOB = 4
_BRE_ESCAPED = {
    "(": "(?:",
    ")": ")",
    "{": "{",
    "}": "}",
    "|": "|",
    "+": "+",
    "?": "?",
    "*": r"\*",
}
_BRE_LITERALS = "+?|(){}"


def build_parser() -> argparse.ArgumentParser:
    prog = command_prog("grep")
    parser = argparse.ArgumentParser(
        prog=prog,
        description="搜索包含 PATTERN 的行",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            f"  {prog} -n TODO src\n"
            f"  {prog} -ril error .\n"
            f"  {prog} -E 'ERROR|FATAL' app.log\n"
            f"  {prog} -c 'import' setup.py\n"
        ),
    )
    parser.add_argument("pattern", help="要搜索的正则表达式")
    parser.add_argument("paths", nargs="*", help="要搜索的文件或目录，目录需配合 -r")
    parser.add_argument("-i", "--ignore-case", action="store_true", help="忽略大小写")
    parser.add_argument("-v", "--invert-match", action="store_true", help="反向匹配，输出不匹配的行")
    parser.add_argument("-n", "--line-number", action="store_true", help="在输出前显示行号")
    parser.add_argument("-r", "--recursive", action="store_true", help="递归搜索目录")
    parser.add_argument("-E", "--extended-regexp", action="store_true", help="使用扩展正则 ERE，默认使用基本正则 BRE")
    parser.add_argument("-w", "--word-regexp", action="store_true", help="只匹配构成完整单词的片段")
    parser.add_argument("-c", "--count", action="store_true", help="只输出每个文件的匹配行数")
    parser.add_argument("-l", "--files-with-matches", action="store_true", help="只输出含有匹配的文件名")
    parser.add_argument("-o", "--only-matching", action="store_true", help="只输出匹配到的部分")
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=1,
        metavar="N",
        help="并行搜索的工作进程数；0 表示按 CPU 核数自动决定（默认 1，即串行）",
    )
    return parser


@command("grep", "搜索包含 PATTERN 的行（GNU grep 风格子集）", build_parser)
def grep(args: argparse.Namespace, ctx: RunContext) -> int:
    regex = _compile_regex(args)

    paths = list(args.paths)
    recursive = args.recursive
    stdin_mode = not paths

    if stdin_mode:
        if ctx.stdin is None:
            raise UsageError("没有指定文件，也没有可读取的标准输入")
        if ctx.stdin.isatty():
            paths = ["."]
            recursive = True
            stdin_mode = False
            ctx.stderr.write("未指定路径：递归搜索当前目录（.）。要读标准输入请用管道。\n")

    show_prefix = recursive or len(paths) > 1
    matched_any = False
    had_error = False

    if stdin_mode:
        matched_any = _search_stdin(ctx, regex, args) > 0
    else:
        for raw in paths:
            path = Path(raw)
            if path.is_dir() and not recursive:
                raise UsageError(f"{path}: 是一个目录，请加 -r 递归搜索")

        jobs = _resolve_jobs(args.jobs)
        if jobs > 1:
            matched_any, had_error = _search_parallel(
                paths, recursive, regex, args, ctx, show_prefix, jobs
            )
        else:
            matched_any, had_error = _search_serial(
                paths, recursive, regex, args, ctx, show_prefix
            )

    if had_error:
        return 2
    return 0 if matched_any else 1


def _resolve_jobs(value: int) -> int:
    """把 --jobs 的取值解析成实际进程数，非法值按用法错误处理。"""
    if value < 0:
        raise UsageError(f"--jobs 的进程数不能为负数: {value}")
    return resolve_jobs(value)


def _search_serial(
    paths: list[str],
    recursive: bool,
    regex: re.Pattern,
    args: argparse.Namespace,
    ctx: RunContext,
    show_prefix: bool,
) -> tuple[bool, bool]:
    """串行搜索：边遍历边搜边输出，不在内存里攒结果。"""
    matched_any = False
    had_error = False
    for path in _iter_files(paths, recursive):
        try:
            selected = _search_file(path, regex, args, ctx.stdout, show_prefix)
        except OSError as exc:
            ctx.stderr.write(f"{path}: {exc.strerror or exc}\n")
            had_error = True
            continue
        matched_any = matched_any or selected > 0
    return matched_any, had_error


def _search_parallel(
    paths: list[str],
    recursive: bool,
    regex: re.Pattern,
    args: argparse.Namespace,
    ctx: RunContext,
    show_prefix: bool,
    jobs: int,
) -> tuple[bool, bool]:
    """并行搜索：把文件列表切成若干连续片段分给工作进程，按片段顺序输出。

    片段是连续的，所以输出顺序与串行逐字节一致；每个片段内部仍按
    目录遍历顺序处理，因此并行与串行的结果完全相同。
    """
    files = [str(path) for path in _iter_files(paths, recursive)]
    if len(files) < _PARALLEL_MIN_FILES:
        # 文件太少时起进程的开销大于并行收益，直接串行。
        return _search_serial(paths, recursive, regex, args, ctx, show_prefix)

    chunks = split_evenly(files, jobs * _CHUNKS_PER_JOB)
    payloads = [(chunk, regex.pattern, regex.flags, args, show_prefix) for chunk in chunks]
    results = map_ordered(_search_chunk, payloads, jobs)

    matched_any = False
    had_error = False
    for text, selected, errors in results:
        if text:
            ctx.stdout.write(text)
        for message in errors:
            ctx.stderr.write(message)
        matched_any = matched_any or selected > 0
        had_error = had_error or bool(errors)
    return matched_any, had_error


def _search_chunk(
    payload: tuple[list[str], str, int, argparse.Namespace, bool],
) -> tuple[str, int, list[str]]:
    """工作进程里搜索一个片段，返回 (输出文本, 命中数, 错误信息列表)。

    必须放在模块顶层：spawn 的子进程要能 pickle 它。
    """
    chunk, pattern_source, pattern_flags, args, show_prefix = payload
    regex = re.compile(pattern_source, pattern_flags)
    stream = io.StringIO()
    selected_total = 0
    errors: list[str] = []
    for raw in chunk:
        path = Path(raw)
        try:
            selected = _search_file(path, regex, args, stream, show_prefix)
        except OSError as exc:
            errors.append(f"{path}: {exc.strerror or exc}\n")
            continue
        selected_total += selected
    return stream.getvalue(), selected_total, errors


def _compile_regex(args: argparse.Namespace) -> re.Pattern:
    flags = re.IGNORECASE if args.ignore_case else 0
    try:
        source = args.pattern if args.extended_regexp else _translate_bre(args.pattern)
        if args.word_regexp:
            source = rf"(?<!\w)(?:{source})(?!\w)"
        return re.compile(source, flags)
    except re.error as exc:
        raise UsageError(f"无效的正则表达式 '{args.pattern}': {exc}") from exc


def _translate_bre(pattern: str) -> str:
    """把 GNU 基本正则翻译成 Python 正则：\\( \\) \\{ \\} \\| \\+ \\? 还原为元字符，其余 + ? | ( ) { } 视为字面量。"""
    out: list[str] = []
    index = 0
    length = len(pattern)
    while index < length:
        char = pattern[index]
        if char == "\\":
            if index + 1 >= length:
                raise re.error("模式以孤立的反斜杠结尾")
            nxt = pattern[index + 1]
            if nxt in _BRE_ESCAPED:
                out.append(_BRE_ESCAPED[nxt])
            elif nxt == "b":
                out.append(r"\b")
            else:
                out.append("\\" + nxt)
            index += 2
            continue
        if char in _BRE_LITERALS:
            out.append("\\" + char)
            index += 1
            continue
        if char == "*" and index == 0:
            out.append(r"\*")
            index += 1
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _iter_files(paths: list[str], recursive: bool) -> Iterator[Path]:
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            yield from _walk(path)
        else:
            yield path


def _walk(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            yield Path(dirpath) / name


def _search_stdin(ctx: RunContext, regex: re.Pattern, args: argparse.Namespace) -> int:
    lines = ((index, line.rstrip("\n").rstrip("\r")) for index, line in enumerate(ctx.stdin, 1))
    selected, _ = _run_search(lines, regex, args, ctx.stdout, None, False, not _summary_mode(args))
    if args.files_with_matches:
        if selected:
            ctx.stdout.write("(standard input)\n")
    elif args.count:
        ctx.stdout.write(f"{selected}\n")
    return selected


def _search_file(
    path: Path,
    regex: re.Pattern,
    args: argparse.Namespace,
    stream: IO[str],
    show_prefix: bool,
) -> int:
    with path.open("rb") as handle:
        sample = handle.read(_SNIFF_SIZE)
        if b"\x00" in sample:
            return _search_binary(path, regex, args, stream, show_prefix)
        encoding = _detect_encoding(sample)
        handle.seek(0)
        selected, _ = _run_search(
            _decode_lines(handle, encoding),
            regex,
            args,
            stream,
            str(path),
            show_prefix,
            not _summary_mode(args),
        )

    if args.files_with_matches:
        if selected:
            stream.write(f"{path}\n")
    elif args.count:
        stream.write(f"{path}:{selected}\n" if show_prefix else f"{selected}\n")
    return selected


def _search_binary(
    path: Path,
    regex: re.Pattern,
    args: argparse.Namespace,
    stream: IO[str],
    show_prefix: bool,
) -> int:
    selected = 0
    with path.open("rb") as handle:
        for _, raw in enumerate(handle, 1):
            text = raw.decode("latin-1", errors="replace")
            matched = regex.search(text) is not None
            if args.invert_match:
                matched = not matched
            if matched:
                selected += 1

    if selected == 0:
        return 0
    if args.files_with_matches:
        stream.write(f"{path}\n")
    elif args.count:
        stream.write(f"{path}:{selected}\n" if show_prefix else f"{selected}\n")
    else:
        stream.write(f"Binary file {path} matches\n")
    return selected


def _run_search(
    lines: Iterable[tuple[int, str]],
    regex: re.Pattern,
    args: argparse.Namespace,
    stream: IO[str],
    label: str | None,
    show_prefix: bool,
    emit_lines: bool,
) -> tuple[int, int]:
    selected = 0
    total = 0
    for lineno, text in lines:
        total += 1
        matched = regex.search(text) is not None
        if args.invert_match:
            matched = not matched
        if not matched:
            continue
        selected += 1
        if not emit_lines:
            continue
        if args.only_matching:
            for piece in _matched_pieces(text, regex, args.invert_match):
                prefix = f"{lineno}:" if args.line_number else ""
                stream.write(f"{prefix}{piece}\n")
        else:
            stream.write(f"{_line_prefix(label, lineno, args, show_prefix)}{text}\n")
    return selected, total


def _line_prefix(label: str | None, lineno: int, args: argparse.Namespace, show_prefix: bool) -> str:
    prefix = ""
    if show_prefix and label:
        prefix = f"{label}:"
    if args.line_number:
        prefix += f"{lineno}:"
    return prefix


def _matched_pieces(text: str, regex: re.Pattern, invert: bool) -> list[str]:
    if not invert:
        return [match.group(0) for match in regex.finditer(text)]
    pieces: list[str] = []
    cursor = 0
    for match in regex.finditer(text):
        if match.start() > cursor:
            pieces.append(text[cursor : match.start()])
        cursor = match.end()
    if cursor < len(text):
        pieces.append(text[cursor:])
    return pieces


def _summary_mode(args: argparse.Namespace) -> bool:
    return args.count or args.files_with_matches


def _decode_lines(handle: IO[bytes], encoding: str) -> Iterator[tuple[int, str]]:
    for lineno, raw in enumerate(handle, 1):
        text = raw.decode(encoding, errors="replace")
        if text.endswith("\n"):
            text = text[:-1]
        if text.endswith("\r"):
            text = text[:-1]
        yield lineno, text
