"""chmod：修改文件权限（GNU chmod 风格子集）。

Windows 没有 POSIX 权限位，能真正落盘的只有一个「只读属性」。
本实现按 MSYS 的口径处理——实测 Git Bash 的 chmod 也只存只读属性
（chmod 755 之后 GNU stat 报的是 644），所以两边行为是对得上的：

- 当前模式：可写文件 0644、只读文件 0444、目录 0755、可执行文件 0755
- 目标模式：八进制直接取；符号模式在当前模式上逐条算
- 落盘：目标模式里属主没有写位就设只读属性，有写位就清掉只读属性
- 报数：沿用 GNU 原文（changed / retained as / failed to change）

能存下来的权限位只有属主写位这一位，其余位（组、其他、执行、setuid 等）
只参与报数、不落盘，这一点与 MSYS 上的 GNU chmod 完全一致。

退出码遵循本项目约定：0 成功，2 用法或运行错误（GNU 用 1）。
"""

from __future__ import annotations

import argparse
import os
import stat
from pathlib import Path

from ..context import RunContext
from ..entry import command_prog
from ..errors import UsageError
from ..perms import MISSING_MODE, canonical_mode, mode_octal, perm_bits
from ..registry import command

_OCTAL_DIGITS = "01234567"
# 每一类权限的位掩码（含 rwx）与它在模式里的位移。
_CLASS_BITS = {"u": 0o700, "g": 0o070, "o": 0o007}
_CLASS_SHIFT = {"u": 6, "g": 3, "o": 0}
_CLASS_SPECIAL = {"u": 0o4000, "g": 0o2000, "o": 0o1000}
_ALL_CLASSES = 0o777
_PERM_CHARS = "rwxXst"


def build_parser() -> argparse.ArgumentParser:
    prog = command_prog("chmod")
    parser = argparse.ArgumentParser(
        prog=prog,
        description="修改文件权限",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            f"  {prog} 644 README.md\n"
            f"  {prog} +x bin/tool.exe\n"
            f"  {prog} -R u+w,go-w data/\n"
            f"  {prog} -v --reference=template.txt a.txt b.txt\n"
        ),
    )
    parser.add_argument("operands", nargs="*", metavar="MODE FILE...", help="模式与要改的文件")
    parser.add_argument("-c", "--changes", action="store_true", help="只报告真的改了的文件")
    parser.add_argument("-f", "--silent", "--quiet", action="store_true", help="不输出错误信息")
    parser.add_argument("-v", "--verbose", action="store_true", help="每个处理过的文件都报一行")
    parser.add_argument("-R", "--recursive", action="store_true", help="递归处理目录")
    parser.add_argument("--reference", default=None, metavar="RFILE", help="用 RFILE 的模式")
    parser.add_argument(
        "--preserve-root",
        action="store_true",
        help="拒绝操作根目录（本实现的默认行为）",
    )
    parser.add_argument(
        "--no-preserve-root",
        action="store_true",
        help="允许操作根目录（GNU 的默认行为）",
    )
    return parser


@command("chmod", "修改文件权限（GNU chmod 风格子集）", build_parser)
def chmod(args: argparse.Namespace, ctx: RunContext) -> int:
    state = _State(args, ctx)
    try:
        plan = state.plan()
    except UsageError as exc:
        ctx.stderr.write(f"chmod: {exc}\n")
        return 2
    if plan is None:
        return 2

    spec, files = plan
    for label in files:
        state.process(label, spec)
    return 2 if state.had_error else 0


class _Clause:
    """符号模式里的一条子句，例如 u+w、go-w、a=rwx。"""

    def __init__(self, who: int, op: str, perms: str, copy_from: str | None) -> None:
        self.who = who
        self.op = op
        self.perms = perms
        self.copy_from = copy_from

    @property
    def special_mask(self) -> int:
        """这条子句涉及的特殊位（setuid / setgid / sticky）。"""
        mask = 0
        for name, bits in _CLASS_BITS.items():
            if self.who & bits:
                mask |= _CLASS_SPECIAL[name]
        return mask

    def apply(self, mode: int, is_dir: bool) -> int:
        if self.copy_from is not None:
            # 复制写法（u+g、g=u）只在 '=' 时生效，GNU 实测如此。
            if self.op != "=":
                return mode
            # 取源类那一组「局部三位」，再填进目标类（类与类之间要错位）。
            local = (mode >> _CLASS_SHIFT[self.copy_from]) & 0o7
            result = mode
            for name, bits in _CLASS_BITS.items():
                if self.who & bits:
                    result &= ~bits
                    result |= (local & 0o7) << _CLASS_SHIFT[name]
            return result

        rwx, special = self._masks(mode, is_dir)
        if self.op == "+":
            return mode | (rwx & self.who) | special
        if self.op == "-":
            return mode & ~((rwx & self.who) | special)
        # '='：先清掉这一类的权限位与特殊位，再按子句设置
        return (mode & ~(self.who | self.special_mask)) | (rwx & self.who) | special

    def _masks(self, mode: int, is_dir: bool) -> tuple[int, int]:
        """把子句里的权限字符拆成「rwx 位掩码」与「特殊位掩码」。"""
        rwx = 0
        special = 0
        for ch in self.perms:
            if ch == "r":
                rwx |= 0o444
            elif ch == "w":
                rwx |= 0o222
            elif ch == "x":
                rwx |= 0o111
            elif ch == "X":
                # X 只在「是目录」或「本来就有执行位」时才给执行位。
                if is_dir or (mode & 0o111):
                    rwx |= 0o111
            elif ch == "s":
                if self.who & _CLASS_BITS["u"]:
                    special |= 0o4000
                if self.who & _CLASS_BITS["g"]:
                    special |= 0o2000
            elif ch == "t":
                # sticky 位只对 other 类有效：GNU 的 u+t 什么也不改（实测）。
                if self.who & _CLASS_BITS["o"]:
                    special |= 0o1000
        return rwx, special


class _ModeSpec:
    """一次 chmod 请求里的模式：要么是八进制，要么是若干条符号子句。"""

    def __init__(self, octal: int | None, clauses: list[_Clause]) -> None:
        self.octal = octal
        self.clauses = clauses

    @classmethod
    def octal(cls, value: int) -> "_ModeSpec":
        return cls(value, [])

    def target(self, current: int, is_dir: bool) -> int:
        """算出这个模式作用在当前模式上之后的结果。"""
        if self.octal is not None:
            return self.octal
        mode = current
        for clause in self.clauses:
            mode = clause.apply(mode, is_dir)
        return mode


class _State:
    """一次 chmod 调用的全部状态与动作。"""

    def __init__(self, args: argparse.Namespace, ctx: RunContext) -> None:
        self.args = args
        self.ctx = ctx
        self.had_error = False
        self.verbose = args.verbose
        self.changes = args.changes
        self.silent = args.silent
        self.recursive = args.recursive
        self.allow_root = args.no_preserve_root and not args.preserve_root
        # GNU 打不开文件时报的「原模式」是上一个处理过的文件的模式（实测如此），
        # 一个文件都没处理过时它报的是未初始化的随机值，这里用 0644 兜底。
        self.last_mode: int | None = None

    # ---------- 规划 ----------

    def plan(self) -> tuple[_ModeSpec, list[str]] | None:
        """拆出模式与文件列表。返回 None 表示规划阶段已经报错。"""
        operands = list(self.args.operands)

        if self.args.reference is not None:
            spec = self._reference_spec(self.args.reference)
            if spec is None:
                return None
            if not operands:
                self.error("缺少操作数")
                return None
            return spec, operands

        if not operands:
            self.error("缺少操作数")
            return None

        mode_text = operands[0]
        files = operands[1:]
        if not files:
            self.error(f"模式 '{mode_text}' 之后缺少操作数")
            return None
        try:
            spec = _parse_mode(mode_text)
        except UsageError as exc:
            self.error(str(exc))
            return None
        return spec, files

    def _reference_spec(self, reference: str) -> _ModeSpec | None:
        """--reference：拿参照文件当前的模式当目标模式。"""
        path = _resolve(self.ctx.cwd, reference)
        try:
            st = os.lstat(path)
        except OSError:
            self.error(f"无法访问 '{reference}': 没有那个文件或目录")
            return None
        return _ModeSpec.octal(canonical_mode(st.st_mode))

    # ---------- 单个文件 ----------

    def process(self, label: str, spec: _ModeSpec) -> None:
        path = _resolve(self.ctx.cwd, label)
        if _is_root(path) and not self.allow_root:
            self.error(f"拒绝操作根目录 '{label}'")
            return
        try:
            st = os.lstat(path)
        except OSError:
            self.report_missing(label, spec)
            return
        is_dir = stat.S_ISDIR(st.st_mode)
        self.apply_to(path, label, spec, st.st_mode, is_dir)
        if self.recursive and is_dir:
            self.walk(path, label, spec)

    def walk(self, root: Path, label: str, spec: _ModeSpec) -> None:
        """递归处理目录内容：先进目录，再按名字顺序逐项处理。"""
        try:
            entries = sorted(os.scandir(root), key=lambda item: item.name)
        except OSError as exc:
            self.error(f"无法打开目录 '{label}': {exc.strerror or exc}")
            return
        for entry in entries:
            child_path = Path(entry.path)
            child_label = f"{label}/{entry.name}"
            try:
                st = os.lstat(child_path)
            except OSError:
                self.report_missing(child_label, spec)
                continue
            is_dir = stat.S_ISDIR(st.st_mode)
            self.apply_to(child_path, child_label, spec, st.st_mode, is_dir)
            if is_dir:
                self.walk(child_path, child_label, spec)

    def apply_to(
        self, path: Path, label: str, spec: _ModeSpec, raw_mode: int, is_dir: bool
    ) -> None:
        """算目标模式、报数、落盘。"""
        current = canonical_mode(raw_mode)
        target = spec.target(current, is_dir)
        self.last_mode = current

        if _same_mode(current, target, is_dir):
            if self.verbose:
                self.ctx.stdout.write(
                    f"mode of '{label}' retained as {mode_octal(target)} ({perm_bits(target)})\n"
                )
        elif self.verbose or self.changes:
            self.ctx.stdout.write(
                f"mode of '{label}' changed from {mode_octal(current)} ({perm_bits(current)}) "
                f"to {mode_octal(target)} ({perm_bits(target)})\n"
            )

        try:
            _write_mode(path, target)
        except OSError as exc:
            self.had_error = True
            if not self.silent:
                self.ctx.stderr.write(f"chmod: 无法修改 '{label}' 的权限: {exc.strerror or exc}\n")
            if self.verbose:
                self.ctx.stdout.write(
                    f"failed to change mode of '{label}' from {mode_octal(current)} "
                    f"({perm_bits(current)}) to {mode_octal(target)} ({perm_bits(target)})\n"
                )

    def report_missing(self, label: str, spec: _ModeSpec) -> None:
        """打不开的文件：原模式沿用上一个处理过的文件（GNU 的口径）。"""
        self.had_error = True
        if not self.silent:
            self.ctx.stderr.write(f"chmod: 无法访问 '{label}': 没有那个文件或目录\n")
        if self.verbose:
            current = self.last_mode if self.last_mode is not None else MISSING_MODE
            target = spec.target(current, False)
            self.ctx.stdout.write(
                f"failed to change mode of '{label}' from {mode_octal(current)} "
                f"({perm_bits(current)}) to {mode_octal(target)} ({perm_bits(target)})\n"
            )

    def error(self, message: str) -> None:
        self.had_error = True
        if self.silent:
            return
        self.ctx.stderr.write(f"chmod: {message}\n")


# ---------- 模式解析 ----------


def _parse_mode(text: str) -> _ModeSpec:
    """解析模式参数：以数字开头按八进制，否则按符号模式。"""
    if not text:
        raise UsageError("缺少模式")
    if text[0] in _OCTAL_DIGITS:
        if len(text) > 4 or any(ch not in _OCTAL_DIGITS for ch in text):
            raise UsageError(f"非法模式: '{text}'")
        return _ModeSpec.octal(int(text, 8))
    clauses = _parse_clauses(text)
    if not clauses:
        raise UsageError(f"非法模式: '{text}'")
    return _ModeSpec(None, clauses)


def _parse_clauses(text: str) -> list[_Clause]:
    clauses: list[_Clause] = []
    for raw in text.split(","):
        parsed = _parse_clause(raw)
        if parsed is None:
            raise UsageError(f"非法模式: '{text}'")
        clauses.extend(parsed)
    return clauses


def _parse_clause(raw: str) -> list[_Clause] | None:
    """解析一条子句；不合法返回 None。

    GNU 允许权限串里再出现运算符：`a+rw-x` 是「加 rw，再减 x」，
    逗号分隔的子句与这种串内运算符都会拆成多条子句，
    后一条沿用前一条的 who（GNU 实测如此）。
    """
    index = 0
    who = 0
    while index < len(raw) and raw[index] in "ugoa":
        ch = raw[index]
        # a 代表三类全都要（u|g|o），不是只管 other。
        who |= _ALL_CLASSES if ch == "a" else _CLASS_BITS[ch]
        index += 1
    if index >= len(raw):
        return None
    if not who:
        who = _ALL_CLASSES

    clauses: list[_Clause] = []
    op = ""
    perms = ""
    while index < len(raw):
        ch = raw[index]
        if ch in "+-=":
            if op:
                clause = _make_clause(who, op, perms)
                if clause is None:
                    return None
                clauses.append(clause)
            op = ch
            perms = ""
        else:
            if not op:
                return None
            perms += ch
        index += 1
    if not op:
        return None
    clause = _make_clause(who, op, perms)
    if clause is None:
        return None
    clauses.append(clause)
    return clauses


def _make_clause(who: int, op: str, perms: str) -> _Clause | None:
    """把「who + 运算符 + 权限串」拼成一条子句。"""
    if len(perms) == 1 and perms in "ugo":
        # 复制写法：u+g / g=u，GNU 只在 '=' 时才生效。
        return _Clause(who, op, "", perms)
    if any(ch not in _PERM_CHARS for ch in perms):
        return None
    # 空的权限串是合法的（"o=" 清空 other、"u+" 什么都不加），GNU 实测如此。
    return _Clause(who, op, perms, None)


# ---------- 落盘 ----------


def _same_mode(old: int, new: int, is_dir: bool) -> bool:
    """GNU 判定「模式没变」的规则（本机实测归纳，138 组用例逐条吻合）。

    - 目标模式带 setuid / setgid / sticky 任一位时：
      文件只看「写位的有无」有没有变（这些位在 Windows 上存不下来）；
      目录一律算没变（MSYS 的 stat 对目录恒报 0755，写位看不出来）。
    - 其余情况：写位的有无变了就算变了，否则比低 9 位（rwx）。
    """
    if new & 0o7000:
        if is_dir:
            return True
        return bool(old & 0o222) == bool(new & 0o222)
    if bool(old & 0o222) != bool(new & 0o222):
        return False
    return (old & 0o777) == (new & 0o777)


def _write_mode(path: Path, target: int) -> None:
    """把目标模式落成 Windows 的只读属性。

    Windows 只有只读属性这一个可存的权限位：目标模式里一个写位都没有
    （owner / group / other 三类都没有 w）就设只读，有写位就清掉只读。
    MSYS 上的 GNU chmod 是同一套判据（实测 chmod 7 = 0007 之后文件仍可写，
    chmod 2 = 0002 之后也可写，只有全无写位才变只读）。
    """
    if target & 0o222:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    else:
        os.chmod(path, stat.S_IREAD)


# ---------- 路径小工具 ----------


def _resolve(cwd: Path, operand: str) -> Path:
    """相对路径按运行上下文的工作目录解析（与本项目其它指令一致）。"""
    target = Path(operand)
    if not target.is_absolute():
        target = cwd / target
    return target


def _is_root(path: Path) -> bool:
    """判断是不是文件系统根目录（盘符根或 POSIX 根）。"""
    anchor = path.anchor
    if not anchor:
        return False
    if anchor in ("\\", "/"):
        return True
    if not anchor.endswith(("\\", "/")):
        return False
    return str(path).rstrip("\\/") == anchor.rstrip("\\/")
