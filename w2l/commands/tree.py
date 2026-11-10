"""tree：以树形列出目录内容（GNU tree 风格子集）。

对齐 GNU tree 2.3.x 的部分（依据上游源码 tree.c / list.c / unix.c / color.c）：

- 输出结构：根目录单独一行，下面按深度缩进画树，连接符是「├── 」和「└── 」
- 默认不列隐藏文件（名字以 . 开头），-a 才列；. 与 .. 永远不列
- 默认按名字排序，目录与文件混在一起排；--dirsfirst 才把目录提到前面
- -t 按修改时间排序，旧的在前（与 ls -t 相反）
- 末尾统计行：先空一行，再打 "N directories, M files"（数目为 1 时用单数）
- -L N 限制根目录往下最多 N 层；-I/-P 用通配符筛选
- -F 给名字追加类型标记，-s/-h 打大小，-p 打权限，-D 打修改时间

Windows 环境下的必然差异（README 有完整说明）：

- 画线字符默认用 UTF-8（GNU 在 C 区域设置下默认用 ASCII）
- 目录的大小按 0 算（Windows 的目录 st_size 不稳定，GNU 侧恒为 0）
- 没有属主/属组列（Windows 没有 POSIX 的属主语义）
- 符号链接在 Windows 上要管理员权限才能创建，相关行为没法完整验证
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import time
from pathlib import Path
from typing import NamedTuple

from ..context import RunContext
from ..entry import command_prog
from ..errors import UsageError
from ..registry import command

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
# GNU tree 的 SIXMONTHS：6*31 天
_SIX_MONTHS = 6 * 31 * 24 * 60 * 60
# GNU tree 的 psize 用 IEC 进制（1024）
_SIZE_UNITS = "BKMGTPEZY"

# GNU tree 的画线字符表（对应上游 color.c 的 cstable）。
# vert 是祖先层后面还有兄弟时画的竖线；竖线后面那个空格由 indent() 统一补。
# UTF-8 版的竖线后面跟的是不换行空格（U+00A0），与 GNU 的字节输出一致。
_CHARSETS = {
    "utf8": {
        "vert": "│\u00a0\u00a0",
        "vert_left": "├──",
        "corner": "└──",
        "space": "   ",
    },
    "ascii": {
        "vert": "|  ",
        "vert_left": "|--",
        "corner": "`--",
        "space": "   ",
    },
}

_CHARSET_ALIASES = {
    "utf8": "utf8",
    "utf-8": "utf8",
    "ascii": "ascii",
}


class _Entry(NamedTuple):
    """一条待输出的目录项，只带排版需要的字段。"""

    name: str
    path: Path
    is_dir: bool
    is_link: bool
    mode: int
    size: int
    mtime: float


class _State:
    """一次 tree 运行的状态：统计数、错误标记与根目录所在文件系统。"""

    def __init__(self, ctx: RunContext) -> None:
        self.ctx = ctx
        self.dirs = 0
        self.files = 0
        self.had_error = False
        self.root_dev: int | None = None


def build_parser() -> argparse.ArgumentParser:
    prog = command_prog("tree")
    # GNU 的 -h 是 --human-readable，不是 --help，所以要关掉 argparse 自带的 -h
    parser = argparse.ArgumentParser(
        prog=prog,
        description="以树形列出目录内容",
        add_help=False,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            f"  {prog}\n"
            f"  {prog} w2l\n"
            f"  {prog} -L 2 w2l\n"
            f"  {prog} -d w2l\n"
            f"  {prog} -I '__pycache__' w2l\n"
            f"  {prog} -f --charset=ascii tests\n"
        ),
    )
    parser.add_argument("paths", nargs="*", help="要列出的目录，默认当前目录")
    parser.add_argument("-a", "--all", action="store_true", help="显示隐藏文件")
    parser.add_argument("-d", "--dirs", action="store_true", help="只列目录")
    parser.add_argument("-f", "--fullpath", action="store_true", help="打印完整路径")
    parser.add_argument("-F", "--classify", action="store_true", help="给名字追加类型标记（/ * @）")
    parser.add_argument("-i", "--no-indent", action="store_true", help="不画缩进线")
    parser.add_argument("-l", "--follow-links", action="store_true", help="跟随指向目录的符号链接")
    parser.add_argument("-L", "--level", type=int, help="最多往下显示几层")
    parser.add_argument("-I", "--ignore", action="append", default=[], metavar="PATTERN", help="不列匹配通配符的条目，可重复")
    parser.add_argument("-P", "--pattern", action="append", default=[], metavar="PATTERN", help="只列匹配通配符的文件，可重复")
    parser.add_argument("--ignore-case", action="store_true", help="通配符匹配忽略大小写")
    parser.add_argument("--dirsfirst", action="store_true", help="目录排在文件前面")
    parser.add_argument("--noreport", action="store_true", help="不打末尾的统计行")
    parser.add_argument("--charset", default="utf8", metavar="X", help="画线字符集：utf8（默认）或 ascii")
    parser.add_argument("-p", "--permissions", action="store_true", help="打印权限位")
    parser.add_argument("-s", "--size", action="store_true", help="打印文件大小（字节）")
    parser.add_argument("-h", "--human-readable", action="store_true", help="以 K/M/G 显示大小")
    parser.add_argument("-D", "--date", action="store_true", help="打印最后修改时间")
    parser.add_argument("-t", "--time", action="store_true", help="按修改时间排序，旧的在前")
    parser.add_argument("-r", "--reverse", action="store_true", help="反向输出排序结果")
    parser.add_argument("-U", "--unsorted", action="store_true", help="不排序，按目录顺序输出")
    parser.add_argument("-x", "--one-file-system", action="store_true", help="不跨越文件系统")
    parser.add_argument("--help", action="help", help="显示此帮助信息并退出")
    return parser


@command("tree", "以树形列出目录内容（GNU tree 风格子集）", build_parser)
def tree(args: argparse.Namespace, ctx: RunContext) -> int:
    if args.level is not None and args.level < 1:
        raise UsageError("选项 '-L' 的层数必须大于 0")
    charset = _CHARSET_ALIASES.get(str(args.charset).lower())
    if charset is None:
        raise UsageError(f"未知的字符集 '{args.charset}'（可用：utf8、ascii）")

    operands = list(args.paths) if args.paths else ["."]
    state = _State(ctx)

    for operand in operands:
        target = _resolve(ctx.cwd, operand)
        try:
            st = target.lstat()
        except OSError as exc:
            ctx.stderr.write(f"tree: 无法访问 '{operand}': {exc.strerror or exc}\n")
            state.had_error = True
            continue
        if stat.S_ISLNK(st.st_mode):
            # 指向目录的链接（含 Windows 的目录联接）当目录用，与 GNU 一致
            try:
                st = target.stat()
            except OSError:
                pass
        if not stat.S_ISDIR(st.st_mode):
            ctx.stderr.write(f"tree: '{operand}' 不是目录\n")
            state.had_error = True
            continue
        state.root_dev = st.st_dev
        _emit_tree(target, operand, args, state, charset)

    if not args.noreport:
        ctx.stdout.write("\n" + _format_report(state, args))
    return 2 if state.had_error else 0


# --------------------------------------------------------------------------
# 树的输出
# --------------------------------------------------------------------------


def _emit_tree(root: Path, label: str, args: argparse.Namespace, state: _State, charset: str) -> None:
    """打印一棵目录树：先打根目录那一行，再逐层往下画。"""
    st = root.lstat()
    state.ctx.stdout.write(_format_meta(st, args) + label + "\n")

    # GNU：根目录本身命中 -P 时，它下面的内容全部列出
    pattern_active = not _matches_patterns(args.pattern, _basename(label), label, True, args)
    entries = _read_entries(root, args, label, pattern_active, state)
    if not entries:
        # GNU：根目录里一个条目都没有时，它本身也不计入目录数
        return
    state.dirs += 1
    _list_dir(root, entries, 1, args, state, [], charset, pattern_active, label)


def _list_dir(
    dir_path: Path,
    entries: list[_Entry],
    level: int,
    args: argparse.Namespace,
    state: _State,
    ancestors: list[bool],
    charset: str,
    pattern_active: bool,
    display_path: str,
) -> None:
    """列出一个目录的内容，并按需递归下去。"""
    for index, entry in enumerate(entries):
        is_last = index == len(entries) - 1
        child_path = f"{display_path}/{entry.name}"
        state.ctx.stdout.write(_build_prefix(ancestors, is_last, args, charset))
        state.ctx.stdout.write(_format_entry(entry, child_path, args) + "\n")

        if not entry.is_dir:
            state.files += 1
            continue

        state.dirs += 1
        if not _can_descend(entry, level, args):
            continue

        children = _read_entries(entry.path, args, child_path, pattern_active, state)
        if not children:
            continue
        # 进入的目录本身命中 -P 时，它下面的内容全部列出（GNU 的做法）
        child_active = pattern_active and not _matches_patterns(
            args.pattern, entry.name, child_path, True, args
        )
        _list_dir(
            entry.path,
            children,
            level + 1,
            args,
            state,
            ancestors + [not is_last],
            charset,
            child_active,
            child_path,
        )


def _can_descend(entry: _Entry, level: int, args: argparse.Namespace) -> bool:
    """这个目录要不要往下走。"""
    if args.level is not None and level >= args.level:
        return False
    if entry.is_link and not args.follow_links:
        return False
    return True


def _build_prefix(ancestors: list[bool], is_last: bool, args: argparse.Namespace, charset: str) -> str:
    """按 GNU 的 indent() 规则拼出缩进前缀。

    ancestors 里每个值表示「那一层后面还有没有兄弟」：有就画竖线，没有就画空格；
    最后再画当前条目自己的连接符（最后一个兄弟用 └── ，其余用 ├── ）。
    """
    if args.no_indent:
        return ""
    glyphs = _CHARSETS[charset]
    parts = []
    for has_more in ancestors:
        parts.append(glyphs["vert"] if has_more else glyphs["space"])
    parts.append(glyphs["corner"] if is_last else glyphs["vert_left"])
    return "".join(part + " " for part in parts)


def _format_entry(entry: _Entry, child_path: str, args: argparse.Namespace) -> str:
    """拼出单条目的显示文本：元信息 + 名字（符号链接带上目标）+ 类型标记。

    -f 打开时名字换成完整路径，路径是「根目录的操作数 + / + 逐级名字」，
    所以操作数是 "." 时条目显示成 "./子目录/文件"。
    """
    meta = _format_meta(entry.path.lstat(), args)
    name = child_path if args.fullpath else entry.name
    if entry.is_link:
        target = _read_link(entry.path)
        if target is not None:
            name = f"{name} -> {target}"
    if args.classify:
        name += _type_marker(entry)
    return meta + name


def _format_meta(st: os.stat_result, args: argparse.Namespace) -> str:
    """按 GNU fillinfo() 的顺序拼元信息：权限、大小、时间。"""
    parts = []
    if args.permissions:
        parts.append(" " + _format_perms(st))
    # GNU 的 -h 隐含 -s（源码里写着 "Assume they also want -s"）
    if args.size or args.human_readable:
        parts.append(_format_size(st, args.human_readable))
    if args.date:
        parts.append(" " + _format_time(st.st_mtime))
    return "".join(parts)


def _format_perms(st: os.stat_result) -> str:
    """权限列：类型字符加 rwx rwx rwx，与 ls -l 同一套口径。"""
    mode = st.st_mode
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
    rwx = ""
    for shift in (6, 3, 0):
        bits = (mode >> shift) & 0o7
        rwx += "r" if bits & 0o4 else "-"
        rwx += "w" if bits & 0o2 else "-"
        rwx += "x" if bits & 0o1 else "-"
    return kind + rwx


def _format_size(st: os.stat_result, human: bool) -> str:
    """大小列：GNU 的 psize()，字节时右对齐 11 列，人-readable 时带单位。"""
    size = st.st_size
    if stat.S_ISDIR(st.st_mode):
        # Windows 的目录 st_size 会在 0 与 4096 之间跳，统一按 0 算
        size = 0
    if not human:
        return f" {size:>11d}"
    if size < 1024:
        return f" {size:>4d}"
    value = size
    index = 1
    while value >= 1024 * 1024 and index < len(_SIZE_UNITS) - 1:
        value //= 1024
        index += 1
    number = value / 1024
    if (value + 52) // 1024 >= 10:
        return f" {number:.0f}{_SIZE_UNITS[index]}"
    return f" {number:.1f}{_SIZE_UNITS[index]}"


def _format_time(timestamp: float) -> str:
    """GNU 的 do_date()：半年以内显示 "Nov 11 02:00"，更早显示 "Nov 11  2025"。"""
    moment = time.localtime(timestamp)
    month = _MONTHS[moment.tm_mon - 1]
    now = time.time()
    if timestamp > now or (timestamp + _SIX_MONTHS) < now:
        return f"{month} {moment.tm_mday:>2}  {moment.tm_year}"
    return f"{month} {moment.tm_mday:>2} {moment.tm_hour:02d}:{moment.tm_min:02d}"


def _type_marker(entry: _Entry) -> str:
    """-F 的类型标记，与 ls -F 同一套口径。"""
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


def _format_report(state: _State, args: argparse.Namespace) -> str:
    """末尾的统计行：GNU 的单复数写法。"""
    dirs = state.dirs
    files = state.files
    if args.dirs:
        return f"{dirs} director{'y' if dirs == 1 else 'ies'}\n"
    return (
        f"{dirs} director{'y' if dirs == 1 else 'ies'}, "
        f"{files} file{'' if files == 1 else 's'}\n"
    )


# --------------------------------------------------------------------------
# 目录读取与筛选
# --------------------------------------------------------------------------


def _read_entries(
    dir_path: Path,
    args: argparse.Namespace,
    display_path: str,
    pattern_active: bool,
    state: _State,
) -> list[_Entry]:
    """读一个目录的内容，按 -a/-d/-x/-I/-P 过滤后排序。"""
    try:
        scanner = os.scandir(dir_path)
    except OSError as exc:
        state.ctx.stderr.write(f"tree: 无法打开目录 '{display_path}': {exc.strerror or exc}\n")
        state.had_error = True
        return []

    entries: list[_Entry] = []
    with scanner:
        for item in scanner:
            name = item.name
            if not args.all and name.startswith("."):
                continue
            try:
                st = item.stat(follow_symlinks=False)
            except OSError:
                continue
            is_link = stat.S_ISLNK(st.st_mode)
            is_dir = stat.S_ISDIR(st.st_mode)
            if is_link and args.follow_links:
                # -l：指向目录的链接按目录算（GNU 用 stat 而不是 lstat 判定）
                try:
                    is_dir = stat.S_ISDIR(item.stat(follow_symlinks=True).st_mode)
                except OSError:
                    is_dir = False
            if args.dirs and not is_dir:
                continue
            if args.one_file_system and state.root_dev is not None and st.st_dev != state.root_dev:
                continue
            child_path = f"{display_path}/{name}"
            if _matches_patterns(args.ignore, name, child_path, is_dir, args):
                continue
            if (
                pattern_active
                and args.pattern
                and not is_dir
                and not _matches_patterns(args.pattern, name, child_path, is_dir, args)
            ):
                continue
            entries.append(
                _Entry(
                    name=name,
                    path=Path(item.path),
                    is_dir=is_dir,
                    is_link=is_link,
                    mode=st.st_mode,
                    size=st.st_size,
                    mtime=st.st_mtime,
                )
            )
    return _sort_entries(entries, args)


def _sort_entries(entries: list[_Entry], args: argparse.Namespace) -> list[_Entry]:
    """排序：默认按名字，-t 按修改时间（旧的在前），--dirsfirst 把目录提前，-r 反向。"""
    if args.unsorted:
        return entries
    if args.time:
        ordered = sorted(entries, key=lambda entry: (entry.mtime, entry.name))
    else:
        ordered = sorted(entries, key=lambda entry: entry.name)
    if args.dirsfirst:
        dirs = [entry for entry in ordered if entry.is_dir]
        files = [entry for entry in ordered if not entry.is_dir]
        ordered = dirs + files
    if args.reverse:
        ordered = list(reversed(ordered))
    return ordered


def _resolve(cwd: Path, operand: str) -> Path:
    target = Path(operand)
    if not target.is_absolute():
        target = cwd / target
    return target


def _basename(path: str) -> str:
    """取路径最后一段；没有分隔符时整串就是名字。"""
    cleaned = path.rstrip("/")
    if not cleaned:
        return path
    return cleaned.rsplit("/", 1)[-1]


def _read_link(path: Path) -> str | None:
    try:
        return os.readlink(path)
    except OSError:
        return None


# --------------------------------------------------------------------------
# 通配符匹配（GNU tree 的 patmatch 语义）
# --------------------------------------------------------------------------


def _matches_patterns(
    patterns: list[str],
    name: str,
    path: str,
    is_dir: bool,
    args: argparse.Namespace,
) -> bool:
    """条目名、完整路径、或路径的任意后缀命中任一模式就算命中。"""
    if not patterns:
        return False
    candidates = [name, path]
    parts = path.split("/")
    for index in range(1, len(parts)):
        candidates.append("/".join(parts[index:]))
    for pattern in patterns:
        for candidate in candidates:
            if _match_pattern(candidate, pattern, is_dir, args.ignore_case):
                return True
    return False


def _match_pattern(text: str, pattern: str, is_dir: bool, ignore_case: bool) -> bool:
    """GNU 的 patmatch：模式里 '|' 分隔候选，任一命中即可。"""
    for alternative in pattern.split("|"):
        if not alternative:
            continue
        dir_only = alternative.endswith("/")
        if dir_only:
            alternative = alternative[:-1]
        if not alternative:
            continue
        regex = _compile_pattern(alternative, ignore_case)
        if regex.fullmatch(text) and (not dir_only or is_dir):
            return True
    return False


def _compile_pattern(pattern: str, ignore_case: bool) -> re.Pattern:
    """把 GNU 的通配符翻译成正则。

    '*' 不跨 '/'，'**' 跨 '/'，'?' 匹配任意一个字符，'[...]' 是字符类（'^' 取反）。
    """
    out: list[str] = []
    index = 0
    length = len(pattern)
    while index < length:
        char = pattern[index]
        if char == "*":
            if index + 1 < length and pattern[index + 1] == "*":
                out.append(".*")
                index += 2
            else:
                out.append("[^/]*")
                index += 1
            continue
        if char == "?":
            out.append(".")
            index += 1
            continue
        if char == "[":
            closing = _find_class_end(pattern, index)
            if closing is None:
                out.append(re.escape("["))
                index += 1
                continue
            out.append(_translate_class(pattern[index + 1 : closing]))
            index = closing + 1
            continue
        out.append(re.escape(char))
        index += 1
    flags = re.IGNORECASE if ignore_case else 0
    return re.compile("".join(out), flags)


def _find_class_end(pattern: str, start: int) -> int | None:
    """找字符类的右括号位置；没闭合就返回 None。"""
    index = start + 1
    length = len(pattern)
    if index < length and pattern[index] in "^!":
        index += 1
    if index < length and pattern[index] == "]":
        index += 1
    while index < length and pattern[index] != "]":
        if pattern[index] == "\\":
            index += 1
        index += 1
    return index if index < length else None


def _translate_class(body: str) -> str:
    """把字符类内容翻译成正则里的类体。"""
    negate = ""
    if body[:1] in ("^", "!"):
        negate = "^"
        body = body[1:]
    chars: list[str] = []
    index = 0
    length = len(body)
    while index < length:
        char = body[index]
        if char == "\\" and index + 1 < length:
            index += 1
            chars.append(re.escape(body[index]))
        elif char == "-" and chars and index + 1 < length:
            chars.append("-")
        else:
            chars.append(re.escape(char))
        index += 1
    return "[" + negate + "".join(chars) + "]"
