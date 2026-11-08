"""wc：统计行数、词数、字符数、字节数（GNU wc 风格子集）。

对齐 GNU wc 的部分（行为实测自 coreutils 8.32）：

- 默认打印「行 词 字节」三列；-l/-w/-m/-c/-L 各自打开对应的一列
- 列的顺序固定为 行 → 词 → 字符 → 字节 → 最长行，与选项书写的顺序无关
- 行只按 \\n 计，文件末尾没有换行的那一行不算一行
- 词按空白分隔，空白包含空格、制表符、换行、回车、竖制表、换页；片段里
  夹着控制字符不算断开，整个片段没有可打印字符时不算词
- -m 按字符计（文本按判定出的编码解码后数），-c 按字节计
- -L 给最长行的显示宽度：全角字符算 2 列，制表符展开到 8 的倍数，
  \\r 把列号清零，组合字符算 0 列；一行里 \\r 之后的宽度再大也不算数，
  取的是这一行出现过的最大列数
- 多个操作数时最后打一行 total：行/词/字符/字节求和，最长行取最大值
- 操作数 - 表示标准输入；不给操作数时也读标准输入，但那一行不写文件名
- 打不开的文件不输出计数行，只报错并继续处理后面的文件；目录则输出一行
  全 0 并报错
- 重复的 - 只读一次标准输入，第二次起读到的是空的，total 也只算一次
- 列宽逐列算：每列按自己出现过的最大计数定下限，只有一列且不打 total 行时
  不做对齐；否则每列再按「普通文件字节数之和」撑开，标准输入与目录的大小
  事先数不出来，GNU 为它们预留 7 列。计数比预留宽度长时直接写长，不截断

与 GNU 的差异（README 有完整说明）：

- 文本按判定出的编码解码后统计字符数，所以 GBK 里的汉字按 1 个字算；
  GNU 在 C 区域设置下遇到解不出的字节序列，会把字符数整个记成 0
- 中文算可打印字符，所以中文文件里的中文算词；GNU 在 C 区域设置下只把
  可打印的 ASCII 当可打印字符，中文文件在 GNU 那边词数是 0
- 解不出的字节既不算字符也不算词，显示宽度算 0，与 GNU 一致
- 文件打不开时按本项目约定返回退出码 2（GNU wc 返回 1），其余文件照常统计
"""

from __future__ import annotations

import argparse
import codecs
import locale
import unicodedata
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

# GNU 对「事先数不出大小」的来源（标准输入、目录）预留的列宽。
_UNKNOWN_SIZE_WIDTH = 7
# 制表位宽度：制表符展开到下一个 8 的倍数。
_TAB_STOP = 8
# GNU 的空白字符集合：空格、制表符、换行、回车、竖制表、换页。
_WHITESPACE = " \t\n\r\v\f"

# 列的固定顺序：行 → 词 → 字符 → 字节 → 最长行。
_COLUMN_ORDER = ("lines", "words", "chars", "bytes", "max_line_length")


@dataclass(frozen=True)
class _Options:
    """一组生效的列选项。"""

    lines: bool
    words: bool
    chars: bool
    bytes: bool
    max_line_length: bool

    @property
    def column_count(self) -> int:
        """打开的列数。"""
        return sum(1 for column in _COLUMN_ORDER if getattr(self, column))

    def enabled(self, column: str) -> bool:
        """某一列是否要打印。"""
        return bool(getattr(self, column))

    @property
    def needs_text(self) -> bool:
        """是否要解码内容（词数、字符数、最长行都要）。"""
        return self.words or self.chars or self.max_line_length


@dataclass
class _Counts:
    """一个来源的统计结果。"""

    lines: int = 0
    words: int = 0
    chars: int = 0
    bytes: int = 0
    max_line_length: int = 0

    def value(self, column: str) -> int:
        """取某一列的数值。"""
        return getattr(self, column)


def build_parser() -> argparse.ArgumentParser:
    prog = command_prog("wc")
    parser = argparse.ArgumentParser(
        prog=prog,
        description="统计行数、词数、字符数、字节数",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            f"  {prog} w2l/cli.py\n"
            f"  {prog} -l w2l/registry.py\n"
            f"  {prog} -lwc README.md AGENTS.md\n"
            f"  {prog} -L README.md\n"
        ),
    )
    parser.add_argument("files", nargs="*", help="要统计的文件，- 表示标准输入；不填则读标准输入")
    parser.add_argument("-l", "--lines", action="store_true", help="打印行数")
    parser.add_argument("-w", "--words", action="store_true", help="打印词数")
    parser.add_argument("-m", "--chars", action="store_true", help="打印字符数")
    parser.add_argument("-c", "--bytes", action="store_true", help="打印字节数")
    parser.add_argument("-L", "--max-line-length", action="store_true", help="打印最长行的显示宽度")
    return parser


@command("wc", "统计行数、词数、字符数、字节数（GNU wc 风格子集）", build_parser)
def wc(args: argparse.Namespace, ctx: RunContext) -> int:
    options = _build_options(args)
    operands = list(args.files)
    # 没给操作数时读标准输入，但那一行不带文件名，与 GNU 一致。
    named = bool(operands)
    if not operands:
        operands = ["-"]

    rows: list[tuple[str | None, _Counts]] = []
    total = _Counts()
    regular_bytes = 0
    unknown_size = False
    stdin_used = False
    had_error = False

    for name in operands:
        if name == "-":
            unknown_size = True
            if stdin_used:
                # GNU 对第二个 - 读到的是空的：标准输入只读一次。
                rows.append(("-" if named else None, _Counts()))
                continue
            stdin_used = True
            source = _Source(_stdin_chunks(ctx))
            counts = _count_stream(source, options)
            rows.append(("-" if named else None, counts))
            total = _add(total, counts)
            continue

        path = _resolve(ctx.cwd, name)
        if path.is_dir():
            # GNU 对目录会打一行全 0，再报「是一个目录」。
            ctx.stderr.write(f"wc: 无法打开 '{name}': 是一个目录\n")
            had_error = True
            unknown_size = True
            rows.append((name, _Counts()))
            continue

        try:
            with path.open("rb") as handle:
                source = _Source(_chunks(handle))
                counts = _count_stream(source, options)
        except OSError as exc:
            # 打不开的文件不输出计数行，只报错并继续。
            ctx.stderr.write(f"wc: 无法打开 '{name}': {exc.strerror or exc}\n")
            had_error = True
            continue

        rows.append((name, counts))
        total = _add(total, counts)
        regular_bytes += counts.bytes

    total_printed = len(operands) > 1
    widths = _column_widths(rows, options, regular_bytes, unknown_size, total_printed)
    for row_name, counts in rows:
        _write_row(ctx, counts, options, widths, row_name)
    if total_printed:
        _write_row(ctx, total, options, widths, "total")

    if had_error:
        return 2
    return 0


def _build_options(args: argparse.Namespace) -> _Options:
    # 不给任何选项时打印 行/词/字节 三列，与 GNU 一致。
    options = _Options(
        lines=args.lines,
        words=args.words,
        chars=args.chars,
        bytes=args.bytes,
        max_line_length=args.max_line_length,
    )
    if options.column_count == 0:
        options = _Options(lines=True, words=True, chars=False, bytes=True, max_line_length=False)
    return options


def _add(left: _Counts, right: _Counts) -> _Counts:
    """把一个来源的计数累加到合计里（最长行取最大值）。"""
    return _Counts(
        lines=left.lines + right.lines,
        words=left.words + right.words,
        chars=left.chars + right.chars,
        bytes=left.bytes + right.bytes,
        max_line_length=max(left.max_line_length, right.max_line_length),
    )


def _column_widths(
    rows: list[tuple[str | None, _Counts]],
    options: _Options,
    regular_bytes: int,
    unknown_size: bool,
    total_printed: bool,
) -> dict[str, int]:
    """算出每一列的宽度。

    规则分两层：

    - 每列先按自己出现过的最大计数定下限（最大的那个数的位数）
    - 只打印一列、且不打 total 行时不做对齐；否则每列再按「普通文件字节数
      之和」撑开，标准输入与目录的大小事先数不出来，GNU 为它们预留 7 列

    total 行用同一套宽度写，计数比预留宽度长时直接写长，不截断——这也是
    GNU 的行为，所以 total 行的字节数可以比前面的行更宽。
    """
    floor = len(str(regular_bytes))
    if unknown_size:
        floor = max(floor, _UNKNOWN_SIZE_WIDTH)
    aligned = options.column_count >= 2 or total_printed

    widths: dict[str, int] = {}
    for column in _COLUMN_ORDER:
        if not options.enabled(column):
            continue
        width = 1
        for _, counts in rows:
            width = max(width, len(str(counts.value(column))))
        if aligned:
            width = max(width, floor)
        widths[column] = width
    return widths


def _write_row(
    ctx: RunContext,
    counts: _Counts,
    options: _Options,
    widths: dict[str, int],
    name: str | None,
) -> None:
    """输出一行计数，右对齐到列宽，列之间用一个空格隔开。"""
    parts = []
    for column in _COLUMN_ORDER:
        if not options.enabled(column):
            continue
        parts.append(f"{counts.value(column):>{widths[column]}d}")
    line = " ".join(parts)
    if name is not None:
        line = f"{line} {name}"
    ctx.stdout.write(f"{line}\n")


class _Source:
    """待统计的数据源。

    负责两件事：把内容按块吐出来；在吐出第一块之前先 sniff 一次编码，
    后面每一块内容都按这个编码解码。
    """

    def __init__(self, chunks: Iterator[bytes]) -> None:
        self._chunks = chunks
        self._primed = False
        self._first = b""
        self._encoding = _BINARY_ENCODING

    def _prime(self) -> None:
        if self._primed:
            return
        self._primed = True
        self._first = next(self._chunks, b"")
        self._encoding = _pick_encoding(self._first[:_SNIFF_SIZE])

    def chunks(self) -> Iterator[bytes]:
        self._prime()
        if self._first:
            yield self._first
        yield from self._chunks

    def encoding(self) -> str:
        self._prime()
        return self._encoding


def _resolve(cwd: Path, operand: str) -> Path:
    target = Path(operand)
    if not target.is_absolute():
        target = cwd / target
    return target


def _stdin_chunks(ctx: RunContext) -> Iterator[bytes]:
    """从标准输入取原始字节。

    文本模式的 stdin 会把 CRLF 归一成 LF、丢掉 lone CR，那不是 wc 该做的事，
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


def _count_stream(source: _Source, options: _Options) -> _Counts:
    """统计一个来源。

    只按需要的东西算：没打开 -w 就不数词，没打开 -m/-L 就不解码，
    大文件也不会因为多算一列而变慢。
    """
    counts = _Counts()
    encoding = source.encoding()
    for raw, terminated in _split_lines(source.chunks()):
        if terminated:
            counts.lines += 1
        counts.bytes += len(raw) + (1 if terminated else 0)
        if not options.needs_text:
            continue
        text = _decode(raw, encoding)
        if options.words:
            counts.words += _count_words(text)
        if options.chars:
            counts.chars += len(text) + (1 if terminated else 0)
        if options.max_line_length:
            width = _display_width(text)
            if width > counts.max_line_length:
                counts.max_line_length = width
    return counts


def _split_lines(chunks: Iterator[bytes]) -> Iterator[tuple[bytes, bool]]:
    """按 "\\n" 切行，产出 (原始字节, 是否以换行结尾)。

    只认 "\\n" 作行分隔符，"\\r" 留在行内容里，与 GNU 一致。
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


def _count_words(text: str) -> int:
    """数词：空白隔开的片段算一个词。

    GNU 的规则（实测自 coreutils 8.32）比「按空白切」多两条：

    - 片段里夹着控制字符不算断开：``a\\x01b`` 算一个词，不是两个
    - 整个片段里一个可打印字符都没有时不算词：纯二进制内容词数是 0

    中文、字母这类正常字符算可打印，所以中文文件里的中文算词。
    词不会跨过换行，所以按行统计与按整篇统计结果一致。
    """
    words = 0
    in_word = False
    printable = False
    for char in text:
        if char in _WHITESPACE:
            if in_word:
                if printable:
                    words += 1
                in_word = False
                printable = False
            continue
        in_word = True
        if _is_printable(char):
            printable = True
    if in_word and printable:
        words += 1
    return words


def _is_printable(char: str) -> bool:
    """这个字符算不算可打印字符（决定一个片段算不算词）。"""
    return unicodedata.category(char) not in ("Cc", "Cf", "Cs")


def _decode(raw: bytes, encoding: str) -> str:
    """按判定出的编码解码一段内容。

    解不出来时退到「能解的按 utf-8 解，解不出的字节一个算一个字符」，
    与 GNU 在 C 区域设置下的行为一致：GNU 数不出非法字节序列有几个字符，
    就把它们按字节算。
    """
    try:
        return raw.decode(encoding)
    except UnicodeDecodeError:
        return _decode_bytes(raw)


def _decode_bytes(raw: bytes) -> str:
    """兜底解码：解不出的字节不算字符，直接跳过。

    GNU 在 C 区域设置下遇到非法字节序列时，那一段既不算字符也不算词，
    直接跳过与它的行为一致。
    """
    out: list[str] = []
    index = 0
    length = len(raw)
    while index < length:
        for size in (1, 2, 3, 4):
            chunk = raw[index:index + size]
            try:
                out.append(chunk.decode("utf-8"))
            except UnicodeDecodeError:
                continue
            index += size
            break
        else:
            # 解不出的字节直接跳过，不占字符，也不占词。
            index += 1
    return "".join(out)


def _display_width(text: str) -> int:
    """算一行占多少显示列。

    - 制表符展开到下一个制表位（8 的倍数）
    - \\r 把列号清零，GNU 也是这么算的
    - 其余字符按显示宽度算：全角 2 列，组合字符 0 列
    - 取这一行出现过的最大列数：\\r 之后的宽度再大也不算数
    """
    width = 0
    widest = 0
    for char in text:
        if char == "\t":
            width = (width // _TAB_STOP + 1) * _TAB_STOP
        elif char == "\r":
            width = 0
        else:
            width += _char_width(char)
        if width > widest:
            widest = width
    return widest


def _char_width(char: str) -> int:
    """单个字符占几列。"""
    if unicodedata.combining(char):
        return 0
    category = unicodedata.category(char)
    if category in ("Mn", "Me", "Cf", "Cs", "Cc"):
        return 0
    if unicodedata.east_asian_width(char) in ("W", "F"):
        return 2
    return 1


def _pick_encoding(sample: bytes) -> str:
    """按内容选解码方式。

    分三类：

    - 文本：先判定编码再解码，中文按 UTF-8 输出，Windows 控制台上正常显示。
      判据是样本能被 utf-8 / 系统首选编码 / gb18030 之一严格解码。
    - 二进制（含 NUL 字节，或谁也解不出来）：按 utf-8 解，解不出的字节按
      一个字节一个字符算。

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
