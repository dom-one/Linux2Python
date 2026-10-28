"""grep：在文件或目录中搜索匹配模式的行（GNU grep 风格子集）。

默认使用基本正则（BRE），与 GNU grep 一致；-E 切换为扩展正则（ERE）。
文件编码按文本可信度择优判定，GBK 文件在英文 Windows 上也能正确检索。
退出码遵循 GNU 约定：0 有命中、1 无命中、2 出错。
"""

from __future__ import annotations

import argparse
import codecs
import locale
import os
import re
from pathlib import Path
from typing import IO, Iterable, Iterator

from ..context import RunContext
from ..errors import UsageError
from ..registry import command

_SNIFF_SIZE = 8192
_FALLBACK_ENCODINGS = ("utf-8", "gb18030", "latin-1")
_SCORE_MARGIN = 0.3
_CJK_RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF))
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
    parser = argparse.ArgumentParser(
        prog="python main.py grep",
        description="搜索包含 PATTERN 的行",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python main.py grep -n TODO src\n"
            "  python main.py grep -ril error .\n"
            "  python main.py grep -E 'ERROR|FATAL' app.log\n"
            "  python main.py grep -c 'import' setup.py\n"
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
    return parser


@command("grep", "搜索包含 PATTERN 的行（GNU grep 风格子集）", build_parser)
def grep(args: argparse.Namespace, ctx: RunContext) -> int:
    regex = _compile_regex(args)

    stdin_mode = not args.paths
    if stdin_mode and ctx.stdin is None:
        raise UsageError("没有指定文件，也没有可读取的标准输入")
    if stdin_mode and ctx.stdin.isatty():
        ctx.stderr.write("未指定文件，从标准输入读取（Windows 下按 Ctrl+Z 后回车结束）。\n")
        ctx.stderr.write('要搜索当前目录：python main.py grep -r "PATTERN" .\n')

    show_prefix = args.recursive or len(args.paths) > 1
    matched_any = False
    had_error = False

    if stdin_mode:
        matched_any = _search_stdin(ctx, regex, args) > 0
    else:
        for raw in args.paths:
            path = Path(raw)
            if path.is_dir() and not args.recursive:
                raise UsageError(f"{path}: 是一个目录，请加 -r 递归搜索")
        for path in _iter_files(args.paths, args.recursive):
            try:
                selected = _search_file(path, regex, args, ctx, show_prefix)
            except OSError as exc:
                ctx.stderr.write(f"{path}: {exc.strerror or exc}\n")
                had_error = True
                continue
            matched_any = matched_any or selected > 0

    if had_error:
        return 2
    return 0 if matched_any else 1


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
    selected, _ = _run_search(lines, regex, args, ctx, None, False, not _summary_mode(args))
    if args.files_with_matches:
        if selected:
            ctx.stdout.write("(standard input)\n")
    elif args.count:
        ctx.stdout.write(f"{selected}\n")
    return selected


def _search_file(path: Path, regex: re.Pattern, args: argparse.Namespace, ctx: RunContext, show_prefix: bool) -> int:
    with path.open("rb") as handle:
        sample = handle.read(_SNIFF_SIZE)
        if b"\x00" in sample:
            return _search_binary(path, regex, args, ctx, show_prefix)
        encoding = _detect_encoding(sample)
        handle.seek(0)
        selected, _ = _run_search(
            _decode_lines(handle, encoding),
            regex,
            args,
            ctx,
            str(path),
            show_prefix,
            not _summary_mode(args),
        )

    if args.files_with_matches:
        if selected:
            ctx.stdout.write(f"{path}\n")
    elif args.count:
        ctx.stdout.write(f"{path}:{selected}\n" if show_prefix else f"{selected}\n")
    return selected


def _search_binary(path: Path, regex: re.Pattern, args: argparse.Namespace, ctx: RunContext, show_prefix: bool) -> int:
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
        ctx.stdout.write(f"{path}\n")
    elif args.count:
        ctx.stdout.write(f"{path}:{selected}\n" if show_prefix else f"{selected}\n")
    else:
        ctx.stdout.write(f"Binary file {path} matches\n")
    return selected


def _run_search(
    lines: Iterable[tuple[int, str]],
    regex: re.Pattern,
    args: argparse.Namespace,
    ctx: RunContext,
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
                ctx.stdout.write(f"{prefix}{piece}\n")
        else:
            ctx.stdout.write(f"{_line_prefix(label, lineno, args, show_prefix)}{text}\n")
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


def _detect_encoding(sample: bytes) -> str:
    """按文本可信度选编码，而不是取第一个能解的。

    系统首选编码在英文 Windows 上是 cp1252，它几乎不报错，能把 GBK 字节解成乱码，
    按顺序取第一个可解码的编码会让中文内容彻底搜不到。这里给每个候选解码打分，
    可信度明显更高时才替换当前选择。
    """
    best_encoding = "utf-8"
    best_score = -1.0
    for encoding in _candidate_encodings():
        text = _decode_sample(sample, encoding)
        if text is None:
            continue
        score = _text_score(text)
        if score > best_score + _SCORE_MARGIN:
            best_score = score
            best_encoding = encoding
    return best_encoding


def _candidate_encodings() -> list[str]:
    candidates: list[str] = []
    preferred = locale.getpreferredencoding(False)
    for encoding in ("utf-8", preferred, *_FALLBACK_ENCODINGS):
        if encoding and encoding not in candidates:
            candidates.append(encoding)
    return candidates


def _decode_sample(sample: bytes, encoding: str) -> str | None:
    try:
        decoder = codecs.getincrementaldecoder(encoding)(errors="strict")
        return decoder.decode(sample, final=False)
    except (UnicodeDecodeError, LookupError, ValueError):
        return None


def _text_score(text: str) -> float:
    if not text:
        return 0.0
    score = 0.0
    for char in text:
        code = ord(char)
        if 32 <= code < 127:
            score += 1.0
        elif any(low <= code <= high for low, high in _CJK_RANGES):
            score += 3.0
        elif 0x3000 <= code <= 0x303F or 0xFF00 <= code <= 0xFFEF:
            score += 1.0
        elif code in (9, 10, 13):
            score += 0.5
        elif code >= 0x80:
            score += 0.2
    return score / len(text)
