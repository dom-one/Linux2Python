"""rm：删除文件或目录（GNU rm 风格子集）。

行为对齐 GNU coreutils 8.32 的 rm（全部经 Git Bash 的 /usr/bin/rm 实跑对照，
提示语与取舍另见 README 的「rm 能力清单」）。

与 GNU 的两处关键差异：

1. **目录遍历按名字排序**（GNU 用 readdir 顺序，本来就不确定），
   所以 -v 的打印顺序与 GNU 可能不同，最终删除的内容完全一致。
2. **提示语用中文**（GNU 是英文），与本项目的 cp / mv 保持一致。

退出码遵循本项目约定：0 成功，2 用法或运行错误（GNU 用 1）。
"""

from __future__ import annotations

import argparse
import errno
import os
import stat
import sys
from pathlib import Path

from ..context import RunContext
from ..entry import command_prog
from ..errors import UsageError
from ..registry import command

# 交互档位。本项目把 GNU 的 SOMETIMES 拆成「不逐项询问」+「开工前问一次」。
_NEVER = "never"
_ALWAYS = "always"

# GNU 的 nonexistent_file_errno：这几个 errno 算「文件本来就不存在」，-f 时忽略。
_IGNORABLE_MISSING = frozenset(
    {errno.ENOENT, errno.ENOTDIR, errno.EINVAL, errno.EILSEQ}
)

# --interactive=WHEN 的取值表（GNU 接受 never/no/none、once、always/yes）。
# 第三位是「忽略不存在的文件」：None 表示这一位不动（GNU 里 --interactive=never
# 就是不动它，见 rm.c 的 interactive_never 分支）。
_WHEN_VALUES = {
    "never": (_NEVER, False, None),
    "no": (_NEVER, False, None),
    "none": (_NEVER, False, None),
    "once": (_NEVER, True, False),
    "always": (_ALWAYS, False, False),
    "yes": (_ALWAYS, False, False),
}

# 内部选项名：把 --interactive=WHEN 改写成「选项 + 值」两个 token。
_INTERNAL_WHEN = "--__rm_interactive_when"

# 一棵子树的处理结果。
_OK = "ok"              # 正常删除
_DECLINED = "declined"  # 用户拒绝了这一项，但祖先仍会被询问
_SKIPPED = "skipped"    # 用户拒绝进入该目录，该目录及其祖先都不再询问
_FAILED = "failed"      # 出错了，祖先不再询问（错误已经报过）


def _append_mode(namespace: argparse.Namespace, spec) -> None:
    order = getattr(namespace, "mode_order", None)
    if order is None:
        order = []
        setattr(namespace, "mode_order", order)
    order.append(spec)


class _RmParser(argparse.ArgumentParser):
    """GNU 风格的 --interactive[=WHEN]。

    GNU 用 getopt_long 的 optional_argument：**只有 --interactive=WHEN 这种写法才带值**，
    `--interactive WHEN` 里的 WHEN 是文件操作数（会被当成待删的文件）。

    argparse 的 nargs="?" 分不清这两者（会把后面的操作数吃掉），所以在解析前
    把 --interactive=WHEN 改写成内部选项「选项 + 值」两个 token。
    """

    def parse_known_args(self, args=None, namespace=None):
        argv = list(sys.argv[1:] if args is None else args)
        rewritten: list[str] = []
        for token in argv:
            # GNU 的 getopt_long 允许长选项缩写，--inter=once 与 --interactive=once 等价。
            if token.startswith("--inter") and "=" in token:
                rewritten.append(_INTERNAL_WHEN)
                rewritten.append(token.split("=", 1)[1])
            else:
                rewritten.append(token)
        return super().parse_known_args(rewritten, namespace)


class _ModeTracker(argparse.Action):
    """记录交互类选项的先后顺序。

    GNU 的 -f / -i / -I 共用同一组开关，**后给的那个赢**：
    `-f -i` 等于 `-i`（不忽略不存在的文件），`-i -f` 等于 `-f`。
    """

    def __init__(self, option_strings, dest, spec=None, **kwargs):
        kwargs["nargs"] = 0
        super().__init__(option_strings, dest, **kwargs)
        self.spec = spec

    def __call__(self, parser, namespace, values, option_string=None):
        _append_mode(namespace, self.spec)


class _InteractiveFlag(argparse.Action):
    """裸 --interactive（不带值）：等价于 --interactive=always。"""

    def __init__(self, option_strings, dest, **kwargs):
        kwargs["nargs"] = 0
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        _append_mode(namespace, ("when", "always"))


class _InteractiveWhen(argparse.Action):
    """内部选项：承载 --interactive=WHEN 的 WHEN 值。"""

    def __init__(self, option_strings, dest, **kwargs):
        kwargs["nargs"] = 1
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        _append_mode(namespace, ("when", values[0]))


def build_parser() -> argparse.ArgumentParser:
    prog = command_prog("rm")
    parser = _RmParser(
        prog=prog,
        # GNU 的 rm 没有 -h（那是 ls 的），所以关掉 argparse 自带的 -h。
        add_help=False,
        description="删除文件或目录",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            f"  {prog} w2l/registry.py.bak\n"
            f"  {prog} -r build/\n"
            f"  {prog} -v -f logs/*.tmp\n"
            f"  {prog} -d empty_dir\n"
        ),
    )
    parser.add_argument("--help", action="help", help="显示此帮助信息并退出")
    parser.add_argument("operands", nargs="*", metavar="FILE", help="要删除的文件或目录")
    parser.add_argument(
        "-f",
        "--force",
        action=_ModeTracker,
        dest="force",
        spec="force",
        help="忽略不存在的文件与缺失的操作数，绝不询问",
    )
    parser.add_argument(
        "-i",
        action=_ModeTracker,
        dest="interactive",
        spec="always",
        help="每删一个之前都询问一次",
    )
    parser.add_argument(
        "-I",
        action=_ModeTracker,
        dest="interactive_once",
        spec="once",
        help="只在删超过三个文件或递归删目录前询问一次",
    )
    parser.add_argument(
        "--interactive",
        action=_InteractiveFlag,
        dest="interactive",
        help="按 WHEN 决定何时询问：never / once / always（不带值等于 always）",
    )
    parser.add_argument(
        _INTERNAL_WHEN,
        action=_InteractiveWhen,
        dest="interactive_when",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "-r",
        "-R",
        "--recursive",
        action="store_true",
        help="递归删除目录及其内容",
    )
    parser.add_argument("-d", "--dir", action="store_true", help="删除空目录")
    parser.add_argument("-v", "--verbose", action="store_true", help="逐条打印删了什么")
    return parser


@command("rm", "删除文件或目录（GNU rm 风格子集）", build_parser)
def rm(args: argparse.Namespace, ctx: RunContext) -> int:
    try:
        state = _State(args, ctx)
    except UsageError as exc:
        ctx.stderr.write(f"rm: {exc}\n")
        return 2
    return state.run()


class _State:
    """一次 rm 调用的全部状态与动作。"""

    def __init__(self, args: argparse.Namespace, ctx: RunContext) -> None:
        self.args = args
        self.ctx = ctx
        self.had_error = False

        self.operands = list(args.operands)
        self.recursive = args.recursive
        self.dir_mode = args.dir
        self.verbose = args.verbose

        # 交互档位：逐项询问、开工前问一次、忽略不存在的文件。
        self.mode = _NEVER
        self.prompt_once = False
        self.ignore_missing = False
        for spec in getattr(args, "mode_order", None) or []:
            self._apply_spec(spec)

    # ---------- 选项归并 ----------

    def _apply_spec(self, spec) -> None:
        """套用一个交互类选项（GNU：后给的那个赢）。"""
        if spec[0] == "when":
            when = spec[1].strip().lower()
            if when not in _WHEN_VALUES:
                raise UsageError(
                    f"--interactive 的无效取值 '{spec[1]}'，可选：never、once、always"
                )
            mode, prompt_once, ignore_missing = _WHEN_VALUES[when]
            self.mode = mode
            self.prompt_once = prompt_once
            if ignore_missing is not None:
                self.ignore_missing = ignore_missing
            return

        if spec == "force":
            self.mode = _NEVER
            self.prompt_once = False
            self.ignore_missing = True
            return

        if spec == "always":
            self.mode = _ALWAYS
            self.prompt_once = False
            self.ignore_missing = False
            return

        if spec == "once":
            self.mode = _NEVER
            self.prompt_once = True
            self.ignore_missing = False
            return

    # ---------- 主流程 ----------

    def run(self) -> int:
        if not self.operands:
            # GNU：给了 -f 时缺操作数不算错（ignore_missing_files 决定的）。
            if self.ignore_missing:
                return 0
            self.error("缺少文件操作数")
            return 2

        if self.prompt_once and (self.recursive or 3 < len(self.operands)):
            count = len(self.operands)
            if self.recursive:
                question = f"递归删除 {count} 个参数? "
            else:
                question = f"删除 {count} 个参数? "
            if not self.confirm(question):
                return 0

        for operand in self.operands:
            self.remove_operand(operand)
        return 2 if self.had_error else 0

    # ---------- 单个操作数 ----------

    def remove_operand(self, label: str) -> None:
        path = _resolve(self.ctx.cwd, label)
        try:
            st = os.lstat(path)
        except OSError as exc:
            if self.ignore_missing and exc.errno in _IGNORABLE_MISSING:
                return
            self.error(f"无法删除 '{label}': {exc.strerror or exc}")
            return

        if not stat.S_ISDIR(st.st_mode):
            self.remove_file(path, label)
            return

        # GNU 的顺序：先看「能不能删这个目录」，再谈 . / .. 守卫。
        empty = _is_empty_dir(path)
        if not self.recursive and not (self.dir_mode and empty):
            if self.dir_mode:
                self.error(f"无法删除 '{label}': 目录非空")
            else:
                self.error(f"无法删除 '{label}': 是一个目录")
            return

        # POSIX：命令行的 basename 是 . 或 .. 时直接跳过。
        if _last_component(label) in (".", ".."):
            self.error(f"拒绝删除 '.' 或 '..' 目录: 跳过 '{label}'")
            return

        # GNU 默认 --preserve-root：根目录一律不删。
        if _is_root(path):
            self.error(f"拒绝删除根目录: 跳过 '{label}'")
            return

        if not self.recursive:
            # 只有 -d 且目录为空这一种情况能走到这里。
            self.remove_empty_dir(path, label)
            return

        self.remove_tree(path, label)

    # ---------- 文件 ----------

    def remove_file(self, path: Path, label: str) -> str:
        kind = "符号链接" if _is_symlink(path) else "普通文件"
        if self.mode == _ALWAYS and not self.confirm(f"删除{kind} '{label}'? "):
            return _DECLINED
        try:
            # POSIX 的 rm 只看目录的写权限，文件自身只读照样能删；
            # Windows 上只读属性会挡住 DeleteFile，所以先去掉它。
            _clear_readonly(path)
            os.unlink(path)
        except OSError as exc:
            if self.ignore_missing and exc.errno in _IGNORABLE_MISSING:
                return _OK
            self.error(f"无法删除 '{label}': {exc.strerror or exc}")
            return _FAILED
        if self.verbose:
            self.ctx.stdout.write(f"removed '{label}'\n")
        return _OK

    # ---------- 目录 ----------

    def remove_empty_dir(self, path: Path, label: str) -> str:
        if self.mode == _ALWAYS and not self.confirm(f"删除目录 '{label}'? "):
            return _DECLINED
        try:
            _clear_readonly(path)
            os.rmdir(path)
        except OSError as exc:
            if self.ignore_missing and exc.errno in _IGNORABLE_MISSING:
                return _OK
            self.error(f"无法删除 '{label}': {exc.strerror or exc}")
            return _FAILED
        if self.verbose:
            self.ctx.stdout.write(f"removed directory '{label}'\n")
        return _OK

    def remove_tree(self, path: Path, label: str) -> str:
        """递归删除一棵目录树。

        GNU 的顺序：先进目录（问「要不要进去」），逐个子项处理，
        最后回头删目录本身（问「要不要删这个目录」）。
        """
        try:
            names = sorted(os.listdir(path))
        except OSError as exc:
            self.error(f"无法打开目录 '{label}': {exc.strerror or exc}")
            return _FAILED

        if not names:
            # 空目录不用问「要不要进去」，直接问「要不要删这个目录」。
            return self.remove_empty_dir(path, label)

        if self.mode == _ALWAYS and not self.confirm(f"进入目录 '{label}'? "):
            # 用户拒绝进入：这棵子树整体跳过，祖先也不再询问。
            return _SKIPPED

        failed = skipped = declined = False
        for name in names:
            child = path / name
            child_label = _join_label(label, name)
            try:
                st = os.lstat(child)
            except OSError as exc:
                self.error(f"无法访问 '{child_label}': {exc.strerror or exc}")
                failed = True
                continue
            if stat.S_ISDIR(st.st_mode):
                status = self.remove_tree(child, child_label)
            else:
                status = self.remove_file(child, child_label)
            if status == _FAILED:
                failed = True
            elif status == _SKIPPED:
                skipped = True
            elif status == _DECLINED:
                declined = True

        if failed:
            # 子项出错：祖先不再询问，本目录也不删（GNU 的 mark_ancestor_dirs）。
            return _FAILED
        if skipped:
            # 拒绝进入某个子目录：祖先也不再询问（GNU 同此）。
            return _SKIPPED
        # declined（拒绝了某个文件）不影响祖先的询问：GNU 里拒绝删文件不会
        # 给祖先打标记，父目录照样问「要不要删这个目录」。

        if self.mode == _ALWAYS and not self.confirm(f"删除目录 '{label}'? "):
            return _DECLINED
        try:
            _clear_readonly(path)
            os.rmdir(path)
        except OSError as exc:
            self.error(f"无法删除 '{label}': {exc.strerror or exc}")
            return _FAILED
        if self.verbose:
            self.ctx.stdout.write(f"removed directory '{label}'\n")
        return _OK

    # ---------- 交互与报错 ----------

    def confirm(self, question: str) -> bool:
        """问一句并读一行回答。

        GNU 的 yesno 只看这一行的第一个字符是不是 y/Y：
        'y'、'Y'、'yes'、'y extra' 算同意，' y'（前面有空格）算不同意。
        """
        self.ctx.stderr.write(f"rm: {question}")
        self.ctx.stderr.flush()
        if self.ctx.stdin is None:
            return False
        line = self.ctx.stdin.readline()
        if not line:
            return False
        return line[0] in ("y", "Y")

    def error(self, message: str) -> None:
        self.had_error = True
        self.ctx.stderr.write(f"rm: {message}\n")


# ---------- 路径小工具 ----------


def _resolve(cwd: Path, operand: str) -> Path:
    """相对路径按运行上下文的工作目录解析（与本项目其它指令一致）。"""
    target = Path(operand)
    if not target.is_absolute():
        target = cwd / target
    return target


def _is_empty_dir(path: Path) -> bool:
    try:
        with os.scandir(path) as entries:
            for _ in entries:
                return False
    except OSError:
        return False
    return True


def _is_symlink(path: Path) -> bool:
    try:
        return os.path.islink(path)
    except OSError:
        return False


def _is_root(path: Path) -> bool:
    """判断是不是文件系统根目录（GNU 默认 --preserve-root 拒绝删它）。"""
    text = str(path)
    try:
        return os.path.dirname(text) == text
    except (TypeError, ValueError):
        return False


def _last_component(label: str) -> str:
    """取路径的最后一段（去掉尾部的斜杠）。"""
    text = label.replace("\\", "/").rstrip("/")
    if not text:
        return text
    return text.rsplit("/", 1)[-1]


def _join_label(parent: str, name: str) -> str:
    """子项的标签：父标签 + '/' + 名字（GNU 的 fts 路径也是这么拼的）。"""
    return f"{parent.rstrip('/')}/{name}"


def _clear_readonly(path: Path) -> None:
    """去掉只读属性。

    POSIX 的 rm 只看目录的写权限，文件自身只读照样能删；
    Windows 上只读属性会挡住 DeleteFile，所以这里补上写权限位。
    """
    try:
        if _is_symlink(path):
            return
        mode = os.lstat(path).st_mode
        os.chmod(path, mode | stat.S_IWRITE)
    except OSError:
        pass
