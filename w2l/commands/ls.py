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
- 权限位按 MSYS 的口径折算（可写文件 0644、只读文件 0444、目录 0755、
  可执行文件 0755），与 GNU 的 ls -l 一致；Windows 合成出来的 st_mode 是
  0666/0777/0444，直接用会把组位与执行位显示错
- 空目录返回退出码 1（GNU 返回 0），遵循本项目「无结果返回 1」的约定

--json 是本项目的扩展选项（GNU ls 没有）：

- 输出 {"command": "ls", "entries": [...]}，每个条目带 name / path / type /
  size / mtime / mode / permissions 七个字段
- 错误照旧走 stderr，所以 stdout 永远是合法 JSON
"""

from __future__ import annotations

import argparse
import os
import stat
import time
from pathlib import Path
from typing import NamedTuple

from .. import jsonout
from ..context import RunContext
from ..entry import command_prog
from ..perms import canonical_mode, format_perms, mode_octal
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
            f"  {prog} --json w2l\n"
        ),
    )
    parser.add_argument("--help", action="help", help="显示此帮助信息并退出")
    parser.add_argument("paths", nargs="*", help="要列出的目录或文件，默认当前目录")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果（机器可读）")
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

    out = _Output(ctx, json_mode=args.json)
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
        ordered = _sort_entries(files, args)
        # 文件操作数本身就是一个路径，它自己就是条目的路径（不拼父目录）
        out.block(_format_block(ordered, args), ordered, _records(ordered, None))

    show_header = len(operands) > 1
    for label, target in directories:
        if args.recursive:
            _list_tree(target, label, args, ctx, out, show_all, almost_all)
        else:
            _list_directory(target, label, args, ctx, out, show_all, almost_all, show_header)

    if args.json:
        jsonout.write(ctx, {"command": "ls", "entries": out.records})

    if out.had_error:
        return 2
    return 0 if out.count else 1


class _Output:
    """收集输出状态：是否已经输出过内容（决定块之间要不要空行）、条目总数、是否出错。

    JSON 模式不写文本，只把结构化记录攒起来，最后一次性输出。
    """

    def __init__(self, ctx: RunContext, json_mode: bool = False) -> None:
        self.ctx = ctx
        self.json_mode = json_mode
        self.started = False
        self.count = 0
        self.had_error = False
        self.records: list[dict] = []

    def block(
        self,
        lines: list[str],
        entries: list[_Entry],
        records: list[dict] | None = None,
    ) -> None:
        """输出一个块；除第一块外，块之间空一行，与 GNU 的分块格式一致。"""
        if not lines:
            return
        if self.json_mode:
            self.records.extend(records or [])
            self.count += len(entries)
            return
        if self.started:
            self.ctx.stdout.write("\n")
        for line in lines:
            self.ctx.stdout.write(line + "\n")
        self.started = True
        self.count += len(entries)


def _records(entries: list[_Entry], parent: str | None) -> list[dict]:
    """把条目转成 JSON 记录。

    parent 为 None 表示条目本身就是命令行给的操作数（路径就是它自己）；
    否则 parent 是所在目录的操作数路径，拼在名字前面。
    """
    records = []
    for entry in entries:
        if parent is None:
            path = entry.name.replace("\\", "/")
            name = _basename(entry.name)
        else:
            path = _entry_path(parent, entry.name)
            name = entry.name
        records.append(_json_record(entry, name, path))
    return records


def _basename(path: str) -> str:
    """取路径的最后一段（正斜杠与反斜杠都算分隔符）。"""
    normalized = path.replace("\\", "/").rstrip("/")
    if not normalized:
        return path
    return normalized.rsplit("/", 1)[-1]


def _entry_path(parent: str | None, name: str) -> str:
    """拼出条目在 JSON 里的路径。

    路径统一用正斜杠：Windows 上给的是反斜杠，转成正斜杠后同一份 JSON
    在 Windows 与 Linux 上长得一样，消费方不用分支处理分隔符。
    """
    if parent is None:
        return name.replace("\\", "/")
    base = parent.replace("\\", "/")
    if not base.endswith("/"):
        base += "/"
    if name == ".":
        # "." 这个条目指向所在目录本身，不是它的子项
        return base[:-1] if len(base) > 1 else base
    return base + name


def _json_record(entry: _Entry, name: str, path: str) -> dict:
    """一条条目的 JSON 记录。

    字段口径：
    - name   条目名（永远是路径的最后一段，不含路径）
    - path   条目路径，父目录 + 名字（正斜杠）
    - type   类型名（file / directory / symlink ...）
    - size   字节数（原始整数，不受 -h 影响）
    - mtime  修改时间，Unix 时间戳（浮点，带亚秒）
    - mode   权限位的四位八进制写法，按 MSYS 口径折算
    - permissions 权限列的符号写法（-rw-r--r--）
    """
    return {
        "name": name,
        "path": path,
        "type": jsonout.type_name(entry.mode),
        "size": entry.size,
        "mtime": entry.mtime,
        "mode": mode_octal(canonical_mode(entry.mode)),
        "permissions": format_perms(entry.mode),
    }


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
    out.block(lines, ordered, _records(ordered, label))


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
    out.block(
        [f"{label}:"] + _format_block(ordered, args),
        ordered,
        _records(ordered, label),
    )

    for entry in ordered:
        if not stat.S_ISDIR(entry.mode):
            continue
        # -a 会把 . 与 .. 也列进条目里，但它们不是子目录：
        # . 递归回自己、.. 递归到上一级，两条都停不下来（GNU 也不往里递归）
        if entry.name in (".", ".."):
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
    if canonical_mode(mode) & 0o111:
        return "*"
    return ""


def _format_perms(entry: _Entry) -> str:
    return format_perms(entry.mode)


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
