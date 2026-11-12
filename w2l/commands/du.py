"""du：统计目录占用（GNU du 风格子集）。

对齐 GNU coreutils 8.32 的部分（全部依据本机 Git Bash 的 GNU du 实测）：

- 输出结构：每行是「大小<TAB>路径」，目录排在它自己的内容后面（后序遍历）
- 统计口径：表观大小——文件字节数之和，目录自身按 0 算
- 块大小：默认 1K，显示时把字节数向上取整到块；-b 按字节、-k/-m/-B 自定
- -a 连文件一起列，-s 每个操作数只给一行总数，-c 末尾再加一行 total
- -d N 只打印到第 N 层（统计照样算到底），-t SIZE 按阈值过滤
- -h/--si 人类可读（1024 进制 / 1000 进制），-S 目录大小不含子目录
- -0 用 NUL 分隔输出，--time 多打一列最后修改时间

Windows 环境下的必然差异（README 有完整说明）：

- GNU 默认报的是磁盘占用（按块向上取整），Windows 的 Python 拿不到每个文件占了几个块
  （os.stat_result 没有 st_blocks），所以本实现默认就按文件字节数统计
- 目录自身的大小按 0 算（与本项目的 find、tree 一致）
- 同层条目按名字排序，GNU 用的是目录原始顺序
- 符号链接在 Windows 上要管理员权限才能创建，相关行为没法完整验证
"""

from __future__ import annotations

import argparse
import os
import stat
import sys
import time
from pathlib import Path
from typing import NamedTuple

from ..context import RunContext
from ..entry import command_prog
from ..errors import UsageError
from ..registry import command

# GNU 的人类可读单位表：IEC 用 1024 进制，SI 用 1000 进制
_HUMAN_IEC = "KMGTPE"
_HUMAN_SI = "kMGTPE"

# 1024 进制后缀（不带 B 也表示这一档）
_SIZE_SUFFIX_1024 = {
    "k": 1024,
    "m": 1024**2,
    "g": 1024**3,
    "t": 1024**4,
    "p": 1024**5,
    "e": 1024**6,
}
# 1000 进制后缀（必须带 B）
_SIZE_SUFFIX_1000 = {
    "kb": 1000,
    "mb": 1000**2,
    "gb": 1000**3,
    "tb": 1000**4,
    "pb": 1000**5,
    "eb": 1000**6,
}


class _Record(NamedTuple):
    """一条待输出的记录：显示路径、大小、层级、最后修改时间。"""

    display: str
    size: int
    depth: int
    mtime: float
    is_dir: bool


class _State:
    """一次 du 运行的状态：去重表、累计字节数、输出记录与错误标记。"""

    def __init__(self, ctx: RunContext) -> None:
        self.ctx = ctx
        self.seen: set[tuple[int, int]] = set()
        self.total_bytes = 0
        self.records: list[_Record] = []
        self.had_error = False
        self.root_dev: int | None = None
        self.newest_mtime = 0.0

    def record(self, display: str, size: int, depth: int, mtime: float, is_dir: bool) -> None:
        self.records.append(_Record(display, size, depth, mtime, is_dir))
        if mtime > self.newest_mtime:
            self.newest_mtime = mtime

    def fail(self, message: str) -> None:
        """记一条错误并写进 stderr。"""
        self.had_error = True
        self.ctx.stderr.write(message + "\n")


class _HumanAction(argparse.Action):
    """-h 与 --si 都打开人类可读，命令行上靠后的那个决定进制。"""

    def __init__(self, option_strings, dest, base: str = "iec", **kwargs) -> None:
        self.base = base
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        setattr(namespace, self.dest, self.base)
        namespace.human = True


class _BlockSizeAction(argparse.Action):
    """-B 的取值先原样收下，报错文案要跟 GNU 一样才在本指令里统一处理。"""

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        setattr(namespace, self.dest, values)


# 这些选项后面跟一个值，值可能以负号开头（-t -1K 这种写法）
_VALUE_OPTIONS = ("-d", "--max-depth", "-B", "--block-size", "-t", "--threshold")


class _DuParser(argparse.ArgumentParser):
    """改写命令行参数：值以负号开头时改写成 `-t=-1K` 这种形式。

    argparse 会把 `-1K` 当成下一个选项而不是值，不改写就取不到负阈值。
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
    """把「选项 + 以负号开头的值」改写成 argparse 认得的写法。"""
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
        if arg in _VALUE_OPTIONS and index + 1 < len(args):
            value = args[index + 1]
            if value.startswith("-"):
                out.append(f"{arg}={value}")
                index += 2
                continue
        out.append(arg)
        index += 1
    return out


def build_parser() -> argparse.ArgumentParser:
    prog = command_prog("du")
    # GNU 的 -h 是 --human-readable，不是 --help，所以要关掉 argparse 自带的 -h
    parser = _DuParser(
        prog=prog,
        description="统计目录占用",
        add_help=False,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            f"  {prog}\n"
            f"  {prog} -s w2l\n"
            f"  {prog} -sh w2l tests\n"
            f"  {prog} -a -d 1 w2l\n"
            f"  {prog} -b w2l\n"
            f"  {prog} -t 1M w2l\n"
        ),
    )
    parser.add_argument("paths", nargs="*", help="要统计的路径，默认当前目录")
    parser.add_argument("-a", "--all", action="store_true", help="连普通文件一起列出")
    parser.add_argument("-c", "--total", action="store_true", help="末尾多打一行总计")
    parser.add_argument("-s", "--summarize", action="store_true", help="每个操作数只打一行总数")
    parser.add_argument("-d", "--max-depth", type=int, default=None, help="最多打印到第几层（操作数本身是第 0 层）")
    parser.add_argument(
        "-h",
        "--human-readable",
        action=_HumanAction,
        dest="human_base",
        base="iec",
        help="以 K/M/G 显示大小（1024 进制）",
    )
    parser.add_argument(
        "--si",
        action=_HumanAction,
        dest="human_base",
        base="si",
        help="同 -h，但用 1000 进制",
    )
    parser.add_argument("-b", "--bytes", dest="block_size_opt", action="store_const", const=1, help="以字节为单位显示")
    parser.add_argument("-k", dest="block_size_opt", action="store_const", const=1024, help="以 1K 为单位显示（默认）")
    parser.add_argument("-m", dest="block_size_opt", action="store_const", const=1024**2, help="以 1M 为单位显示")
    parser.add_argument(
        "-B",
        "--block-size",
        dest="block_size_opt",
        action=_BlockSizeAction,
        metavar="SIZE",
        help="以指定块大小为单位显示",
    )
    parser.add_argument(
        "-t",
        "--threshold",
        metavar="SIZE",
        help="小于阈值的条目不显示；给负数则只显示不大于它的条目",
    )
    parser.add_argument("-x", "--one-file-system", action="store_true", help="不跨越文件系统")
    parser.add_argument("-S", "--separate-dirs", action="store_true", help="目录大小不含子目录")
    parser.add_argument("-l", "--count-links", action="store_true", help="硬链接的文件重复计入")
    parser.add_argument("-L", "--dereference", dest="link_mode", action="store_const", const="all", help="跟随所有符号链接")
    parser.add_argument("-H", "--dereference-args", dest="link_mode", action="store_const", const="args", help="只跟随命令行上的符号链接")
    parser.add_argument("-P", "--no-dereference", dest="link_mode", action="store_const", const="none", help="不跟随符号链接（默认）")
    parser.add_argument("--time", action="store_true", help="多打一列最后修改时间")
    parser.add_argument("-0", "--null", action="store_true", help="用 NUL 而不是换行分隔输出")
    parser.add_argument(
        "--apparent-size",
        action="store_true",
        help="按文件字节数统计（本实现默认口径，写上也不改变行为）",
    )
    parser.add_argument("--help", action="help", help="显示此帮助信息并退出")
    parser.set_defaults(human=False, human_base=None, block_size_opt=1024, link_mode="none")
    return parser


@command("du", "统计目录占用（GNU du 风格子集）", build_parser)
def du(args: argparse.Namespace, ctx: RunContext) -> int:
    if args.summarize and args.all:
        raise UsageError("不能同时使用 '-s'（只给总数）与 '-a'（列出所有条目）")
    if args.summarize and args.max_depth is not None and args.max_depth > 0:
        # GNU 把它当冲突项：'-s' 等于 '--max-depth=0'，跟更大的层数矛盾
        raise UsageError(
            f"不能同时使用 '-s'（只给总数）与 '--max-depth={args.max_depth}'"
        )
    if args.max_depth is not None and args.max_depth < 0:
        raise UsageError(f"选项 '-d' 的层数不能为负数: {args.max_depth}")

    block_size = _resolve_block_size(args.block_size_opt)
    threshold = 0 if args.threshold is None else _parse_size(args.threshold, "-t")

    state = _State(ctx)
    operands = list(args.paths) if args.paths else ["."]
    for operand in operands:
        target = _resolve(ctx.cwd, operand)
        _scan_operand(target, operand, args, state)

    printed = _flush(ctx, args, state, block_size, threshold)

    if args.total:
        size_text = _format_size(state.total_bytes, args, block_size)
        if args.time:
            stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(state.newest_mtime))
            _write_line(ctx, args, f"{size_text}\t{stamp}\ttotal")
        else:
            _write_line(ctx, args, f"{size_text}\ttotal")
        printed += 1

    if state.had_error:
        return 2
    if printed == 0:
        # 全被阈值滤掉了，本项目约定「无结果返回 1」（GNU 返回 0）
        return 1
    return 0


# --------------------------------------------------------------------------
# 扫描
# --------------------------------------------------------------------------


def _scan_operand(target: Path, operand: str, args: argparse.Namespace, state: _State) -> None:
    """处理一个操作数：文件直接算，目录递归进去。"""
    follow = _should_follow(args, depth=0)
    try:
        st = target.stat() if follow else target.lstat()
    except OSError as exc:
        state.fail(f"du: 无法访问 '{operand}': {exc.strerror or exc}")
        return

    if stat.S_ISDIR(st.st_mode):
        if not _claim(state, args, st):
            # 同一个目录被多个操作数覆盖：GNU 整个跳过，不输出也不重复统计
            return
        state.root_dev = st.st_dev
        total, own, newest = _scan_dir(target, operand, 0, args, state)
        if newest > state.newest_mtime:
            state.newest_mtime = newest
        state.record(operand, own if args.separate_dirs else total, 0, newest, True)
    else:
        size, counted, mtime = _count_file(target, args, state, st)
        if counted:
            if mtime > state.newest_mtime:
                state.newest_mtime = mtime
            state.record(operand, size, 0, mtime, False)


def _claim(state: _State, args: argparse.Namespace, st: os.stat_result) -> bool:
    """登记一个 inode，返回 True 表示「这是第一次见到」。

    GNU 默认把同一个文件只算一次：多个操作数指向同一个目录、或目录被别的操作数
    覆盖时，后来的那一份既不重复统计也不输出。-l 打开后每次都算。
    """
    key = (st.st_dev, st.st_ino)
    if args.count_links:
        return True
    if key in state.seen:
        return False
    state.seen.add(key)
    return True


def _should_follow(args: argparse.Namespace, depth: int) -> bool:
    """要不要跟随符号链接。

    -L 全部跟随，-H 只跟随命令行上的操作数（也就是第 0 层），-P 不跟随（默认）。
    """
    if args.link_mode == "all":
        return True
    if args.link_mode == "args":
        return depth == 0
    return False


def _scan_dir(
    dir_path: Path,
    display: str,
    depth: int,
    args: argparse.Namespace,
    state: _State,
) -> tuple[int, int, float]:
    """扫描一个目录。

    返回三元组：(含子目录的总字节, 不含子目录的自身文件字节, 最新的修改时间)。
    """
    own_bytes = 0
    total_bytes = 0
    newest = 0.0
    try:
        newest = dir_path.stat().st_mtime
    except OSError:
        pass

    follow = _should_follow(args, depth)
    for name, child_path, child_stat in _list_children(dir_path, display, args, state, follow):
        child_display = _join(display, name)
        if stat.S_ISDIR(child_stat.st_mode):
            if not _claim(state, args, child_stat):
                # 已经算过这个目录（多个操作数覆盖同一棵子树）
                continue
            sub_total, sub_own, sub_newest = _scan_dir(child_path, child_display, depth + 1, args, state)
            total_bytes += sub_total
            newest = max(newest, sub_newest)
            state.record(child_display, sub_own if args.separate_dirs else sub_total, depth + 1, sub_newest, True)
        else:
            size, counted, mtime = _count_file(child_path, args, state, child_stat)
            if not counted:
                continue
            own_bytes += size
            total_bytes += size
            newest = max(newest, mtime)
            if args.all:
                state.record(child_display, size, depth + 1, mtime, False)

    return total_bytes, own_bytes, newest


def _list_children(
    dir_path: Path,
    display: str,
    args: argparse.Namespace,
    state: _State,
    follow: bool,
) -> list[tuple[str, Path, os.stat_result]]:
    """读目录内容：按名字排序，并按 -x 跳过别的文件系统。"""
    try:
        scanner = os.scandir(dir_path)
    except OSError as exc:
        state.fail(f"du: 无法打开目录 '{display}': {exc.strerror or exc}")
        return []

    children: list[tuple[str, Path, os.stat_result]] = []
    with scanner:
        for item in scanner:
            # 不能用 item.stat()：Windows 上它给的是目录枚举的缓存结果，
            # st_dev 与 st_ino 全是 0，硬链接去重与 -x 都会失效
            try:
                st = os.stat(item.path, follow_symlinks=follow)
            except OSError:
                continue
            if args.one_file_system and state.root_dev is not None and st.st_dev != state.root_dev:
                continue
            children.append((item.name, Path(item.path), st))
    # GNU 用的是目录原始顺序，本实现按名字排序，输出才稳定
    children.sort(key=lambda entry: entry[0])
    return children


def _count_file(
    path: Path,
    args: argparse.Namespace,
    state: _State,
    known_stat: os.stat_result | None = None,
) -> tuple[int, bool, float]:
    """统计一个普通文件的字节数。

    返回 (字节数, 是否计入, 修改时间)。默认按 inode 去重——同一个文件被多个操作数
    或多个路径覆盖时只算一次，这与 GNU 一致；-l 打开后重复计入。
    """
    try:
        st = known_stat if known_stat is not None else path.lstat()
    except OSError as exc:
        state.fail(f"du: 无法访问 '{path}': {exc.strerror or exc}")
        return 0, False, 0.0

    if not _claim(state, args, st):
        # 已经算过：既不计入也不打印（GNU 的行为）
        return 0, False, st.st_mtime
    state.total_bytes += st.st_size
    return st.st_size, True, st.st_mtime


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------


def _flush(
    ctx: RunContext,
    args: argparse.Namespace,
    state: _State,
    block_size: int,
    threshold: int,
) -> int:
    """把记录按顺序打印出去，返回打印了多少行。"""
    printed = 0
    for record in state.records:
        if args.summarize and record.depth > 0:
            continue
        if args.max_depth is not None and record.depth > args.max_depth:
            continue
        if not _passes_threshold(record.size, threshold):
            continue
        size_text = _format_size(record.size, args, block_size)
        if args.time:
            stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(record.mtime))
            _write_line(ctx, args, f"{size_text}\t{stamp}\t{record.display}")
        else:
            _write_line(ctx, args, f"{size_text}\t{record.display}")
        printed += 1
    return printed


def _write_line(ctx: RunContext, args: argparse.Namespace, text: str) -> None:
    ctx.stdout.write(text + ("\0" if args.null else "\n"))


def _format_size(size: int, args: argparse.Namespace, block_size: int) -> str:
    """把字节数变成输出里的大小列。"""
    if args.human:
        return _format_human(size, args.human_base == "si")
    return str(_blocks(size, block_size))


def _blocks(size: int, block_size: int) -> int:
    """字节数向上取整到块（GNU 的做法）。"""
    return -(-size // block_size)


def _format_human(size: int, si: bool) -> str:
    """GNU human_readable 的规则。

    1. 选单位：一直除到商不超过 999 为止（按真实商比，不是整除）
    2. 尾数向上取整到一位小数；取整后达到 10 就改成整数显示
    """
    if si:
        base, letters = 1000, _HUMAN_SI
    else:
        base, letters = 1024, _HUMAN_IEC

    if size < base:
        return str(size)

    exponent = 1
    divisor = base
    while size > 999 * divisor:
        exponent += 1
        divisor *= base

    # 尾数放大十倍后向上取整，全程整数运算，避免浮点噪声
    tenths = -((-size * 10) // divisor)
    suffix = letters[exponent - 1]
    if tenths >= 100:
        return f"{-((-tenths) // 10)}{suffix}"
    return f"{tenths // 10}.{tenths % 10}{suffix}"


def _passes_threshold(size: int, threshold: int) -> bool:
    """阈值判定：跟字节数比，不是跟块数比（GNU 实测如此）。

    阈值为正时丢掉小于它的条目，为负时丢掉大于它的条目。
    """
    if threshold == 0:
        return True
    if threshold > 0:
        return size >= threshold
    return size <= -threshold


# --------------------------------------------------------------------------
# 取值解析与路径处理
# --------------------------------------------------------------------------


def _parse_size(text: str, option: str) -> int:
    """按 GNU 的 SIZE 语法解析字节数。

    支持整数与小数，可以带后缀：K/M/G/T/P/E 是 1024 进制，
    KB/MB/GB/TB/PB/EB 是 1000 进制，KiB/MiB/... 也是 1024 进制，B 单独用是 1。
    """
    raw = text.strip()
    body = raw
    sign = 1
    if body.startswith("+"):
        body = body[1:]
    elif body.startswith("-"):
        sign = -1
        body = body[1:]

    index = 0
    while index < len(body) and (body[index].isdigit() or body[index] == "."):
        index += 1
    number_text = body[:index]
    suffix = body[index:].strip().lower()

    if not number_text or number_text == ".":
        raise UsageError(f"选项 '{option}' 的取值无效: '{text}'")
    try:
        number = float(number_text)
    except ValueError:
        raise UsageError(f"选项 '{option}' 的取值无效: '{text}'") from None

    multiplier = _size_multiplier(suffix)
    if multiplier is None:
        raise UsageError(f"选项 '{option}' 的取值无效: '{text}'")
    return sign * int(number * multiplier)


def _size_multiplier(suffix: str) -> int | None:
    """把 SIZE 的后缀翻成倍数，不认识就返回 None。"""
    if suffix in ("", "b"):
        return 1
    if suffix in _SIZE_SUFFIX_1000:
        return _SIZE_SUFFIX_1000[suffix]
    if suffix in _SIZE_SUFFIX_1024:
        return _SIZE_SUFFIX_1024[suffix]
    if suffix.endswith("ib") and suffix[:-2] in _SIZE_SUFFIX_1024:
        return _SIZE_SUFFIX_1024[suffix[:-2]]
    return None


def _resolve_block_size(value) -> int:
    """定下显示用的块大小。"""
    if isinstance(value, int):
        size = value
    else:
        size = _parse_size(value, "-B")
    if size <= 0:
        raise UsageError(f"选项 '-B' 的取值无效: '{value}'")
    return size


def _resolve(cwd: Path, operand: str) -> Path:
    target = Path(operand)
    if not target.is_absolute():
        target = cwd / target
    return target


def _join(display: str, name: str) -> str:
    """把父路径与子名接起来，操作数带尾斜杠时不出现双斜杠。"""
    if display.endswith("/"):
        return display + name
    return f"{display}/{name}"
