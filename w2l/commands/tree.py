"""tree：以树形列出目录内容（GNU tree 风格子集）。

对齐 GNU tree 2.3.x 的部分（依据上游源码 tree.c / list.c / unix.c / color.c）：

- 输出结构：根目录单独一行，下面按深度缩进画树，连接符是「├── 」和「└── 」
- 默认不列隐藏文件（名字以 . 开头），-a 才列；. 与 .. 永远不列
- 默认按名字排序，目录与文件混在一起排；--dirsfirst 才把目录提到前面
- -t 按修改时间排序，旧的在前（与 ls -t 相反）
- 末尾统计行：先空一行，再打 "N directories, M files"（数目为 1 时用单数）
- -L N 限制根目录往下最多 N 层；-I/-P 用通配符筛选
- -F 给名字追加类型标记，-s/-h 打大小，-p 打权限，-D 打修改时间
- -x 只在「不往下走」这一层生效：跨设备的目录照样打印、照样计入目录数
  （上游 list.c 的 tot.dirs++ 排在 xdev 判断之前）
- 链接默认不展开（上游 list.c 的 !(*dir)->lnk || ((*dir)->lnk && lflag)），
  -l 才跟随；跟随时目标已经访问过就停在那一层，报 "recursive, not followed"

Windows 环境下的必然差异（README 有完整说明）：

- 画线字符默认用 UTF-8（GNU 在 C 区域设置下默认用 ASCII）
- 目录的大小按 0 算（Windows 的目录 st_size 不稳定，GNU 侧恒为 0）
- 没有属主/属组列（Windows 没有 POSIX 的属主语义）
- 符号链接在 Windows 上要管理员权限才能创建，相关行为没法完整验证；
  但目录联接（junction）不需要权限，Python 的 lstat 认不出它是链接，
  所以这里按 st_reparse_tag 判定，把联接当链接处理（与 MSYS 的 ls 一致）
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
from ..perms import canonical_mode, format_perms
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
    """一条待输出的目录项，只带排版需要的字段。

    dev/ino 跟上游 tree 的 ent->dev/ent->inode 一个口径：链接取「跟随后」
    目标的那个身份，普通条目取 lstat 的（上游 getinfo() 就是这么分的）。
    mode/size/mtime 一律取 lstat 的值，跟上游 ent->mode/ent->size/ent->mtime 对齐。
    """

    name: str
    path: Path
    is_dir: bool
    is_link: bool
    mode: int
    size: int
    mtime: float
    dev: int
    ino: int
    link_target: str | None


class _State:
    """一次 tree 运行的状态：统计数、错误标记与根目录所在文件系统。"""

    def __init__(self, ctx: RunContext) -> None:
        self.ctx = ctx
        self.dirs = 0
        self.files = 0
        self.had_error = False
        self.root_dev: int | None = None
        # 已经走过的目录（dev, ino），用来发现跟随链接时的递归
        self.visited: set[tuple[int, int]] = set()


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
            lst = target.lstat()
        except OSError as exc:
            ctx.stderr.write(f"tree: 无法访问 '{operand}': {exc.strerror or exc}\n")
            state.had_error = True
            continue
        if _is_link(lst):
            # 指向目录的链接（含 Windows 的目录联接）当目录用，与 GNU 一致
            try:
                st = target.stat()
            except OSError:
                st = lst
        else:
            st = lst
        if not stat.S_ISDIR(st.st_mode):
            ctx.stderr.write(f"tree: '{operand}' 不是目录\n")
            state.had_error = True
            continue
        # -x 的基准是根目录自己所在的卷（上游用的是 lstat 的 st_dev）
        state.root_dev = lst.st_dev
        _emit_tree(target, operand, lst, args, state, charset)

    if not args.noreport:
        ctx.stdout.write("\n" + _format_report(state, args))
    return 2 if state.had_error else 0


# --------------------------------------------------------------------------
# 树的输出
# --------------------------------------------------------------------------


def _emit_tree(
    root: Path,
    label: str,
    root_stat: os.stat_result,
    args: argparse.Namespace,
    state: _State,
    charset: str,
) -> None:
    """打印一棵目录树：先打根目录那一行，再逐层往下画。"""
    state.ctx.stdout.write(
        _format_meta(root_stat.st_mode, root_stat.st_size, root_stat.st_mtime, args) + label + "\n"
    )

    # 根目录自己先记进已访问集合：跟随链接时靠它挡住指向根的环
    state.visited.add((root_stat.st_dev, root_stat.st_ino))

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
        prefix = _build_prefix(ancestors, is_last, args, charset)

        if not entry.is_dir:
            state.files += 1
            state.ctx.stdout.write(prefix + _format_entry(entry, child_path, args) + "\n")
            continue

        state.dirs += 1
        descend, note = _plan_descend(entry, level, args, state)
        state.ctx.stdout.write(prefix + _format_entry(entry, child_path, args) + note + "\n")
        if not descend:
            continue

        # 进入的目录本身命中 -P 时，它下面的内容全部列出（GNU 的做法）。
        # 顺序很关键：先算出 child_active，再用它去读 children，
        # 反过来的话命中目录的直接子文件会被父层的模式筛掉。
        child_active = pattern_active and not _matches_patterns(
            args.pattern, entry.name, child_path, True, args
        )
        children = _read_entries(entry.path, args, child_path, child_active, state)
        if not children:
            continue
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


def _plan_descend(entry: _Entry, level: int, args: argparse.Namespace, state: _State) -> tuple[bool, str]:
    """这个目录要不要往下走，以及这一行末尾要补什么提示。

    返回的提示是上游的 "recursive, not followed"：跟随链接时目标已经访问过，
    就停在这一层不再往下走（上游 list.c 的同名报错）。
    """
    # 上游先把目录的身份记进已访问集合，再判断要不要展开
    key = (entry.dev, entry.ino)
    found = key in state.visited
    if not found:
        state.visited.add(key)

    if args.level is not None and level >= args.level:
        return False, ""
    # -x：跨设备的目录照样打印、照样计入目录数，只是不往下展开
    # （上游 list.c 的 tot.dirs++ 在 xdev 判断之前）
    if args.one_file_system and state.root_dev is not None and entry.dev != state.root_dev:
        return False, ""
    # 链接默认不展开（上游：!(*dir)->lnk || ((*dir)->lnk && lflag)）
    if entry.is_link and not args.follow_links:
        return False, ""
    if entry.is_link and found:
        return False, "  [recursive, not followed]"
    return True, ""


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
    """拼出单条目的显示文本：元信息 + 名字（链接带上目标）+ 类型标记。

    -f 打开时名字换成完整路径，路径是「根目录的操作数 + / + 逐级名字」，
    所以操作数是 "." 时条目显示成 "./子目录/文件"。
    """
    meta = _format_meta(entry.mode, entry.size, entry.mtime, args)
    name = child_path if args.fullpath else entry.name
    if entry.is_link and entry.link_target is not None:
        name = f"{name} -> {entry.link_target}"
    if args.classify:
        name += _type_marker(entry)
    return meta + name


def _format_meta(mode: int, size: int, mtime: float, args: argparse.Namespace) -> str:
    """按 GNU fillinfo() 的顺序拼元信息：权限、大小、时间。

    取的都是 lstat 的值（上游 ent->mode/ent->size/ent->mtime 同源）。
    """
    parts = []
    if args.permissions:
        parts.append(" " + format_perms(mode))
    # GNU 的 -h 隐含 -s（源码里写着 "Assume they also want -s"）
    if args.size or args.human_readable:
        parts.append(_format_size(mode, size, args.human_readable))
    if args.date:
        parts.append(" " + _format_time(mtime))
    return "".join(parts)


def _format_perms(mode: int) -> str:
    """权限列：类型字符加 rwx rwx rwx，与 ls -l 同一套口径。"""
    return format_perms(mode)


def _format_size(mode: int, size: int, human: bool) -> str:
    """大小列：GNU 的 psize()，字节时右对齐 11 列，人-readable 时带单位。"""
    if stat.S_ISDIR(mode):
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
    if canonical_mode(mode) & 0o111:
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
    """读一个目录的内容，按 -a/-d/-I/-P 过滤后排序。

    -x 不在这里筛条目：上游的跨设备判断只管「要不要往下走」，跨设备的目录
    照样打印、照样计入目录数（上游 list.c 的 tot.dirs++ 在 xdev 判断之前）。

    取 st_dev / st_ino 必须用 os.stat()：Windows 上 os.scandir() 给的
    DirEntry.stat() 是目录枚举缓存，st_dev 与 st_ino 全是 0，拿它比永远
    不相等，整棵树会被过滤光（du.py 早就踩过这个坑）。
    """
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
                lst = os.stat(item.path, follow_symlinks=False)
            except OSError:
                continue

            is_link = _is_link(lst)
            is_dir = stat.S_ISDIR(lst.st_mode)
            dev, ino = lst.st_dev, lst.st_ino
            link_target = None
            if is_link:
                # 上游 getinfo()：链接走 stat() 取目标，ent->dev/ent->inode
                # 用的是「跟随后」目标的身份；stat 失败就是悬空链接，
                # 按不是目录处理（上游把它的 isdir 置成 FALSE）
                try:
                    target = os.stat(item.path)
                except OSError:
                    target = None
                if target is not None:
                    is_dir = stat.S_ISDIR(target.st_mode)
                    dev, ino = target.st_dev, target.st_ino
                else:
                    is_dir = False
                link_target = _read_link(Path(item.path))

            if args.dirs and not is_dir:
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
                    mode=lst.st_mode,
                    size=lst.st_size,
                    mtime=lst.st_mtime,
                    dev=dev,
                    ino=ino,
                    link_target=link_target,
                )
            )
    return _sort_entries(entries, args)


def _is_link(st: os.stat_result) -> bool:
    """这个目录项是不是链接。

    符号链接看 S_ISLNK 就够了；但 Windows 的目录联接（junction）lstat 出来
    是个普通目录（S_ISLNK 为假、S_ISDIR 为真），只能靠重分析点标记认出来——
    实测 st_reparse_tag 等于 stat.IO_REPARSE_TAG_MOUNT_POINT 就是联接。
    MSYS 的 ls -l 把联接显示成 "lrwxrwxrwx ... -> 目标"，也是当链接看的。
    """
    if stat.S_ISLNK(st.st_mode):
        return True
    tag = getattr(st, "st_reparse_tag", None)
    mount = getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", None)
    return tag is not None and mount is not None and tag == mount


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
    """读链接目标；读不出来（不是链接）就返回 None。

    Windows 的目录联接读出来带 "\\\\?\\" 前缀（扩展长度路径），
    那是内核层面的写法，对读者没意义，显示时去掉；
    UNC 的 "\\?\\UNC\\server\\share" 要还原成 "\\\\server\\share"。
    """
    try:
        target = os.readlink(path)
    except OSError:
        return None
    if target.startswith("\\\\?\\UNC\\"):
        return "\\\\" + target[len("\\\\?\\UNC\\") :]
    if target.startswith("\\\\?\\"):
        return target[len("\\\\?\\") :]
    return target


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
