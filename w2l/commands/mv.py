"""mv：移动文件或目录（GNU mv 风格子集）。

同盘移动走 rename/replace，跨盘退回「拷贝 + 删除」；文件按字节搬，不做编码转换。
行为对齐 GNU coreutils 8.32 的 mv（全部经 Git Bash 的 /usr/bin/mv 实跑对照）。

与 GNU 的一处关键差异：GNU 的 mv **不合并目录**。目标下同名目录已存在且非空时
直接报「Directory not empty」，不像 cp 那样逐个文件覆盖过去。

退出码遵循本项目约定：0 成功，2 用法或运行错误（GNU 用 1）。
"""

from __future__ import annotations

import argparse
import errno
import os
import shutil
import stat
from pathlib import Path

from ..context import RunContext
from ..entry import command_prog
from ..errors import UsageError
from ..flags import FlagTracker, resolve_exclusive
from ..registry import command

_DEFAULT_SUFFIX = "~"


def build_parser() -> argparse.ArgumentParser:
    prog = command_prog("mv")
    parser = argparse.ArgumentParser(
        prog=prog,
        description="移动文件或目录",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            f"  {prog} w2l/registry.py w2l/registry.py.bak\n"
            f"  {prog} w2l/commands backup/\n"
            f"  {prog} -v -b README.md docs/README.md\n"
            f"  {prog} -t build/ w2l/registry.py w2l/context.py\n"
        ),
    )
    parser.add_argument("operands", nargs="*", metavar="SOURCE... DEST", help="源（可多个）与目标")
    parser.add_argument("-f", "--force", action="store_true", help="强制覆盖（先去掉目标的只读属性）")
    parser.add_argument(
        "-i",
        "--interactive",
        action=FlagTracker,
        dest="interactive",
        default=False,
        help="覆盖已存在的目标前询问",
    )
    parser.add_argument(
        "-n",
        "--no-clobber",
        action=FlagTracker,
        dest="no_clobber",
        default=False,
        help="不覆盖已存在的目标",
    )
    parser.add_argument("-u", "--update", action="store_true", help="仅当源比目标新时才移动")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示每个被移动的条目")
    parser.add_argument("-b", "--backup", action="store_true", help="覆盖前把旧目标改名备份")
    parser.add_argument(
        "-S",
        "--suffix",
        default=None,
        metavar="SUFFIX",
        help="备份后缀（默认 ~，单独给 -S 就等于隐含开备份）",
    )
    parser.add_argument("-t", "--target-directory", default=None, metavar="DIR", help="把目标目录写死")
    parser.add_argument("-T", "--no-target-directory", action="store_true", help="把目标当普通文件，不当目录")
    return parser


@command("mv", "移动文件或目录（GNU mv 风格子集）", build_parser)
def mv(args: argparse.Namespace, ctx: RunContext) -> int:
    try:
        state = _State(args, ctx)
        plan = state.plan()
    except UsageError as exc:
        ctx.stderr.write(f"mv: {exc}\n")
        return 2
    if plan is None:
        return 2

    sources, dest, dest_label, dest_is_dir = plan
    for source in sources:
        state.move_source(source, dest, dest_label, dest_is_dir)
    return 2 if state.had_error else 0


class _State:
    """一次 mv 调用的全部状态与动作。"""

    def __init__(self, args: argparse.Namespace, ctx: RunContext) -> None:
        self.args = args
        self.ctx = ctx
        self.had_error = False

        self.verbose = args.verbose
        self.force = args.force
        self.update = args.update
        # GNU 里 -S 单独给就等于隐含开备份。
        self.backup = args.backup or args.suffix is not None
        self.suffix = args.suffix if args.suffix is not None else _DEFAULT_SUFFIX
        self.interactive, self.no_clobber = self._resolve_overwrite_policy(args)

    # ---------- 选项归并 ----------

    @staticmethod
    def _resolve_overwrite_policy(args: argparse.Namespace) -> tuple[bool, bool]:
        """-i 与 -n 互相清掉对方：GNU 里后给的那个赢。

        判据取「最后一次出现」（共享实现见 w2l/flags.py），所以
        `-n -i -n` 是 -n 赢，与 GNU 实测一致。
        """
        policy = resolve_exclusive(
            getattr(args, "option_order", None) or [],
            {"interactive": bool(args.interactive), "no_clobber": bool(args.no_clobber)},
        )
        return policy["interactive"], policy["no_clobber"]

    # ---------- 操作数规划 ----------

    def plan(self) -> tuple[list[str], Path, str, bool] | None:
        """拆出源列表与目标。返回 None 表示规划阶段已经报错。"""
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
            dest_text = operands[1]
            return [operands[0]], _resolve(self.ctx.cwd, dest_text), _trim(dest_text), False

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
            return list(operands), dest, _trim(target_dir), True

        if not operands:
            self.error("缺少文件操作数")
            return None
        if len(operands) < 2:
            self.error(f"缺少目标文件操作数: '{operands[0]}'")
            return None

        sources = operands[:-1]
        dest_text = operands[-1]
        dest = _resolve(self.ctx.cwd, dest_text)

        # 多个源时目标必须是已存在的目录，这条先于逐个源的存在性检查。
        if len(sources) > 1 and not dest.is_dir():
            self.error(f"目标 '{dest_text}' 不是目录")
            return None

        return sources, dest, _trim(dest_text), dest.is_dir()

    # ---------- 单个源 ----------

    def move_source(self, source: str, dest: Path, dest_label: str, dest_is_dir: bool) -> None:
        src = _resolve(self.ctx.cwd, source)
        try:
            src_stat = os.stat(src)
        except OSError:
            self.error(f"无法访问 '{source}': 没有那个文件或目录")
            return

        is_dir = stat.S_ISDIR(src_stat.st_mode)
        dst, dst_label = self._destination_for(source, dest, dest_label, dest_is_dir)

        if _same_file(src, dst):
            self.error(f"'{source}' 和 '{dst_label}' 是同一个文件")
            return

        if is_dir and _is_inside(dst, src):
            self.error(f"不能把目录 '{source}' 移动到它自己的子目录: '{dst_label}'")
            return

        dst_exists = os.path.lexists(dst)
        dst_is_dir = False
        if dst_exists:
            dst_is_dir = os.path.isdir(dst) and not os.path.islink(dst)
            if is_dir and not dst_is_dir:
                self.error(f"不能用目录 '{source}' 覆盖非目录 '{dst_label}'")
                return
            if not is_dir and dst_is_dir:
                self.error(f"不能用普通文件 '{source}' 覆盖目录 '{dst_label}'")
                return

        if dst_exists:
            # 覆盖策略：-n 直接跳过，-u 只在源更新时才动，-i 问一句。
            if self.no_clobber:
                return
            if self.update and not _source_is_newer(src, dst):
                return
            if self.interactive and not self._confirm(dst_label):
                return
            # GNU 的 mv 不合并目录：目标同名目录非空时直接报错。
            if is_dir and dst_is_dir and _dir_not_empty(dst):
                self.error(f"无法把目录 '{source}' 移动到 '{dst_label}': 目录非空")
                return

        if not dst.parent.exists():
            self.error(f"无法把 '{source}' 移动到 '{dst_label}': 没有那个文件或目录")
            return

        backup_label = ""
        if dst_exists and self.backup:
            backup_label = self._backup(dst, dst_label)
            if not backup_label:
                return

        if not self._do_move(src, dst, source, dst_label):
            return

        if self.verbose:
            line = f"renamed '{source}' -> '{dst_label}'"
            if backup_label:
                line += f" (backup: '{backup_label}')"
            self.ctx.stdout.write(line + "\n")

    def _destination_for(
        self, source: str, dest: Path, dest_label: str, dest_is_dir: bool
    ) -> tuple[Path, str]:
        """算出这个源的落点路径，以及报错/verbose 里要显示的标签。"""
        if dest_is_dir:
            name = _basename(source)
            return dest / name, f"{dest_label}/{name}"
        return dest, dest_label

    # ---------- 动作 ----------

    def _backup(self, dst: Path, dst_label: str) -> str:
        """把旧目标改名加后缀备份掉。返回备份标签，失败返回空串。"""
        backup = Path(str(dst) + self.suffix)
        backup_label = f"{dst_label}{self.suffix}"
        try:
            if os.path.lexists(backup):
                _remove_path(backup)
            os.replace(dst, backup)
        except OSError as exc:
            self.error(f"无法把 '{dst_label}' 备份成 '{backup_label}': {exc.strerror or exc}")
            return ""
        return backup_label

    def _do_move(self, src: Path, dst: Path, src_label: str, dst_label: str) -> bool:
        try:
            if os.path.isdir(dst) and not os.path.islink(dst):
                # 目标是个空目录：Windows 的 rename 不允许覆盖已有目录，先删掉再改名。
                os.rmdir(dst)
            _clear_readonly(dst)
            os.replace(src, dst)
            return True
        except OSError as exc:
            if exc.errno == errno.EXDEV:
                # 跨盘：退回到「拷贝 + 删除」。
                try:
                    shutil.move(str(src), str(dst))
                    return True
                except OSError as inner:
                    self.error(
                        f"无法把 '{src_label}' 移动到 '{dst_label}': {inner.strerror or inner}"
                    )
                    return False
            self.error(f"无法把 '{src_label}' 移动到 '{dst_label}': {exc.strerror or exc}")
            return False

    # ---------- 交互与报错 ----------

    def _confirm(self, dst_label: str) -> bool:
        self.ctx.stderr.write(f"mv: 覆盖 '{dst_label}'? ")
        self.ctx.stderr.flush()
        line = self.ctx.stdin.readline() if self.ctx.stdin is not None else ""
        answer = line.strip().lower()
        return answer in ("y", "yes")

    def error(self, message: str) -> None:
        self.had_error = True
        self.ctx.stderr.write(f"mv: {message}\n")


# ---------- 路径小工具 ----------


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
    """判断 child 是否落在 parent 里面（用于挡住把目录移进自己）。"""
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


def _dir_not_empty(path: Path) -> bool:
    try:
        with os.scandir(path) as entries:
            for _ in entries:
                return True
    except OSError:
        return False
    return False


def _clear_readonly(path: Path) -> None:
    """Windows 上覆盖只读文件会失败，先去掉只读属性。

    GNU 的 mv 直接 rename 过去，不看目标文件的权限位，所以这里无条件清。
    """
    try:
        if not path.exists():
            return
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    except OSError:
        pass


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        os.unlink(path)
