"""cat：把文件内容连接起来输出到标准输出（GNU cat 风格子集）。

对齐 GNU cat 的部分：

- 多个文件按顺序连接输出，中间不加分隔符
- -n 给所有行编号，-b 只给非空行编号；两者同开时以 -b 为准
- -E 在行尾显示 $，-T 把制表符显示成 ^I，-s 把连续空行压成一行
- -v 用 ^ 与 M- 记号显示非打印字符；-e 等价于 -vE，-t 等价于 -vT，
  -A 等价于 -vET
- 操作数 - 表示标准输入；不给操作数时读标准输入
- 行号跨文件连续累计，空行压紧状态也跨文件延续
- 编号格式为右对齐 6 位后跟制表符，与 GNU 一致
- -v 的记号按字节算：控制字符显示成 ^X，高位字节显示成 M- 加低七位
- 二进制文件（含 NUL 字节）逐字节原样转交，不做编码转换

与 GNU 的差异（README 有完整说明）：

- 文本文件按判定出的编码解码后统一输出 UTF-8，所以 GBK 中文在 Windows
  控制台上正常显示；GNU cat 是字节透传，直接把 GBK 字节写出去
- 文件打不开时按本项目约定返回退出码 2（GNU cat 返回 1），其余文件照常输出
- 输出的换行：管道与重定向时按原样转交 LF/CRLF，控制台里仍用 CRLF
"""

from __future__ import annotations

import argparse
import codecs
import locale
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Iterator

from ..context import RunContext
from ..entry import command_prog
from ..registry import command

_SNIFF_SIZE = 8192
_READ_SIZE = 65536
_SCORE_MARGIN = 0.3
_CJK_RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF))
_FALLBACK_ENCODINGS = ("utf-8", "gb18030", "latin-1")
_BINARY_ENCODING = "utf-8"
_NUMBER_WIDTH = 6


@dataclass(frozen=True)
class _Options:
    """一组生效的显示选项。"""

    number_all: bool
    number_nonblank: bool
    show_ends: bool
    show_tabs: bool
    squeeze_blank: bool
    show_nonprinting: bool


class _State:
    """跨文件延续的状态：行号计数器与空行压紧标记。"""

    def __init__(self) -> None:
        self.line_number = 0
        self.previous_blank = False


def build_parser() -> argparse.ArgumentParser:
    prog = command_prog("cat")
    parser = argparse.ArgumentParser(
        prog=prog,
        description="连接文件内容并输出到标准输出",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            f"  {prog} w2l/cli.py\n"
            f"  {prog} -n w2l/registry.py\n"
            f"  {prog} -A w2l/context.py\n"
            f"  {prog} README.md AGENTS.md\n"
        ),
    )
    parser.add_argument("files", nargs="*", help="要输出的文件，- 表示标准输入；不填则读标准输入")
    parser.add_argument("-n", "--number", action="store_true", help="给所有输出行编号")
    parser.add_argument("-b", "--number-nonblank", action="store_true", help="只给非空行编号（与 -n 同开时以 -b 为准）")
    parser.add_argument("-E", "--show-ends", action="store_true", help="在每行末尾显示 $")
    parser.add_argument("-e", action="store_true", help="同 -vE")
    parser.add_argument("-T", "--show-tabs", action="store_true", help="把制表符显示成 ^I")
    parser.add_argument("-t", action="store_true", help="同 -vT")
    parser.add_argument("-s", "--squeeze-blank", action="store_true", help="把连续空行压成一行")
    parser.add_argument("-v", "--show-nonprinting", action="store_true", help="用 ^ 与 M- 记号显示非打印字符")
    parser.add_argument("-A", "--show-all", action="store_true", help="等价于 -vET")
    parser.add_argument("-u", "--unbuffered", action="store_true", help="立即输出，不缓冲（此实现无实际影响）")
    return parser


@command("cat", "连接文件内容并输出到标准输出（GNU cat 风格子集）", build_parser)
def cat(args: argparse.Namespace, ctx: RunContext) -> int:
    options = _build_options(args)
    state = _State()
    files = list(args.files) if args.files else ["-"]

    _prepare_stdout(ctx)

    had_error = False
    for name in files:
        if name == "-":
            _emit_stream(_stdin_chunks(ctx), "utf-8", options, state, ctx)
            continue
        path = _resolve(ctx.cwd, name)
        if path.is_dir():
            ctx.stderr.write(f"cat: 无法打开 '{name}': 是一个目录\n")
            had_error = True
            continue
        try:
            with path.open("rb") as handle:
                sample = handle.read(_SNIFF_SIZE)
                encoding = _pick_encoding(sample)
                handle.seek(0)
                _emit_stream(_chunks(handle), encoding, options, state, ctx)
        except OSError as exc:
            ctx.stderr.write(f"cat: 无法打开 '{name}': {exc.strerror or exc}\n")
            had_error = True
            continue

    if had_error:
        return 2
    return 0


def _build_options(args: argparse.Namespace) -> _Options:
    # GNU 的 -e 等价于 -vE，-t 等价于 -vT，-A 等价于 -vET；
    # -b 与 -n 同开时以 -b 为准。
    show_nonprinting = args.show_nonprinting or args.show_all or args.e or args.t
    return _Options(
        number_all=args.number and not args.number_nonblank,
        number_nonblank=args.number_nonblank,
        show_ends=args.show_ends or args.show_all or args.e,
        show_tabs=args.show_tabs or args.show_all or args.t,
        squeeze_blank=args.squeeze_blank,
        show_nonprinting=show_nonprinting,
    )


def _prepare_stdout(ctx: RunContext) -> None:
    """调整输出流，让字节原样转交。

    两处调整：

    - 管道与重定向时关掉换行翻译。Windows 上 Python 默认把 "\\n" 写成
      "\\r\\n"，那会把 LF 文件和 CRLF 文件的区别抹掉；cat 的职责是原样
      转交内容，所以重定向时不翻译。控制台保持默认的 CRLF，避免老控制台
      只认 CRLF 换行。
    - 错误处理改成 surrogateescape。这样解不出的字节会用代理码位占位，
      写回时还能还原成原字节，二进制文件因此不会被改写。
    """
    reconfigure = getattr(ctx.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(errors="surrogateescape")
        if not _isatty(ctx.stdout):
            reconfigure(newline="")
    except (ValueError, OSError):
        pass


def _isatty(stream: object) -> bool:
    isatty = getattr(stream, "isatty", None)
    if isatty is None:
        return False
    try:
        return bool(isatty())
    except (ValueError, OSError):
        return False


def _resolve(cwd: Path, operand: str) -> Path:
    target = Path(operand)
    if not target.is_absolute():
        target = cwd / target
    return target


def _stdin_chunks(ctx: RunContext) -> Iterator[bytes]:
    """从标准输入取原始字节。

    文本模式的 stdin 会把 CRLF 归一成 LF、丢掉 lone CR，那不是 cat 该做的事，
    所以优先走底层二进制流；拿不到二进制流时退回文本再编码回 UTF-8。
    """
    stream = ctx.stdin
    if stream is None:
        return
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        yield from _chunks(buffer)
        return
    text = stream.read()
    if text:
        yield text.encode("utf-8", errors="surrogateescape")


def _chunks(handle: IO[bytes]) -> Iterator[bytes]:
    while True:
        chunk = handle.read(_READ_SIZE)
        if not chunk:
            return
        yield chunk


def _emit_stream(
    chunks: Iterator[bytes],
    encoding: str,
    options: _Options,
    state: _State,
    ctx: RunContext,
) -> None:
    """按行输出内容，同时处理编号、空行压紧与显示记号。"""
    for raw, terminated in _split_lines(chunks):
        if options.squeeze_blank and raw == b"":
            if state.previous_blank:
                continue
            state.previous_blank = True
        else:
            state.previous_blank = False

        prefix = _number_prefix(raw, options, state)
        body = _show_content(raw, options)
        if options.show_ends and terminated:
            body += b"$"
        ctx.stdout.write((prefix + body).decode(encoding, errors="surrogateescape"))
        if terminated:
            ctx.stdout.write("\n")


def _split_lines(chunks: Iterator[bytes]) -> Iterator[tuple[bytes, bool]]:
    """按 "\\n" 切行，产出 (原始字节, 是否以换行结尾)。

    只认 "\\n" 作行分隔符，"\\r" 留在行内容里：这样 CRLF 文件的空行内容是
    "\\r" 而不是空行，与 GNU cat 的判定一致（GNU 也只按 LF 切行）。
    """
    buffer = bytearray()
    for chunk in chunks:
        buffer += chunk
        start = 0
        while True:
            index = buffer.find(b"\n", start)
            if index < 0:
                break
            yield bytes(buffer[start:index]), True
            start = index + 1
        if start:
            del buffer[:start]
    if buffer:
        yield bytes(buffer), False


def _number_prefix(raw: bytes, options: _Options, state: _State) -> bytes:
    """算出该行的编号前缀。

    -n 给每一行编号；-b 只给非空行编号，且计数器只在真正编号时才前进。
    """
    if options.number_nonblank:
        if raw == b"":
            return b""
        state.line_number += 1
    elif options.number_all:
        state.line_number += 1
    else:
        return b""
    return f"{state.line_number:>{_NUMBER_WIDTH}d}\t".encode("ascii")


def _show_content(raw: bytes, options: _Options) -> bytes:
    if options.show_nonprinting:
        raw = _show_nonprinting(raw)
    if options.show_tabs:
        raw = raw.replace(b"\t", b"^I")
    return raw


def _show_nonprinting(raw: bytes) -> bytes:
    """把非打印字符显示成 ^ 记号，高位字节显示成 M- 记号。

    记号按字节算，与 GNU cat 一致：0x00-0x1f 与 0x7f 显示成 "^X"，
    0x80-0xff 显示成 "M-" 加低七位的记号。制表符与换行不转义（-T 单独处理）。
    """
    out = bytearray()
    for byte in raw:
        if byte == 0x09 or byte == 0x0A:
            out.append(byte)
        elif byte < 0x20 or byte == 0x7F:
            out += b"^" + bytes((byte ^ 0x40,))
        elif byte >= 0x80:
            out += b"M-" + _control_notation(byte & 0x7F)
        else:
            out.append(byte)
    return bytes(out)


def _control_notation(byte: int) -> bytes:
    """把低七位字节写成控制字符记号。"""
    if byte < 0x20 or byte == 0x7F:
        return b"^" + bytes((byte ^ 0x40,))
    return bytes((byte,))


def _pick_encoding(sample: bytes) -> str:
    """按内容选解码方式。

    分三类：

    - 文本：先判定编码再解码，中文按 UTF-8 输出，Windows 控制台上正常显示。
      判据是样本能被 utf-8 / 系统首选编码 / gb18030 之一严格解码。
    - 二进制（含 NUL 字节，或谁也解不出来）：按 utf-8 + surrogateescape
      解码，解不出的字节用代理码位占位，写回时还原成原字节，逐字节原样转交。

    latin-1 永远能解任何字节，所以判定文本时不把它算进去，否则所有二进制
    都会被误判成文本。
    """
    if b"\x00" in sample:
        return _BINARY_ENCODING
    if _is_text(sample):
        return _detect_encoding(sample)
    return _BINARY_ENCODING


def _is_text(sample: bytes) -> bool:
    """样本能否被某个真正的文本编码严格解码。"""
    for encoding in _candidate_encodings():
        if encoding == "latin-1":
            continue
        if _decode_sample(sample, encoding) is not None:
            return True
    return False


def _detect_encoding(sample: bytes) -> str:
    """按文本可信度判定编码。

    判定思路与 grep.py 保持一致：系统首选编码在英文 Windows 上是 cp1252，
    它几乎不报错，能把 GBK 字节解成乱码，所以不能按顺序取第一个能解的编码。
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
    """给一段解码结果打「像不像正文」的分。

    ASCII 可打印字符记 1 分，CJK 记 3 分，全角标点记 1 分，
    高位乱码字节只记 0.2 分——这样 GBK 正文能压过 cp1252 的乱码结果。
    """
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
