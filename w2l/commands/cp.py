"""cp：复制文件或目录（GNU cp 风格子集）。

复制按字节进行，不做编码转换：二进制文件原样落地，GBK 文本也不会被改写。
行为对齐 GNU coreutils 8.32 的 cp（全部经 Git Bash 的 /usr/bin/cp 实跑对照）。

退出码遵循本项目约定：0 成功，2 用法或运行错误（GNU 用 1）。
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import NamedTuple

from ..context import RunContext
from ..entry import command_prog
from ..errors import UsageError
from ..flags import FlagTracker, resolve_exclusive
from ..registry import command

_PRESERVE_MODES = ("mode", "timestamps", "ownership", "links", "context", "xattr", "all")
_CHUNK = 1024 * 1024


class _CpParser(argparse.ArgumentParser):
    """cp 的命令行有一处要改写后才交给 argparse。

    GNU 的 --preserve 是 getopt 的「可选参数」长选项：值必须用等号附在后面
    （--preserve=mode），裸写 --preserve 等于 --preserve=all，而且
    **不吃后面的操作数**（GNU 实测：`cp --preserve a.txt b.txt` 里 a.txt
    是源、b.txt 是目标）。argparse 的 nargs="?" 会把后面的操作数当成值
    吃掉，所以在解析前把裸写的 --preserve 改写成 --preserve=all。
    """

    def parse_known_args(self, args=None, namespace=None):  # type: ignore[override]
        argv = list(sys.argv[1:] if args is None else args)
        return super().parse_known_args(_rewrite_preserve(argv), namespace)


def _rewrite_preserve(argv: list[str]) -> list[str]:
    """把裸写的 --preserve 改成 --preserve=all（GNU 的可选参数只认等号写法）。

    遇到裸的 -- 就停下：GNU 的 getopt 到 -- 为止不再解析选项，
    之后的 --preserve 是文件名而不是选项。
    """
    out: list[str] = []
    for item in argv:
        if item == "--":
            out.append(item)
            out.extend(argv[len(out):])
            return out
        out.append("--preserve=all" if item == "--preserve" else item)
    return out


def build_parser() -> argparse.ArgumentParser:
    prog = command_prog("cp")
    parser = _CpParser(
        prog=prog,
        description="复制文件或目录",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            f"  {prog} w2l/registry.py w2l/registry.py.bak\n"
            f"  {prog} -r w2l/commands backup/\n"
            f"  {prog} -v -p README.md docs/README.md\n"
            f"  {prog} -n --parents w2l/cli.py backup/\n"
            f"  {prog} -t build/ w2l/registry.py w2l/context.py\n"
        ),
    )
    parser.add_argument("operands", nargs="*", metavar="SOURCE... DEST", help="源（可多个）与目标")
    parser.add_argument("-r", "-R", "--recursive", action="store_true", help="递归复制目录")
    parser.add_argument("-a", "--archive", action="store_true", help="归档模式：递归 + 保留属性 + 不解引用符号链接")
    parser.add_argument("-p", action="store_true", help="保留权限与时间戳")
    parser.add_argument(
        "--preserve",
        action="append",
        default=None,
        metavar="MODE_LIST",
        help="保留指定属性，可选 mode/timestamps/ownership/links/context/xattr/all；裸写等于 all",
    )
    parser.add_argument(
        "--no-preserve",
        action="append",
        default=None,
        metavar="MODE_LIST",
        help="不保留指定属性，可重复给",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action=FlagTracker,
        dest="interactive",
        default=False,
        help="覆盖已存在的文件前询问",
    )
    parser.add_argument("-f", "--force", action="store_true", help="强制覆盖（先去掉目标的只读属性）")
    parser.add_argument(
        "-n",
        "--no-clobber",
        action=FlagTracker,
        dest="no_clobber",
        default=False,
        help="不覆盖已存在的文件",
    )
    parser.add_argument("-u", "--update", action="store_true", help="仅当源比目标新时才复制")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示每个被复制的条目")
    parser.add_argument("-t", "--target-directory", default=None, metavar="DIR", help="把目标目录写死")
    parser.add_argument("-T", "--no-target-directory", action="store_true", help="把目标当普通文件，不当目录")
    parser.add_argument("-S", "--suffix", default=None, metavar="SUFFIX", help="覆盖前把旧目标改名加上该后缀")
    parser.add_argument("--parents", action="store_true", help="在目标下保留源的路径层级")
    parser.add_argument("--remove-destination", action="store_true", help="复制前先删除目标")
    return parser


@command("cp", "复制文件或目录（GNU cp 风格子集）", build_parser)
def cp(args: argparse.Namespace, ctx: RunContext) -> int:
    try:
        state = _State(args, ctx)
        plan = state.plan()
    except UsageError as exc:
        ctx.stderr.write(f"cp: {exc}\n")
        return 2
    if plan is None:
        return 2

    for source in plan.sources:
        state.copy_source(source, plan)
    return 2 if state.had_error else 0


class _State:
    """一次 cp 调用的全部状态与动作。"""

    def __init__(self, args: argparse.Namespace, ctx: RunContext) -> None:
        self.args = args
        self.ctx = ctx
        self.had_error = False

        self.archive = args.archive
        self.recursive = args.recursive or args.archive
        self.no_dereference = args.archive
        self.verbose = args.verbose
        self.suffix = args.suffix
        self.parents = args.parents
        self.remove_destination = args.remove_destination
        self.update = args.update
        self.force = args.force
        # GNU 里 -i 与 -n 互相清掉对方，后给的那个赢（共享判据见 w2l/flags.py）。
        policy = resolve_exclusive(
            getattr(args, "option_order", None) or [],
            {"interactive": bool(args.interactive), "no_clobber": bool(args.no_clobber)},
        )
        self.interactive = policy["interactive"]
        self.no_clobber = policy["no_clobber"]
        self.preserve = self._resolve_preserve()

    # ---------- 选项归并 ----------

    def _resolve_preserve(self) -> set[str]:
        """--preserve 给多次时是并集（GNU 实测），--no-preserve 从并集里减。"""
        modes: set[str] = set()
        if self.args.p:
            modes |= {"mode", "timestamps"}
        if self.archive:
            modes |= {"mode", "timestamps", "links"}
        for item in self.args.preserve or []:
            modes |= self._parse_modes(item, "--preserve")
        for item in self.args.no_preserve or []:
            modes -= self._parse_modes(item, "--no-preserve")
        return modes

    @staticmethod
    def _parse_modes(text: str, flag: str) -> set[str]:
        wanted: set[str] = set()
        for piece in text.split(","):
            name = piece.strip()
            if not name:
                continue
            if name not in _PRESERVE_MODES:
                raise UsageError(
                    f"{flag} 的无效取值 '{name}'，可选：{', '.join(_PRESERVE_MODES)}"
                )
            wanted.add(name)
        if "all" in wanted:
            return set(_PRESERVE_MODES)
        return wanted

    # ---------- 操作数规划 ----------

    def plan(self) -> "_Plan | None":
        """拆出源列表与目标。返回 None 表示规划阶段已经报错。"""
        # 选项之间的冲突先查：GNU 在动任何文件之前就报（缺操作数都不算数）。
        if self.suffix is not None and self.no_clobber:
            self.error("选项 --backup 与 --no-clobber 不能同时使用")
            return None

        operands = list(self.args.operands)
        target_dir = self.args.target_directory

        if self.args.no_target_directory:
            if len(operands) > 2:
                self.error(f"多余的操作数: '{operands[2]}'")
                return None
            if len(operands) < 2:
                if not operands:
                    self.error("缺少文件操作数")
                else:
                    self.error(f"缺少目标文件操作数: '{operands[0]}'")
                return None
            if self.parents:
                # -T 把目标当普通文件，与 --parents「目标必须是目录」天生冲突。
                self.error("使用 --parents 时目标必须是目录，不能与 -T 同时使用")
                return None
            sources = operands[:-1]
            dest_text = operands[-1]
            return _Plan(
                sources=sources,
                dest=_resolve(self.ctx.cwd, dest_text),
                dest_label=_trim(dest_text),
                dest_raw=dest_text,
                dest_is_dir=False,
                dest_trailing_sep=_ends_with_sep(dest_text),
            )

        if target_dir is not None:
            if not operands:
                self.error("缺少文件操作数")
                return None
            dest = _resolve(self.ctx.cwd, target_dir)
            if not dest.exists():
                self.error(f"无法访问 '{target_dir}': 没有那个文件或目录")
                return None
            if not dest.is_dir():
                self.error(f"目标 '{target_dir}' 不是目录")
                return None
            return _Plan(
                sources=list(operands),
                dest=dest,
                dest_label=_trim(target_dir),
                dest_raw=target_dir,
                dest_is_dir=True,
                dest_trailing_sep=_ends_with_sep(target_dir),
            )

        if not operands:
            self.error("缺少文件操作数")
            return None
        if len(operands) < 2:
            self.error(f"缺少目标文件操作数: '{operands[0]}'")
            return None

        sources = operands[:-1]
        dest_text = operands[-1]
        dest = _resolve(self.ctx.cwd, dest_text)
        trailing_sep = _ends_with_sep(dest_text)

        if self.parents:
            if not dest.is_dir():
                self.error(f"使用 --parents 时目标必须是目录: '{dest_text}'")
                return None
            return _Plan(
                sources=sources,
                dest=dest,
                dest_label=_trim(dest_text),
                dest_raw=dest_text,
                dest_is_dir=True,
                dest_trailing_sep=trailing_sep,
            )

        # 目标带尾分隔符 ⇒ 目标必须是一个目录；已存在却不是目录时报错
        # （GNU：failed to access 'X/': Not a directory）。
        # 这条要先于「多个源时目标必须是目录」判：GNU 遇到 plain.txt/ 时
        # 报的是 failed to access，不是 target is not a directory。
        if trailing_sep and dest.exists() and not dest.is_dir():
            self.error(f"无法访问 '{dest_text}': 不是目录")
            return None

        # 多个源时目标必须是已存在的目录，这条先于逐个源的存在性检查。
        if len(sources) > 1 and not dest.is_dir():
            self.error(f"目标 '{dest_text}' 不是目录")
            return None

        return _Plan(
            sources=sources,
            dest=dest,
            dest_label=_trim(dest_text),
            dest_raw=dest_text,
            dest_is_dir=dest.is_dir(),
            dest_trailing_sep=trailing_sep,
        )

    # ---------- 单个源 ----------

    def copy_source(self, source: str, plan: "_Plan") -> None:
        src = _resolve(self.ctx.cwd, source)
        try:
            src_stat = os.stat(src)
        except OSError as exc:
            self.error(f"无法访问 '{source}': {exc.strerror or exc}")
            return

        is_dir = stat.S_ISDIR(src_stat.st_mode)
        if is_dir and not self.recursive:
            self.error(f"未指定 -r，跳过目录 '{source}'")
            return

        dest_path, dest_path_label = self._destination_for(source, plan)

        if os.path.lexists(dest_path):
            if os.path.isdir(dest_path) and not os.path.islink(dest_path):
                if not is_dir:
                    self.error(f"不能用普通文件 '{source}' 覆盖目录 '{dest_path_label}'")
                    return
            elif is_dir:
                self.error(f"不能用目录 '{source}' 覆盖非目录 '{dest_path_label}'")
                return

        if _same_file(src, dest_path):
            self.error(f"'{source}' 和 '{dest_path_label}' 是同一个文件")
            return

        if is_dir and _is_inside(dest_path, src):
            self.error(f"不能把目录 '{source}' 复制到它自己里面: '{dest_path_label}'")
            return

        if is_dir:
            self.copy_dir(src, dest_path, source, dest_path_label, src_stat, plan)
        else:
            self.copy_file(src, dest_path, source, dest_path_label, src_stat, plan)

    def _destination_for(self, source: str, plan: "_Plan") -> tuple[Path, str]:
        """算出这个源的落点路径，以及报错/verbose 里要显示的标签。"""
        if self.parents:
            relative = _parents_relative(source)
            return plan.dest / relative, f"{plan.dest_label}/{relative}"

        if plan.dest_is_dir and not self.args.no_target_directory:
            name = _basename(source)
            return plan.dest / name, f"{plan.dest_label}/{name}"
        return plan.dest, plan.dest_label

    # ---------- 复制动作 ----------

    def copy_file(
        self,
        src: Path,
        dst: Path,
        src_label: str,
        dst_label: str,
        src_stat: os.stat_result,
        plan: "_Plan",
    ) -> None:
        exists = os.path.lexists(dst)

        if exists and os.path.isdir(dst) and not os.path.islink(dst):
            self.error(f"不能用普通文件 '{src_label}' 覆盖目录 '{dst_label}'")
            return

        if exists and self.no_clobber:
            return
        if exists and self.update and not _source_is_newer(src, dst):
            return
        if exists and self.interactive and not self._confirm(dst_label):
            return

        if exists and self.suffix:
            backup = Path(str(dst) + self.suffix)
            try:
                os.replace(dst, backup)
            except OSError as exc:
                self.error(f"无法把 '{dst_label}' 改名为 '{backup}': {exc.strerror or exc}")
                return
            exists = False

        if exists and self.remove_destination:
            try:
                _remove_path(dst)
            except OSError as exc:
                self.error(f"无法删除 '{dst_label}': {exc.strerror or exc}")
                return
            exists = False

        if exists and self.force:
            try:
                os.chmod(dst, stat.S_IREAD | stat.S_IWRITE)
            except OSError:
                pass

        if os.path.islink(src) and self.no_dereference:
            if not self._copy_link(src, dst, src_label, dst_label):
                return
        else:
            if self.parents:
                # --parents 要自己把源路径的父目录建出来。
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    self.error(f"无法创建目录 '{_trim(dst.parent)}': {exc.strerror or exc}")
                    return
            elif plan.dest_trailing_sep and not plan.dest_is_dir and dst == plan.dest and not exists:
                # 目标带尾分隔符时不能落地成普通文件（GNU：cannot create
                # regular file 'X/': Not a directory）。目录源已在上面分流。
                self.error(f"无法创建普通文件 '{plan.dest_raw}': 不是目录")
                return
            try:
                with open(src, "rb") as reader, open(dst, "wb") as writer:
                    shutil.copyfileobj(reader, writer, _CHUNK)
            except OSError as exc:
                self.error(f"无法创建普通文件 '{dst_label}': {exc.strerror or exc}")
                return

        if "timestamps" in self.preserve:
            try:
                os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))
            except OSError:
                pass
        if "mode" in self.preserve:
            _apply_mode(dst, src_stat)

        if self.verbose:
            self.ctx.stdout.write(f"'{src_label}' -> '{dst_label}'\n")

    def copy_dir(
        self,
        src: Path,
        dst: Path,
        src_label: str,
        dst_label: str,
        src_stat: os.stat_result,
        plan: "_Plan",
    ) -> None:
        if not os.path.exists(dst):
            try:
                # 只有 --parents 才顺手建父目录；GNU 拷目录时父目录不存在是直接报错。
                dst.mkdir(parents=self.parents)
            except OSError as exc:
                self.error(f"无法创建目录 '{dst_label}': {exc.strerror or exc}")
                return
            if self.verbose:
                self.ctx.stdout.write(f"'{src_label}' -> '{dst_label}'\n")
        elif not dst.is_dir():
            self.error(f"不能用目录 '{src_label}' 覆盖非目录 '{dst_label}'")
            return

        try:
            names = sorted(os.listdir(src))
        except OSError as exc:
            self.error(f"无法打开目录 '{src_label}': {exc.strerror or exc}")
            return

        for name in names:
            child = src / name
            child_label = f"{src_label}/{name}"
            child_dst = dst / name
            child_dst_label = f"{dst_label}/{name}"
            try:
                child_stat = os.stat(child, follow_symlinks=False)
            except OSError as exc:
                self.error(f"无法访问 '{child_label}': {exc.strerror or exc}")
                continue
            if stat.S_ISDIR(child_stat.st_mode):
                self.copy_dir(child, child_dst, child_label, child_dst_label, child_stat, plan)
            else:
                self.copy_file(child, child_dst, child_label, child_dst_label, child_stat, plan)

        # 目录的 mtime 要在内容写完之后再设，否则会被子文件的写入顶掉。
        if "timestamps" in self.preserve:
            try:
                os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))
            except OSError:
                pass
        if "mode" in self.preserve:
            _apply_mode(dst, src_stat)

    def _copy_link(self, src: Path, dst: Path, src_label: str, dst_label: str) -> bool:
        target = os.readlink(src)
        try:
            os.symlink(target, dst)
        except OSError as exc:
            self.error(f"无法创建符号链接 '{dst_label}': {exc.strerror or exc}")
            return False
        if self.verbose:
            self.ctx.stdout.write(f"'{src_label}' -> '{dst_label}'\n")
        return True

    # ---------- 交互与报错 ----------

    def _confirm(self, dst_label: str) -> bool:
        self.ctx.stderr.write(f"cp: 覆盖 '{dst_label}'? ")
        self.ctx.stderr.flush()
        line = self.ctx.stdin.readline() if self.ctx.stdin is not None else ""
        answer = line.strip().lower()
        return answer in ("y", "yes")

    def error(self, message: str) -> None:
        self.had_error = True
        self.ctx.stderr.write(f"cp: {message}\n")


# ---------- 路径小工具 ----------


class _Plan(NamedTuple):
    """一次 cp 调用的落点规划。

    dest_trailing_sep 记的是「用户写的目标带不带尾分隔符」：
    GNU 用它区分「目标是目录」与「目标是普通文件」，带尾分隔符时
    目标必须是一个目录（已存在却不是目录就报 Not a directory）。
    dest_raw 保留用户原样写的目标串，报错时按原样显示（GNU 也保留尾斜杠）。
    """

    sources: list[str]
    dest: Path
    dest_label: str
    dest_raw: str
    dest_is_dir: bool
    dest_trailing_sep: bool


def _ends_with_sep(text: str) -> bool:
    """操作数是不是以路径分隔符结尾（GNU 靠它判断目标是不是目录）。"""
    return text.endswith("/") or text.endswith("\\")


def _resolve(cwd: Path, operand: str) -> Path:
    """相对路径按运行上下文的工作目录解析（与本项目其它指令一致）。"""
    target = Path(operand)
    if not target.is_absolute():
        target = cwd / target
    return target


def _trim(path: Path | str) -> str:
    """把路径末尾的分隔符去掉，只留一层标签用。"""
    text = str(path).replace("\\", "/")
    return text.rstrip("/") or text


def _basename(path_text: str) -> str:
    normalized = path_text.replace("\\", "/")
    stripped = normalized.rstrip("/")
    if not stripped:
        return normalized
    return stripped.rsplit("/", 1)[-1]


def _parents_relative(source: str) -> str:
    """--parents 用的相对路径：去掉盘符与开头的分隔符。"""
    text = source.replace("\\", "/")
    if len(text) >= 2 and text[1] == ":":
        text = text[2:]
    return text.lstrip("/")


def _same_file(left: Path, right: Path) -> bool:
    try:
        if os.path.exists(left) and os.path.exists(right):
            return os.path.samefile(left, right)
    except OSError:
        pass
    try:
        return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))
    except OSError:
        return False


def _is_inside(child: Path, parent: Path) -> bool:
    """判断 child 是否落在 parent 里面（用于挡住把目录复制进自己）。"""
    try:
        child_key = os.path.normcase(os.path.abspath(child))
        parent_key = os.path.normcase(os.path.abspath(parent))
    except OSError:
        return False
    if child_key == parent_key:
        return False
    prefix = parent_key if parent_key.endswith(os.sep) else parent_key + os.sep
    return child_key.startswith(prefix)


def _source_is_newer(src: Path, dst: Path) -> bool:
    try:
        src_stat = os.stat(src)
        dst_stat = os.stat(dst)
    except OSError:
        return True
    return src_stat.st_mtime_ns > dst_stat.st_mtime_ns


def _apply_mode(dst: Path, src_stat: os.stat_result) -> None:
    """Windows 没有 POSIX 权限位，mode 落成只读属性。"""
    writable = bool(src_stat.st_mode & stat.S_IWRITE)
    try:
        os.chmod(dst, stat.S_IREAD | (stat.S_IWRITE if writable else 0))
    except OSError:
        pass


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        os.unlink(path)
