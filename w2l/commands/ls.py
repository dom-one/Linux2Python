"""ls：列出目录内容（GNU ls 风格子集）。

对齐 GNU ls 的部分：

- 默认按名字排序（字节序，大写在前），每行一个条目
- -a / -A 隐藏文件，-l 长格式，-t / -S 排序，-r 反序，-F 类型标记，
  -R 递归、-d 列目录本身
- 多个操作数时，普通文件先统一排序输出，目录各自成块并带 "目录:" 标题
- 文件不存在时报错并返回退出码 2，同时仍输出其余可列出的内容

Windows 环境下与 GNU 的必然差异（README 有完整说明）：

- -l 不输出链接数、属主、属组三列：Windows 没有 POSIX 的属主/属组语义
- 不输出 "total N" 汇总行：Windows 的 stat 没有 st_blocks，拿不到 GNU 的块数口径
- 权限位取自 Windows 合成出来的 st_mode，不等价于 POSIX 权限
- 空目录返回退出码 1（GNU 返回 0），遵循本项目「无结果返回 1」的约定
"""

from __future__ import annotations

import argparse
import os
import stat
import time
from pathlib import Path
from typing import NamedTuple

from ..context import RunContext
from ..entry import command_prog
from ..registry import command

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_SIZE_UNITS = ("K", "M", "G", "T", "P")
_RECENT_SECONDS = 180 * 24 * 60 * 60


class _Entry(NamedTuple):
    """一条待输出的目录项，只带排版需要的字段。"""

    name: str
    mode: int
    size: int
    mtime: float


def build_parser() -> argparse.ArgumentParser:
    prog = command_prog("ls")
    # GNU 的 -h 是 --human-readable，不是 --help，所以要关掉 argparse 自带的 -h
    parser = argparse.ArgumentParser(
        prog=prog,
        description="列出目录内容",
        add_help=False,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            f"  {prog}\n"
            f"  {prog} -l w2l\n"
            f"  {prog} -lh tests\n"
            f"  {prog} -a .\n"
            f"  {prog} -R w2l\n"
        ),
    )
    parser.add_argument("--help", action="help", help="显示此帮助信息并退出")
    parser.add_argument("paths", nargs="*", help="要列出的目录或文件，默认当前目录")
    parser.add_argument("-l", "--long", action="store_true", help="长格式：权限、大小、修改时间、名称")
    parser.add_argument("-a", "--all", action="store_true", help="显示所有条目，含 . 与 ..")
    parser.add_argument("-A", "--almost-all", action="store_true", help="显示隐藏条目，但不含 . 与 ..")
    parser.add_argument("-h", "--human-readable", action="store_true", help="以 K/M/G 显示大小")
    parser.add_argument("-d", "--directory", action="store_true", help="列出目录本身而不是它的内容")
    parser.add_argument("-t", "--time", action="store_true", help="按修改时间排序，最新的在前")
    parser.add_argument("-S", "--size", action="store_true", help="按大小排序，最大的在前")
    parser.add_argument("-r", "--reverse", action="store_true", help="反向输出排序结果")
    parser.add_argument("-F", "--classify", action="store_true", help="给名称追加类型标记（/ * @）")
    parser.add_argument("-R", "--recursive", action="store_true", help="递归列出子目录")
    parser.add_argument("-1", "--one-per-line", action="store_true", help="每行一个条目（默认行为，保留兼容）")
    return parser


@command("ls", "列出目录内容（GNU ls 风格子集）", build_parser)
def ls(args: argparse.Namespace, ctx: RunContext) -> int:
    operands = list(args.paths) if args.paths else ["."]
    show_all = args.all
    almost_all = args.almost_all and not args.all

    out = _Output(ctx)
    files: list[_Entry] = []
    directories: list[tuple[str, Path]] = []

    for operand in operands:
        target = _resolve(ctx.cwd, operand)
        try:
            st = target.lstat()
        except OSError as exc:
            ctx.stderr.write(f"ls: 无法访问 '{operand}': {exc.strerror or exc}\n")
            out.had_error = True
            continue
        if stat.S_ISDIR(st.st_mode) and not args.directory:
            directories.append((operand, target))
        else:
            files.append(_Entry(operand, st.st_mode, st.st_size, st.st_mtime))

    # GNU 的顺序：普通文件先统一排序输出，目录随后各自成块
    if files:
        out.block(_format_block(_sort_entries(files, args), args), len(files))

    show_header = len(operands) > 1
    for label, target in directories:
        if args.recursive:
            _list_tree(target, label, args, ctx, out, show_all, almost_all)
        else:
            _list_directory(target, label, args, ctx, out, show_all, almost_all, show_header)

    if out.had_error:
        return 2
    return 0 if out.count else 1


class _Output:
    """收集输出状态：是否已经输出过内容（决定块之间要不要空行）、条目总数、是否出错。"""

    def __init__(self, ctx: RunContext) -> None:
        self.ctx = ctx
        self.started = False
        self.count = 0
        self.had_error = False

    def block(self, lines: list[str], entries: int) -> None:
        """输出一个块；除第一块外，块之间空一行，与 GNU 的分块格式一致。"""
        if not lines:
            return
        if self.started:
            self.ctx.stdout.write("\n")
        for line in lines:
            self.ctx.stdout.write(line + "\n")
        self.started = True
        self.count += entries


def _resolve(cwd: Path, operand: str) -> Path:
    target = Path(operand)
    if not target.is_absolute():
        target = cwd / target
    return target


def _read_entries(root: Path, show_all: bool, almost_all: bool) -> list[_Entry]:
    """读取目录内容；show_all 时额外补上 . 与 .. 两个条目。"""
    entries: list[_Entry] = []
    if show_all:
        entries.append(_Entry(".", *_stat_fields(os.lstat(root))))
        entries.append(_Entry("..", *_stat_fields(os.lstat(root.parent))))
    with os.scandir(root) as scanner:
        for item in scanner:
            if not (show_all or almost_all) and item.name.startswith("."):
                continue
            entries.append(_Entry(item.name, *_stat_fields(item.stat(follow_symlinks=False))))
    return entries


def _stat_fields(st: os.stat_result) -> tuple[int, int, float]:
    return st.st_mode, st.st_size, st.st_mtime


def _sort_entries(entries: list[_Entry], args: argparse.Namespace) -> list[_Entry]:
    """按 -t / -S / 名字排序；同级用名字兜底，最后按 -r 反序。"""
    if args.time:
        ordered = sorted(entries, key=lambda entry: (-entry.mtime, entry.name))
    elif args.size:
        ordered = sorted(entries, key=lambda entry: (-entry.size, entry.name))
    else:
        ordered = sorted(entries, key=lambda entry: entry.name)
    if args.reverse:
        ordered.reverse()
    return ordered


def _list_directory(
    root: Path,
    label: str,
    args: argparse.Namespace,
    ctx: RunContext,
    out: _Output,
    show_all: bool,
    almost_all: bool,
    show_header: bool,
) -> None:
    try:
        entries = _read_entries(root, show_all, almost_all)
    except OSError as exc:
        ctx.stderr.write(f"ls: 无法打开目录 '{label}': {exc.strerror or exc}\n")
        out.had_error = True
        return

    ordered = _sort_entries(entries, args)
    lines = _format_block(ordered, args)
    if show_header:
        lines = [f"{label}:"] + lines
    out.block(lines, len(ordered))


def _list_tree(
    root: Path,
    label: str,
    args: argparse.Namespace,
    ctx: RunContext,
    out: _Output,
    show_all: bool,
    almost_all: bool,
) -> None:
    """递归列出一个目录树，每级目录都是独立的一块，带 "目录:" 标题。"""
    try:
        entries = _read_entries(root, show_all, almost_all)
    except OSError as exc:
        ctx.stderr.write(f"ls: 无法打开目录 '{label}': {exc.strerror or exc}\n")
        out.had_error = True
        return

    ordered = _sort_entries(entries, args)
    out.block([f"{label}:"] + _format_block(ordered, args), len(ordered))

    for entry in ordered:
        if not stat.S_ISDIR(entry.mode):
            continue
        _list_tree(root / entry.name, f"{label}/{entry.name}", args, ctx, out, show_all, almost_all)


def _format_block(entries: list[_Entry], args: argparse.Namespace) -> list[str]:
    """把一组条目排成输出行；长格式下大小列按本组最宽值右对齐。"""
    if not args.long:
        return [_format_name(entry, args) for entry in entries]
    width = max((len(_format_size(entry.size, args.human_readable)) for entry in entries), default=0)
    lines = []
    for entry in entries:
        size = _format_size(entry.size, args.human_readable).rjust(width)
        lines.append(f"{_format_perms(entry)} {size} {_format_time(entry.mtime)} {_format_name(entry, args)}")
    return lines


def _format_name(entry: _Entry, args: argparse.Namespace) -> str:
    if not args.classify:
        return entry.name
    return entry.name + _type_marker(entry)


def _type_marker(entry: _Entry) -> str:
    mode = entry.mode
    if stat.S_ISLNK(mode):
        return "@"
    if stat.S_ISDIR(mode):
        return "/"
    if stat.S_ISFIFO(mode):
        return "|"
    if stat.S_ISSOCK(mode):
        return "="
    if mode & 0o111:
        return "*"
    return ""


def _format_perms(entry: _Entry) -> str:
    mode = entry.mode
    if stat.S_ISLNK(mode):
        kind = "l"
    elif stat.S_ISDIR(mode):
        kind = "d"
    elif stat.S_ISFIFO(mode):
        kind = "p"
    elif stat.S_ISSOCK(mode):
        kind = "s"
    else:
        kind = "-"
    return kind + _perm_bits(mode)


def _perm_bits(mode: int) -> str:
    """把权限位拆成 rwx rwx rwx 三组，逐位判断读、写、执行。"""
    rwx = ""
    for shift in (6, 3, 0):
        bits = (mode >> shift) & 0o7
        rwx += "r" if bits & 0o4 else "-"
        rwx += "w" if bits & 0o2 else "-"
        rwx += "x" if bits & 0o1 else "-"
    return rwx


def _format_size(size: int, human: bool) -> str:
    """human 打开时按 1024 进制缩写，跟 GNU 一样小于 10 保留一位小数。"""
    if not human:
        return str(size)
    if size < 1024:
        return str(size)
    value = float(size)
    index = -1
    while value >= 1024 and index < len(_SIZE_UNITS) - 1:
        value /= 1024
        index += 1
    if value < 10:
        return f"{value:.1f}{_SIZE_UNITS[index]}"
    return f"{value:.0f}{_SIZE_UNITS[index]}"


def _format_time(timestamp: float) -> str:
    """GNU 的时间列：半年以内显示 "Nov  1 02:00"，更早显示 "Nov  1  2025"。"""
    moment = time.localtime(timestamp)
    month = _MONTHS[moment.tm_mon - 1]
    if abs(time.time() - timestamp) <= _RECENT_SECONDS:
        return f"{month} {moment.tm_mday:>2} {moment.tm_hour:02d}:{moment.tm_min:02d}"
    return f"{month} {moment.tm_mday:>2}  {moment.tm_year}"
