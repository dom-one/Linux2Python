"""head：打印文件开头部分（GNU head 风格子集）。

对齐 GNU head 的部分（行为实测自 coreutils 8.32）：

- 默认打印前 10 行；-n 指定行数，-c 指定字节数，两个都给时后写的那个生效
- 计数可以带正负号：`-n 5` 取前 5 行，`-n +5` 与 `-n 5` 等价（head 没有
  tail 那种「从第 N 行开始」的语义），`-n -5` 取除末 5 行之外的全部
- 计数可以带乘数后缀：b=512，k/K=1024，m/M=1024²，G=1024³，T=1024⁴，
  P=1024⁵，E=1024⁶；字母加 B 是 1000 进制（kB=1000，MB=1000²），
  字母加 iB 是二进制前缀（KiB=K，MiB=M）
- 多个文件时每个文件前打印 `==> 文件名 <==` 标题，第二个及以后的标题前
  先空一行；-q 不打标题，-v 强制打标题，两个同时给时后写的那个生效
- 操作数 - 表示标准输入；不给操作数时也读标准输入
- -z 把行分隔符换成 NUL
- 打不开的文件不打印标题，只报错并继续处理后面的文件

与 GNU 的差异（README 有完整说明）：

- 文本文件按判定出的编码解码后统一输出 UTF-8，所以 GBK 中文在 Windows
  控制台上正常显示；GNU head 是字节透传，直接把 GBK 字节写出去
- 文件打不开时按本项目约定返回退出码 2（GNU head 返回 1），其余文件照常输出
"""

from __future__ import annotations

import argparse
import codecs
import locale
import re
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Iterator

from ..context import RunContext
from ..entry import command_prog
from ..errors import UsageError
from ..registry import command

_DEFAULT_LINES = 10
_SNIFF_SIZE = 8192
_READ_SIZE = 65536
_SCORE_MARGIN = 0.3
_CJK_RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF))
_FALLBACK_ENCODINGS = ("utf-8", "gb18030", "latin-1")
_BINARY_ENCODING = "utf-8"
_STDIN_NAME = "standard input"

# GNU 的整数上界：非负数按 uintmax 算，负数按 intmax 算。
_UINTMAX_MAX = (1 << 64) - 1
_INTMAX_MAX = (1 << 63) - 1

# 单字母后缀对应的指数：k=1、m=2、G=3、T=4、P=5、E=6、Z=7、Y=8。
# Z/Y 只是指数太大算不出来（1024^7 超出 intmax），语法本身合法。
_SUFFIX_EXPONENT = {
    "k": 1,
    "K": 1,
    "m": 2,
    "M": 2,
    "G": 3,
    "T": 4,
    "P": 5,
    "E": 6,
    "Z": 7,
    "Y": 8,
}
_BLOCK_SIZE = 512

# 数字部分：一个可选正负号、若干数字、可选乘数后缀。
# 后缀里 B / iB 两段都是可选的：k、kB、kiB 三种都合法。
_NUMBER_RE = re.compile(r"[+-]?(\d+)(b|[kKmMGTPEZY](?:B|iB)?)?$")
# GNU 的紧凑写法 `-NUM`，等价于 `-n NUM`。
_COMPACT_RE = re.compile(r"-(\d+(?:b|[kKmMGTPEZY](?:B|iB)?)?)$")


@dataclass(frozen=True)
class _Options:
    """一组生效的选项。"""

    mode: str  # "lines" 或 "bytes"
    negative: bool  # 带负号：表示「除末 N 行/字节之外全要」
    amount: int  # 数量绝对值
    header_mode: str | None  # "quiet" / "verbose" / None
    zero_terminated: bool


class _Source:
    """待读取的数据源：文件或标准输入。

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


class _CountAction(argparse.Action):
    """记录 -n/-c 的出现顺序。

    GNU 里两个都给时后写的那个生效，所以不能各存一个 dest 再挑一个，
    得按顺序存下来，最后一个说了算。
    """

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: object,
        option_string: str | None = None,
    ) -> None:
        specs = getattr(namespace, self.dest, None)
        if specs is None:
            specs = []
            setattr(namespace, self.dest, specs)
        specs.append((self.const, values))


class _HeadParser(argparse.ArgumentParser):
    """把 GNU 的紧凑写法改写成 argparse 认得的写法。

    两处要改：

    - `-2`：GNU 把它当成 `-n 2`，但 argparse 会把 `-2` 当成位置参数
    - `-n -2`：值以负号开头时 argparse 会把它当成下一个选项，
      改写成 `-n=-2` 才能把负号原样交给值解析
    """

    def parse_known_args(
        self,
        args: list[str] | None = None,
        namespace: argparse.Namespace | None = None,
    ) -> tuple[argparse.Namespace, list[str]]:
        if args is None:
            args = sys.argv[1:]
        return super().parse_known_args(_rewrite_argv(list(args)), namespace)


def _rewrite_argv(args: list[str]) -> list[str]:
    """改写命令行参数：紧凑的 -NUM，以及值以负号开头的 -n/-c。"""
    out: list[str] = []
    index = 0
    literal = False
    while index < len(args):
        arg = args[index]
        if literal:
            out.append(arg)
            index += 1
            continue
        if arg == "--":
            literal = True
            out.append(arg)
            index += 1
            continue

        compact = _COMPACT_RE.fullmatch(arg)
        if compact:
            out.extend(["-n", compact.group(1)])
            index += 1
            continue

        if arg in ("-n", "-c", "--lines", "--bytes") and index + 1 < len(args):
            value = args[index + 1]
            if value.startswith("-"):
                out.append(f"{arg}={value}")
                index += 2
                continue

        out.append(arg)
        index += 1
    return out


def build_parser() -> argparse.ArgumentParser:
    prog = command_prog("head")
    parser = _HeadParser(
        prog=prog,
        description="打印文件开头部分",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            f"  {prog} w2l/cli.py\n"
            f"  {prog} -n 20 w2l/registry.py\n"
            f"  {prog} -c 512 w2l/context.py\n"
            f"  {prog} -n -5 w2l/cli.py\n"
            f"  {prog} -q w2l/cli.py w2l/context.py\n"
        ),
    )
    parser.add_argument("files", nargs="*", help="要读取的文件，- 表示标准输入；不填则读标准输入")
    parser.add_argument(
        "-n",
        "--lines",
        dest="count_specs",
        action=_CountAction,
        const="lines",
        metavar="NUM",
        help="打印前 NUM 行（默认 10）；NUM 带负号表示除末 NUM 行之外全要",
    )
    parser.add_argument(
        "-c",
        "--bytes",
        dest="count_specs",
        action=_CountAction,
        const="bytes",
        metavar="NUM",
        help="打印前 NUM 字节；与 -n 同时给时后写的生效",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        "--silent",
        dest="header_mode",
        action="store_const",
        const="quiet",
        help="不打印文件名标题",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="header_mode",
        action="store_const",
        const="verbose",
        help="总是打印文件名标题",
    )
    parser.add_argument(
        "-z",
        "--zero-terminated",
        dest="zero_terminated",
        action="store_true",
        help="行分隔符用 NUL 而不是换行",
    )
    return parser


@command("head", "打印文件开头部分（GNU head 风格子集）", build_parser)
def head(args: argparse.Namespace, ctx: RunContext) -> int:
    options = _build_options(args)
    files = list(args.files) if args.files else ["-"]
    print_headers = _resolve_headers(options.header_mode, len(files))

    _prepare_stdout(ctx)

    header_count = 0
    had_error = False
    stdin_read = False

    for name in files:
        if name == "-":
            # GNU 对每个 - 操作数都打标题，但标准输入只读一次，
            # 第二次起是空的。
            if print_headers:
                _print_header(ctx, _STDIN_NAME, header_count)
                header_count += 1
            if stdin_read:
                continue
            stdin_read = True
            source = _Source(_stdin_chunks(ctx))
            _emit(source, options, ctx)
            continue

        path = _resolve(ctx.cwd, name)
        if path.is_dir():
            # GNU 先打标题再报读取错误，标题照打。
            if print_headers:
                _print_header(ctx, name, header_count)
                header_count += 1
            ctx.stderr.write(f"head: 读取 '{name}' 出错: 是一个目录\n")
            had_error = True
            continue

        try:
            handle = path.open("rb")
        except OSError as exc:
            # 打不开的文件不打标题，只报错。
            ctx.stderr.write(f"head: 无法打开 '{name}': {exc.strerror or exc}\n")
            had_error = True
            continue

        with handle:
            if print_headers:
                _print_header(ctx, name, header_count)
                header_count += 1
            source = _Source(_chunks(handle))
            _emit(source, options, ctx)

    if had_error:
        return 2
    return 0


def _build_options(args: argparse.Namespace) -> _Options:
    specs = getattr(args, "count_specs", None) or []
    if specs:
        mode, text = specs[-1]
    else:
        mode, text = "lines", str(_DEFAULT_LINES)
    negative, amount = _parse_amount(text, mode)
    return _Options(
        mode=mode,
        negative=negative,
        amount=amount,
        header_mode=getattr(args, "header_mode", None),
        zero_terminated=bool(getattr(args, "zero_terminated", False)),
    )


def _resolve_headers(header_mode: str | None, file_count: int) -> bool:
    """决定要不要打印文件名标题。

    默认多个文件时才打；-q 关掉，-v 强制打开。-q 与 -v 同时给时
    后写的那个生效，所以这里只看 argparse 留下的最终值。
    """
    if header_mode == "verbose":
        return True
    if header_mode == "quiet":
        return False
    return file_count > 1


def _parse_amount(text: str, mode: str) -> tuple[bool, int]:
    """解析 -n/-c 的参数，返回 (是否负号, 数量绝对值)。

    GNU 的规则：

    - 允许一个可选正负号；`+N` 与 `N` 等价
    - 负号表示「除末 N 行/字节之外全要」，所以 0 与 -0 含义不同：
      `-n 0` 一行不要，`-n -0` 全部都要
    - 数字后面可以带乘数后缀
    """
    label = "行数" if mode == "lines" else "字节数"
    raw = text.lstrip(" \t")
    match = _NUMBER_RE.match(raw)
    if match is None:
        raise UsageError(f"无效的{label} '{text}'")

    negative = raw.startswith("-")
    digits = match.group(1)
    suffix = match.group(2)
    amount = int(digits) * _suffix_multiplier(suffix)

    limit = _INTMAX_MAX if negative else _UINTMAX_MAX
    if amount > limit:
        raise UsageError(f"无效的{label} '{text}': 数值超出可表示范围")
    return negative, amount


def _suffix_multiplier(suffix: str | None) -> int:
    """算乘数后缀对应的倍数。

    - 单字母：1024 进制，k/K=1024，m/M=1024²，G=1024³，依次到 Y=1024⁸
    - 字母加 B：1000 进制，kB/KB=1000，MB=1000²，依次到 YB=1000⁸
    - 字母加 iB：二进制前缀，等同于对应的单字母形式（KiB=K）
    - b：固定 512，没有 B / iB 形式
    """
    if not suffix:
        return 1
    if suffix == "b":
        return _BLOCK_SIZE
    exponent = _SUFFIX_EXPONENT[suffix[0]]
    if suffix.endswith("iB"):
        return 1024**exponent
    if suffix.endswith("B"):
        return 1000**exponent
    return 1024**exponent


def _prepare_stdout(ctx: RunContext) -> None:
    """调整输出流，让内容按原样转交。

    - 管道与重定向时关掉换行翻译。Windows 上 Python 默认把 "\\n" 写成
      "\\r\\n"，那会把 LF 文件和 CRLF 文件的区别抹掉；head 的职责是原样
      转交内容，所以重定向时不翻译。控制台保持默认的 CRLF。
    - 错误处理改成 surrogateescape，解不出的字节用代理码位占位，
      写回时还能还原成原字节。
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


def _print_header(ctx: RunContext, name: str, header_count: int) -> None:
    """打印文件名标题。

    第二个及以后的标题前先空一行，与 GNU 一致。
    """
    if header_count > 0:
        ctx.stdout.write("\n")
    ctx.stdout.write(f"==> {name} <==\n")


def _stdin_chunks(ctx: RunContext) -> Iterator[bytes]:
    """从标准输入取原始字节。

    文本模式的 stdin 会把 CRLF 归一成 LF、丢掉 lone CR，那不是 head
    该做的事，所以优先走底层二进制流；拿不到二进制流时退回文本再编码回
    UTF-8。
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


def _emit(source: _Source, options: _Options, ctx: RunContext) -> None:
    """按模式输出内容。"""
    if options.mode == "lines":
        _emit_lines(source, options, ctx)
    else:
        _emit_bytes(source, options, ctx)


def _emit_lines(source: _Source, options: _Options, ctx: RunContext) -> None:
    """按行输出。

    行是按分隔符切出来的，分隔符跟着行一起走，所以内容能逐字节原样转交。
    """
    delimiter = b"\x00" if options.zero_terminated else b"\n"
    encoding = source.encoding()

    if options.negative:
        # 「除末 N 行之外全要」：手边留着最后 N 行，读到头再丢掉。
        pending: deque[bytes] = deque()
        for line in _split_lines(source.chunks(), delimiter):
            pending.append(line)
            if len(pending) > options.amount:
                _write(ctx, pending.popleft(), encoding)
        return

    remaining = options.amount
    for line in _split_lines(source.chunks(), delimiter):
        if remaining <= 0:
            break
        _write(ctx, line, encoding)
        remaining -= 1


def _emit_bytes(source: _Source, options: _Options, ctx: RunContext) -> None:
    """按字节输出。

    字节数按源文件的字节算，输出再按判定出的编码解码，所以 GBK 文件
    在控制台上看到的是中文，而不是乱码。
    """
    encoding = source.encoding()

    if options.negative:
        tail = bytearray()
        for chunk in source.chunks():
            tail += chunk
            if len(tail) > options.amount:
                cut = len(tail) - options.amount
                _write(ctx, bytes(tail[:cut]), encoding)
                del tail[:cut]
        return

    remaining = options.amount
    for chunk in source.chunks():
        if remaining <= 0:
            break
        take = chunk[:remaining]
        _write(ctx, take, encoding)
        remaining -= len(take)


def _split_lines(chunks: Iterator[bytes], delimiter: bytes) -> Iterator[bytes]:
    """按分隔符切行，行内容连分隔符一起产出。

    只认 "\\n" 作行分隔符（-z 时是 NUL），"\\r" 留在行内容里：这样
    CRLF 文件的空行内容是 "\\r" 而不是空行，与 GNU 的判定一致。
    """
    buffer = bytearray()
    for chunk in chunks:
        buffer += chunk
        start = 0
        while True:
            index = buffer.find(delimiter, start)
            if index < 0:
                break
            end = index + len(delimiter)
            yield bytes(buffer[start:end])
            start = end
        if start:
            del buffer[:start]
    if buffer:
        yield bytes(buffer)


def _write(ctx: RunContext, raw: bytes, encoding: str) -> None:
    """把一段字节解码后写出去。

    解不开的字节用代理码位占位，写回时还原成原字节，二进制内容因此
    不会被改写。
    """
    ctx.stdout.write(raw.decode(encoding, errors="surrogateescape"))


def _pick_encoding(sample: bytes) -> str:
    """按内容选解码方式。

    分三类：

    - 文本：先判定编码再解码，中文按 UTF-8 输出，Windows 控制台上正常显示。
      判据是样本能被 utf-8 / 系统首选编码 / gb18030 之一严格解码。
    - 二进制（含 NUL 字节，或谁也解不出来）：按 utf-8 + surrogateescape
      解码，解不出的字节用代理码位占位，写回时还原成原字节。

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

    判定思路与 grep.py、cat.py 保持一致：系统首选编码在英文 Windows 上
    是 cp1252，它几乎不报错，能把 GBK 字节解成乱码，所以不能按顺序取
    第一个能解的编码。
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
