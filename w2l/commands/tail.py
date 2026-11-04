"""tail：打印文件末尾部分（GNU tail 风格子集）。

对齐 GNU tail 的部分（行为实测自 coreutils 8.32）：

- 默认打印末 10 行；-n 指定行数，-c 指定字节数，两个都给时后写的那个生效
- 计数可以带正负号，这是 tail 与 head 最大的不同：

  - `-n 5`  取末 5 行
  - `-n +5` 从第 5 行开始一直到最后（head 的 +5 等价 5，tail 的 +5 是起点）
  - `-n -5` 与 `-n 5` 同义，也是取末 5 行；`-n 0` 一个不要，`-n +0` 全部都要
  - `-c` 同理，只是量的单位是字节：`+N` 从第 N 个字节开始
- 计数可以带乘数后缀：b=512，k/K=1024，m/M=1024²，G=1024³，T=1024⁴，
  P=1024⁵，E=1024⁶；字母加 B 是 1000 进制（kB=1000，MB=1000²），
  字母加 iB 是二进制前缀（KiB=K，MiB=M）
  -n 的后缀乘的是行数，-c 的后缀乘的是字节数
- 多个文件时每个文件前打印 `==> 文件名 <==` 标题，第二个及以后的标题前
  先空一行；-q 不打标题，-v 强制打标题，两个同时给时后写的那个生效
- 操作数 - 表示标准输入；不给操作数时也读标准输入
- -z 把行分隔符换成 NUL
- 打不开的文件不打印标题，只报错并继续处理后面的文件；目录则先打标题再报错
- -f 跟随文件增长，-F 跟随文件名（日志轮转场景）

与 GNU 的差异（README 有完整说明）：

- 文本文件按判定出的编码解码后统一输出 UTF-8，所以 GBK 中文在 Windows
  控制台上正常显示；GNU tail 是字节透传，直接把 GBK 字节写出去
- 文件打不开时按本项目约定返回退出码 2（GNU tail 返回 1），其余文件照常输出
- --max-unchanged-stats 没实现；轮转靠比较文件标识识别，行为等价
"""

from __future__ import annotations

import argparse
import codecs
import locale
import os
import re
import sys
import time
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

# GNU 的计数上界：正负号都按 uintmax 算（tail 里负号等价于正号）。
_UINTMAX_MAX = (1 << 64) - 1

# 单字母后缀对应的指数：k=1、m=2、G=3、T=4、P=5、E=6、Z=7、Y=8。
# Z/Y 只是指数太大算不出来（1024^7 超出 uintmax），语法本身合法。
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
_NUMBER_RE = re.compile(r"([+-]?)(\d+)(b|[kKmMGTPEZY](?:B|iB)?)?$")
# GNU 的紧凑写法 `-NUM`，等价于 `-n NUM`。
_COMPACT_RE = re.compile(r"-(\d+(?:b|[kKmMGTPEZY](?:B|iB)?)?)$")


@dataclass(frozen=True)
class _Options:
    """一组生效的选项。"""

    mode: str  # "lines" 或 "bytes"
    direction: str  # "last"（末尾 N 个）或 "from"（从第 N 个开始）
    amount: int  # 数量
    header_mode: str | None  # "quiet" / "verbose" / None
    zero_terminated: bool
    follow: str | None  # None / "descriptor" / "name"
    sleep_interval: float
    pid: int | None
    retry: bool

    @property
    def delimiter(self) -> bytes:
        """行分隔符：-z 时是 NUL，否则是换行。"""
        return b"\x00" if self.zero_terminated else b"\n"


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


class _TailParser(argparse.ArgumentParser):
    """把 GNU 的写法改写成 argparse 认得的写法。

    三处要改：

    - `-2`：GNU 把它当成 `-n 2`，但 argparse 会把 `-2` 当成位置参数
    - `-n -2`：值以负号开头时 argparse 会把它当成下一个选项，
      改写成 `-n=-2` 才能把负号原样交给值解析
    - `-f` / `--follow`：GNU 的可选参数只认 `-f=name` 这种写法，
      单独一个 `-f` 表示按文件描述符跟随，后面的词不算它的值
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
    """改写命令行参数：紧凑的 -NUM、负号开头的值、以及 follow 的可选参数。"""
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

        if arg == "--follow":
            # GNU 的 --follow 单独出现时按 descriptor 处理，后面的词不算值。
            out.append("--follow=descriptor")
            index += 1
            continue

        if arg == "-f":
            out.append("-f=descriptor")
            index += 1
            continue

        if arg.startswith("-f") and len(arg) > 2:
            # 短选项可以贴着写：-fname 等价于 -f=name
            out.append(f"-f={arg[2:]}")
            index += 1
            continue

        out.append(arg)
        index += 1
    return out


def build_parser() -> argparse.ArgumentParser:
    prog = command_prog("tail")
    parser = _TailParser(
        prog=prog,
        description="打印文件末尾部分",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            f"  {prog} w2l/cli.py\n"
            f"  {prog} -n 20 w2l/registry.py\n"
            f"  {prog} -c 512 w2l/context.py\n"
            f"  {prog} -n +20 w2l/cli.py\n"
            f"  {prog} -q w2l/cli.py w2l/context.py\n"
            f"  {prog} -f w2l/cli.py\n"
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
        help="打印末 NUM 行（默认 10）；NUM 带 + 号表示从第 NUM 行开始",
    )
    parser.add_argument(
        "-c",
        "--bytes",
        dest="count_specs",
        action=_CountAction,
        const="bytes",
        metavar="NUM",
        help="打印末 NUM 字节；NUM 带 + 号表示从第 NUM 字节开始；与 -n 同时给时后写的生效",
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
    parser.add_argument(
        "-f",
        "--follow",
        dest="follow",
        nargs="?",
        const="descriptor",
        choices=("name", "descriptor"),
        help="跟随文件增长；不写值时按文件描述符跟随",
    )
    parser.add_argument(
        "-F",
        dest="follow_name",
        action="store_true",
        help="等价于 --follow=name --retry（日志轮转场景）",
    )
    parser.add_argument(
        "-s",
        "--sleep-interval",
        dest="sleep_interval",
        type=float,
        default=1.0,
        metavar="N",
        help="跟随时两次检查之间的间隔秒数（默认 1）",
    )
    parser.add_argument(
        "--pid",
        dest="pid",
        type=int,
        default=None,
        metavar="PID",
        help="跟随时，等这个进程退出就结束",
    )
    parser.add_argument(
        "--retry",
        dest="retry",
        action="store_true",
        help="文件暂时打不开时继续重试而不是放弃",
    )
    return parser


@command("tail", "打印文件末尾部分（GNU tail 风格子集）", build_parser)
def tail(args: argparse.Namespace, ctx: RunContext) -> int:
    options = _build_options(args)
    files = list(args.files) if args.files else ["-"]
    print_headers = _resolve_headers(options.header_mode, len(files))

    _prepare_stdout(ctx)

    header_count = 0
    had_error = False
    stdin_read = False
    followers: list[_Follower] = []
    opened: list[IO[bytes]] = []

    try:
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
                handle = _stdin_handle(ctx)
                if options.follow is not None:
                    payload = _read_tail(handle, 0, options, seekable=False)
                    follower = _Follower(
                        _STDIN_NAME, None, handle, by_name=False, delimiter=options.delimiter
                    )
                    follower.encoding = _pick_encoding(payload)
                    _write(ctx, payload, follower.encoding)
                    _flush(ctx)
                    followers.append(follower)
                    continue
                _emit(_read_tail(handle, 0, options, seekable=False), options, ctx)
                continue

            path = _resolve(ctx.cwd, name)
            if path.is_dir():
                # GNU 先打标题再报读取错误，标题照打。
                if print_headers:
                    _print_header(ctx, name, header_count)
                    header_count += 1
                ctx.stderr.write(f"tail: 读取 '{name}' 出错: 是一个目录\n")
                had_error = True
                continue

            try:
                handle = path.open("rb")
            except OSError as exc:
                # 打不开的文件不打标题，只报错。
                ctx.stderr.write(f"tail: 无法打开 '{name}': {exc.strerror or exc}\n")
                had_error = True
                continue

            if print_headers:
                _print_header(ctx, name, header_count)
                header_count += 1

            size = _file_size(handle)
            payload = _read_tail(handle, size, options, seekable=True)

            if options.follow is not None:
                by_name = options.follow == "name"
                follower = _Follower(
                    name,
                    path,
                    None if by_name else handle,
                    by_name=by_name,
                    delimiter=options.delimiter,
                )
                follower.position = size
                follower.encoding = _pick_encoding(payload)
                _write(ctx, payload, follower.encoding)
                _flush(ctx)
                followers.append(follower)
                if by_name:
                    # 按文件名跟随时不长期占着句柄：Windows 上打开着的
                    # 文件不能改名，日志轮转第一步就卡住。
                    handle.close()
                else:
                    opened.append(handle)
                continue

            opened.append(handle)
            _emit(payload, options, ctx)

        if options.follow is not None and followers:
            _follow_loop(followers, options, ctx)
    finally:
        for handle in opened:
            try:
                handle.close()
            except (OSError, ValueError):
                pass

    if had_error:
        return 2
    return 0


def _build_options(args: argparse.Namespace) -> _Options:
    specs = getattr(args, "count_specs", None) or []
    if specs:
        mode, text = specs[-1]
    else:
        mode, text = "lines", str(_DEFAULT_LINES)

    follow = getattr(args, "follow", None)
    retry = bool(getattr(args, "retry", False))
    if getattr(args, "follow_name", False):
        # -F 等价于 --follow=name --retry
        follow = "name"
        retry = True

    direction, amount = _parse_amount(text, mode)
    interval = float(getattr(args, "sleep_interval", 1.0) or 0.0)
    return _Options(
        mode=mode,
        direction=direction,
        amount=amount,
        header_mode=getattr(args, "header_mode", None),
        zero_terminated=bool(getattr(args, "zero_terminated", False)),
        follow=follow,
        sleep_interval=max(interval, 0.0),
        pid=getattr(args, "pid", None),
        retry=retry,
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


def _parse_amount(text: str, mode: str) -> tuple[str, int]:
    """解析 -n/-c 的参数，返回 (方向, 数量)。

    GNU 的规则：

    - `+N` 是「从第 N 个开始」，N=0 表示从头开始，也就是全部都要
    - `N` 与 `-N` 都是「末尾 N 个」，N=0 表示一个也不要
    - 数字后面可以带乘数后缀，-n 乘行数、-c 乘字节数
    """
    label = "行数" if mode == "lines" else "字节数"
    raw = text.lstrip(" \t")
    match = _NUMBER_RE.match(raw)
    if match is None:
        raise UsageError(f"无效的{label} '{text}'")

    sign = match.group(1)
    digits = match.group(2)
    suffix = match.group(3)
    amount = int(digits) * _suffix_multiplier(suffix)

    if amount > _UINTMAX_MAX:
        raise UsageError(f"无效的{label} '{text}': 数值超出可表示范围")

    if sign == "+":
        return "from", amount
    return "last", amount


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
      "\\r\\n"，那会把 LF 文件和 CRLF 文件的区别抹掉；tail 的职责是原样
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


# ---------------------------------------------------------------- 内容读取


def _stdin_handle(ctx: RunContext) -> object:
    """标准输入的底层二进制流。

    文本模式的 stdin 会把 CRLF 归一成 LF、丢掉 lone CR，那不是 tail
    该做的事，所以优先走底层二进制流；拿不到二进制流时退回文本再编码回
    UTF-8。
    """
    stream = ctx.stdin
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        return buffer
    return _TextStreamAdapter(stream)


class _TextStreamAdapter:
    """没有二进制流时的兜底：把文本重新编码成 UTF-8 字节。"""

    def __init__(self, stream: object) -> None:
        self._stream = stream

    def read(self, size: int = -1) -> bytes:
        data = self._stream.read(size)  # type: ignore[union-attr]
        if not data:
            return b""
        return data.encode("utf-8", errors="surrogateescape")

    def read1(self, size: int = -1) -> bytes:
        return self.read(size)

    def seek(self, offset: int, whence: int = 0) -> int:
        raise OSError("标准输入不可定位")


def _file_size(handle: IO[bytes]) -> int:
    """文件长度；取不到就当 0。"""
    try:
        return os.fstat(handle.fileno()).st_size
    except (OSError, ValueError, AttributeError):
        return 0


def _read_some(handle: object, size: int) -> bytes:
    """读一块数据。

    有 read1 就用 read1：管道上 read(n) 会等凑满 n 个字节才返回，
    跟随时那样会把新来的内容卡住。
    """
    read1 = getattr(handle, "read1", None)
    if read1 is not None:
        try:
            return read1(size)
        except (ValueError, OSError):
            return b""
    try:
        return handle.read(size)  # type: ignore[union-attr]
    except (ValueError, OSError):
        return b""


def _read_tail(handle: object, size: int, options: _Options, seekable: bool) -> bytes:
    """取需要输出的那段内容。

    - 方向是 "last"：取末尾 N 个（行或字节）
    - 方向是 "from"：从第 N 个开始一直到末尾（行或字节），N=0 表示全部

    行模式会从文件末尾往回读，凑够 N 行就停，不必把整个文件读一遍。
    标准输入不能定位，只能顺序读。
    """
    if options.mode == "bytes":
        return _read_tail_bytes(handle, size, options, seekable)
    return _read_tail_lines(handle, size, options, seekable)


def _read_tail_bytes(
    handle: object, size: int, options: _Options, seekable: bool
) -> bytes:
    """按字节取。"""
    amount = options.amount

    if options.direction == "from":
        if not seekable:
            return _read_bytes_from_stream(handle, amount)
        if amount <= 0:
            return _read_from(handle, 0)
        if size and amount > size:
            return b""
        return _read_from(handle, amount - 1)

    if amount <= 0:
        return b""
    if seekable and size:
        start = max(0, size - amount)
        return _read_from(handle, start)
    # 长度未知（标准输入）时只能顺序读，边读边留末尾
    tail = bytearray()
    while True:
        chunk = _read_some(handle, _READ_SIZE)
        if not chunk:
            break
        tail += chunk
        if len(tail) > amount:
            del tail[: len(tail) - amount]
    return bytes(tail)


def _read_bytes_from_stream(handle: object, amount: int) -> bytes:
    """标准输入上取「从第 N 个字节开始」的内容。"""
    if amount <= 0:
        return _read_from(handle, 0)
    remaining = amount - 1
    while remaining > 0:
        chunk = _read_some(handle, min(remaining, _READ_SIZE))
        if not chunk:
            return b""
        remaining -= len(chunk)
    chunks: list[bytes] = []
    while True:
        chunk = _read_some(handle, _READ_SIZE)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def _read_from(handle: object, offset: int) -> bytes:
    """从指定偏移读到最后。"""
    try:
        handle.seek(offset)  # type: ignore[union-attr]
    except (OSError, ValueError):
        return b""
    chunks: list[bytes] = []
    while True:
        chunk = _read_some(handle, _READ_SIZE)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def _read_tail_lines(handle: object, size: int, options: _Options, seekable: bool) -> bytes:
    """按行取。"""
    amount = options.amount
    delimiter = options.delimiter

    if options.direction == "from":
        if not seekable:
            return _read_lines_from_stream(handle, amount - 1, delimiter)
        if amount <= 0:
            return _read_from(handle, 0)
        return _read_lines_from(handle, amount - 1, delimiter)

    if amount <= 0:
        return b""
    if seekable and size:
        return _read_last_lines(handle, size, amount, delimiter)

    # 长度未知（标准输入）时顺序读，保留末尾 amount 行
    keep: deque[bytes] = deque(maxlen=amount)
    for line in _iter_lines(_iter_chunks(handle), delimiter):
        keep.append(line)
    return b"".join(keep)


def _read_last_lines(handle: object, size: int, count: int, delimiter: bytes) -> bytes:
    """从文件末尾往回读，凑齐 count 行。

    回读的起点多半落在行中间，开头那截半行不是完整的一行，要丢掉；
    所以要凑够 count+1 个分隔符才停。多读的那一块不算浪费，
    换来的是不用把整个文件从头读一遍。
    """
    position = size
    buffer = bytearray()
    while position > 0:
        step = min(_READ_SIZE, position)
        position -= step
        try:
            handle.seek(position)  # type: ignore[union-attr]
            chunk = handle.read(step)  # type: ignore[union-attr]
        except (OSError, ValueError):
            break
        if not chunk:
            break
        buffer = bytearray(chunk) + buffer
        if buffer.count(delimiter) >= count + 1:
            break

    lines = list(_iter_lines([bytes(buffer)], delimiter))
    if position > 0:
        # 起点在行中间，第一段是半行，丢掉。
        lines = lines[1:]
    return b"".join(lines[-count:])


def _read_lines_from(handle: object, skip: int, delimiter: bytes) -> bytes:
    """跳过开头 skip 行，把剩下的全要。"""
    out: list[bytes] = []
    seen = 0
    buffer = bytearray()
    started = False

    for chunk in _iter_chunks(handle):
        if started:
            out.append(chunk)
            continue
        buffer += chunk
        while True:
            index = buffer.find(delimiter)
            if index < 0:
                break
            end = index + len(delimiter)
            seen += 1
            line = bytes(buffer[:end])
            buffer = bytearray(buffer[end:])
            if seen > skip:
                out.append(line)
                started = True
                break
    if not started:
        # 文件行数不够 skip+1 行，什么都不输出。
        # 末行没有分隔符时它也算一行，seen+1 才是总行数。
        if buffer and seen + 1 > skip:
            out.append(bytes(buffer))
    elif buffer:
        out.append(bytes(buffer))
    return b"".join(out)


def _read_lines_from_stream(handle: object, skip: int, delimiter: bytes) -> bytes:
    """标准输入上「从第 N 行开始」的内容。"""
    out: list[bytes] = []
    seen = 0
    buffer = bytearray()
    started = False

    for chunk in _iter_chunks(handle):
        if started:
            out.append(chunk)
            continue
        buffer += chunk
        while True:
            index = buffer.find(delimiter)
            if index < 0:
                break
            end = index + len(delimiter)
            seen += 1
            line = bytes(buffer[:end])
            buffer = bytearray(buffer[end:])
            if seen > skip:
                out.append(line)
                started = True
                break
    if not started:
        if buffer and seen + 1 > skip:
            out.append(bytes(buffer))
    elif buffer:
        out.append(bytes(buffer))
    return b"".join(out)


def _iter_chunks(handle: object) -> Iterator[bytes]:
    while True:
        chunk = _read_some(handle, _READ_SIZE)
        if not chunk:
            return
        yield chunk


def _iter_lines(chunks: Iterator[bytes], delimiter: bytes) -> Iterator[bytes]:
    """按分隔符切行，行内容连分隔符一起产出。

    只认 "\\n" 作行分隔符（-z 时是 NUL），"\\r" 留在行内容里：这样
    CRLF 文件的行内容是 "xxx\\r\\n"，与 GNU 的判定一致。
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


# ---------------------------------------------------------------- 跟随模式


class _Follower:
    """跟随一个文件（或者标准输入）的增长。

    - by_name=False：认文件描述符。文件被改名了也照样跟着旧句柄读。
    - by_name=True：认文件名。文件被轮转掉了（换了一个新文件）就重新
      打开接着读，这正是日志轮转想要的。

    按文件名跟随时每轮都重新打开再关掉，不长期占着句柄：Windows 上
    打开着的文件不能改名（FILE_SHARE_DELETE 没开），日志轮转第一步
    就是改名，长期占着句柄的话这一步直接失败。
    """

    def __init__(
        self,
        name: str,
        path: Path | None,
        handle: object,
        by_name: bool,
        delimiter: bytes = b"\n",
    ) -> None:
        self.name = name
        self.path = path
        self.handle = handle
        self.by_name = by_name
        self.delimiter = delimiter
        self.position = 0
        self.pending = bytearray()
        self.encoding = _BINARY_ENCODING
        self.identity: tuple[int, int] | None = None
        self.missing = False

    def poll(self) -> bytes:
        """读出新增内容，返回可以输出的完整行。"""
        if self.by_name:
            chunk = self._read_by_name()
        else:
            chunk = self._read_by_descriptor()
        if not chunk:
            return b""
        self.pending += chunk
        lines, self.pending = _take_complete_lines(self.pending, self.delimiter)
        return b"".join(lines)

    def _read_by_descriptor(self) -> bytes:
        """顺着同一个句柄往后读。"""
        if self.path is not None:
            try:
                self.handle.seek(self.position)  # type: ignore[union-attr]
            except (OSError, ValueError):
                pass

        chunk = _read_some(self.handle, _READ_SIZE)
        if chunk and self.path is not None:
            self.position += len(chunk)
        return chunk

    def _read_by_name(self) -> bytes:
        """按文件名重新打开往后读，顺带处理轮转与截断。"""
        if self.path is None:
            return b""

        try:
            stat = os.stat(self.path)
        except OSError:
            self.missing = True
            return b""

        self.missing = False
        identity = (stat.st_ino, stat.st_dev)
        if self.identity is None:
            self.identity = identity
        elif identity != self.identity:
            # 文件被换掉了（日志轮转），从头读新文件。
            self.position = 0
            self.pending = bytearray()
            self.identity = identity
        elif stat.st_size < self.position:
            # 文件被截断，从头接着读。
            self.position = 0
            self.pending = bytearray()

        try:
            handle = open(self.path, "rb")
        except OSError:
            self.missing = True
            return b""
        try:
            handle.seek(self.position)
            chunk = _read_some(handle, _READ_SIZE)
        except (OSError, ValueError):
            return b""
        finally:
            handle.close()

        if chunk:
            self.position += len(chunk)
        return chunk


def _take_complete_lines(buffer: bytearray, delimiter: bytes) -> tuple[list[bytes], bytearray]:
    """从缓冲里切出完整行，末尾那段不完整的留在缓冲里。

    跟随时半行不能马上输出：写日志的程序可能正在写一半，等它写完
    换行符再整体输出，才不会出现半截行。
    """
    lines: list[bytes] = []
    start = 0
    while True:
        index = buffer.find(delimiter, start)
        if index < 0:
            break
        end = index + len(delimiter)
        lines.append(bytes(buffer[start:end]))
        start = end
    rest = bytearray(buffer[start:])
    buffer[:] = rest
    return lines, rest


def _follow_loop(
    followers: list[_Follower],
    options: _Options,
    ctx: RunContext,
    max_iterations: int | None = None,
) -> None:
    """反复检查各文件有没有新内容。

    max_iterations 只给测试用：命令行路径传 None，一直跟下去。
    """
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        for follower in followers:
            data = follower.poll()
            if data:
                _write(ctx, data, follower.encoding)
                _flush(ctx)
        if options.pid is not None and not _pid_alive(options.pid):
            return
        if max_iterations is not None and iterations >= max_iterations:
            return
        if options.sleep_interval > 0:
            time.sleep(options.sleep_interval)


def _pid_alive(pid: int) -> bool:
    """目标进程还活着吗。

    Windows 上不能用 os.kill(pid, 0)：那边的 0 号信号会真的把进程
    终止掉，所以改用 OpenProcess 探一下句柄。
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            # PROCESS_QUERY_LIMITED_INFORMATION
            handle = kernel32.OpenProcess(0x1000, False, pid)
        except (AttributeError, OSError):
            return True
        if handle:
            kernel32.CloseHandle(handle)
            return True
        # 打不开多半是权限不足，进程应该还在
        return kernel32.GetLastError() == 5
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


# ---------------------------------------------------------------- 输出


def _emit(payload: bytes, options: _Options, ctx: RunContext) -> None:
    """把取到的那段内容写出去。"""
    if not payload:
        return
    encoding = _pick_encoding(payload)
    _write(ctx, payload, encoding)


def _write(ctx: RunContext, raw: bytes, encoding: str) -> None:
    """把一段字节解码后写出去。

    解不开的字节用代理码位占位，写回时还原成原字节，二进制内容因此
    不会被改写。
    """
    ctx.stdout.write(raw.decode(encoding, errors="surrogateescape"))


def _flush(ctx: RunContext) -> None:
    """把缓冲区里的内容立刻推出去。

    跟随时必须刷：输出接到管道上时 Python 是块缓冲（攒够 8KB 才写），
    不刷的话 `tail -f` 跟半天什么也看不见——GNU tail 跟随时是行缓冲的。
    """
    flush = getattr(ctx.stdout, "flush", None)
    if flush is None:
        return
    try:
        flush()
    except (ValueError, OSError):
        pass


def _pick_encoding(sample: bytes) -> str:
    """按内容选解码方式。

    分三类：

    - 文本：先判定编码再解码，中文按 UTF-8 输出，Windows 控制台上正常显示。
      判据是样本能被 utf-8 / 系统首选编码 / gb18030 之一严格解码。
    - 二进制（含 NUL 字节，或谁也解不出来）：按 utf-8 + surrogateescape
      解码，解不出的字节用代理码位占位，写回时还原成原字节。

    latin-1 永远能解任何字节，所以判定文本时不把它算进去，否则所有二进制
    都会被误判成文本。

    样本取的是「将要输出的那段」，不是文件开头：tail 只输出末尾几行，
    那几行是什么编码就按什么编码解，GBK 日志的末尾照样出中文。
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

    判定思路与 grep.py、cat.py、head.py 保持一致：系统首选编码在英文
    Windows 上是 cp1252，它几乎不报错，能把 GBK 字节解成乱码，所以不能
    按顺序取第一个能解的编码。
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
