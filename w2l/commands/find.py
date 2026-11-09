"""find：在目录树中按条件查找文件（GNU find 风格子集）。

对齐 GNU findutils 4.10 的部分（实测 Git Bash 的 GNU find 4.10.0 得出）：

- 表达式语法：谓词用 -a/-and、-o/-or、!/-not 组合，括号分组，-a 优先级高于 -o
- 隐式 -print：表达式里除了 -prune 之外没有动作时，自动在整条表达式后面接一个 -print
- 遍历顺序：按目录项的原始顺序（与 GNU 的 readdir 顺序一致），先序；-depth 改成后序
- 路径打印：操作数原样打印，子项用 / 连接；-print0 用 NUL 分隔
- -size 默认按 512 字节块向上取整，带 c/w/k/M/G 后缀时按对应单位向上取整
- -prune 命中后不再进入该目录；-maxdepth/-mindepth 控制深度
- -exec 支持 ";"（每个文件跑一次）与 "+"（攒一批跑一次）

Windows 环境下的必然差异（README 有完整说明）：

- -type 只认 f（普通文件）与 d（目录），符号链接/块设备/字符设备/FIFO 在 Windows 上不存在
- -newer 比较修改时间；Windows 的 mtime 精度足够，但与 GNU 存在秒级取整差异
- -exec 在 Windows 上先按可执行文件查找，找不到时退回 cmd /c 执行，
  这样 echo 这类内建命令也能用（GNU 不走 shell）
- 什么都不匹配时返回退出码 1（GNU 返回 0），遵循本项目「无结果返回 1」的约定
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Iterator, NamedTuple

from ..context import RunContext
from ..entry import command_prog
from ..errors import UsageError
from ..registry import command

_BLOCK = 512
_SIZE_UNITS = {"b": _BLOCK, "c": 1, "w": 2, "k": 1024, "M": 1024**2, "G": 1024**3}
_DAY = 86400
_AND_OPS = ("-a", "-and")
_OR_OPS = ("-o", "-or")
_NOT_OPS = ("!", "-not")
# 这些动作之外就不再补隐式 -print；-prune 不算（GNU 手册明确说 -prune 不算动作）
_PRINT_SUPPRESSORS = ("print", "print0", "printf", "exec", "delete")


class _Item(NamedTuple):
    """一个待判定的文件：显示用的路径、真实路径、stat 结果与深度。"""

    display: str
    fs_path: Path
    st: os.stat_result
    depth: int

    @property
    def is_dir(self) -> bool:
        return stat.S_ISDIR(self.st.st_mode)

    @property
    def basename(self) -> str:
        return self.fs_path.name or self.display

    @property
    def dirname(self) -> str:
        head = self.display.rsplit("/", 1)[0] if "/" in self.display else "."
        return head


class _Node:
    """表达式节点基类。"""

    is_action = False

    def evaluate(self, item: _Item, state: "_State") -> bool:  # pragma: no cover - 基类
        raise NotImplementedError


class _Test(_Node):
    """判定类谓词：只返回真假，不产生副作用。"""

    def __init__(self, func: Callable[[_Item, "_State"], bool]) -> None:
        self._func = func

    def evaluate(self, item: _Item, state: "_State") -> bool:
        return self._func(item, state)


class _Action(_Node):
    """动作类谓词：执行副作用，恒返回真。

    动作节点带 is_action 标记，GNU 的短路规则靠它决定还要不要算右半边。
    """

    is_action = True

    def __init__(self, func: Callable[[_Item, "_State"], bool], name: str = "") -> None:
        self._func = func
        self.name = name

    def evaluate(self, item: _Item, state: "_State") -> bool:
        return self._func(item, state)


class _And(_Node):
    """与：左侧为假就短路；左侧是动作则不再算右侧（GNU 的规则）。"""

    def __init__(self, left: _Node, right: _Node) -> None:
        self.left = left
        self.right = right

    def evaluate(self, item: _Item, state: "_State") -> bool:
        if not self.left.evaluate(item, state):
            return False
        if self.left.is_action:
            return True
        return self.right.evaluate(item, state)


class _Or(_Node):
    """或：左侧为真且左侧不是动作时短路；否则算右侧。"""

    def __init__(self, left: _Node, right: _Node) -> None:
        self.left = left
        self.right = right

    def evaluate(self, item: _Item, state: "_State") -> bool:
        if self.left.evaluate(item, state) and not self.left.is_action:
            return True
        return self.right.evaluate(item, state)


class _Not(_Node):
    """非。"""

    def __init__(self, child: _Node) -> None:
        self.child = child

    def evaluate(self, item: _Item, state: "_State") -> bool:
        return not self.child.evaluate(item, state)


class _State:
    """一次 find 运行的状态：输出目标、计数、错误、-prune 标记与 -exec 攒批。"""

    def __init__(self, ctx: RunContext, now: float) -> None:
        self.ctx = ctx
        self.now = now
        self.printed = 0
        self.matched = 0
        self.had_error = False
        self.pruned = False
        self.pending: list[str] = []
        self.pending_cmd: list[str] | None = None
        self.pending_uses_placeholder = False

    def write(self, text: str) -> bool:
        """写一行输出。动作类谓词恒返回真，所以这里返回 True。"""
        self.ctx.stdout.write(text)
        self.printed += 1
        return True

    def flush_pending(self) -> None:
        """把 -exec CMD {} + 攒下的一批路径一次性执行掉。"""
        if self.pending_cmd is None or not self.pending:
            return
        args = _expand_placeholder(self.pending_cmd, self.pending, self.pending_uses_placeholder)
        self.pending = []
        self.pending_cmd = None
        _run_command(args, self)


class _FindParser(argparse.ArgumentParser):
    """find 的命令行不能交给 argparse。

    find 的表达式里混着括号、-o、! 和裸参数，argparse 会把它们当选项或位置参数报错，
    所以这里只在 --help 时用 argparse，其余原样把 argv 交给指令自己解析。
    """

    def parse_args(self, args=None, namespace=None):  # type: ignore[override]
        argv = list(sys.argv[1:] if args is None else args)
        if "-h" in argv or "--help" in argv:
            self.print_help()
            raise SystemExit(0)
        result = argparse.Namespace()
        result.raw_args = argv
        return result


def build_parser() -> argparse.ArgumentParser:
    prog = command_prog("find")
    parser = _FindParser(
        prog=prog,
        description="在目录树中按条件查找文件",
        add_help=False,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "表达式:\n"
            "  -name PATTERN      文件名匹配通配符\n"
            "  -iname PATTERN     同上，忽略大小写\n"
            "  -path PATTERN      整个路径匹配通配符\n"
            "  -regex PATTERN     整个路径匹配正则\n"
            "  -type [fd]         按类型筛选：f 普通文件、d 目录\n"
            "  -size N[cwkMG]     按大小筛选，默认 512 字节块\n"
            "  -mtime N           N 天前修改过（可带 +/-）\n"
            "  -mmin N            N 分钟前修改过（可带 +/-）\n"
            "  -newer FILE        比 FILE 新的文件\n"
            "  -empty             空文件或空目录\n"
            "  -true / -false     恒真 / 恒假\n"
            "  -prune             不进入该目录\n"
            "  -print / -print0   打印路径\n"
            "  -printf FORMAT     按格式打印\n"
            "  -exec CMD ;|+      对每个匹配执行命令\n"
            "  -delete            删除匹配的文件\n"
            "  -a -o ! ( )        与 / 或 / 非 / 分组\n"
            "\n"
            "示例:\n"
            f"  {prog} . -name '*.py'\n"
            f"  {prog} w2l -type f -size +1k\n"
            f"  {prog} . -name '*.log' -mtime +7\n"
            f"  {prog} . -type d -name build -prune -o -print\n"
        ),
    )
    parser.add_argument("--help", action="help", help="显示此帮助信息并退出")
    return parser


@command("find", "在目录树中按条件查找文件（GNU find 风格子集）", build_parser)
def find(args: argparse.Namespace, ctx: RunContext) -> int:
    options, paths, tokens = _split_args(list(args.raw_args))
    expression = _parse_expression(tokens)
    state = _State(ctx, time.time())

    if _has_delete_action(expression):
        # -delete 隐含 -depth：必须先删子项再删父目录
        options["depth"] = True

    if expression is None:
        expression = _Action(lambda item, st: st.write(item.display + "\n"), name="print")
    elif not _has_print_action(expression):
        expression = _And(
            expression,
            _Action(lambda item, st: st.write(item.display + "\n"), name="print"),
        )

    operands = paths or ["."]
    for operand in operands:
        _run_operand(operand, expression, options, state)

    state.flush_pending()

    if state.had_error:
        return 2
    # 「有没有结果」按表达式是否命中来算，而不是按打印了几行：
    # -delete 这种只做动作不打印的用法，命中的文件照样算结果。
    return 0 if state.matched else 1


# --------------------------------------------------------------------------
# 命令行拆分
# --------------------------------------------------------------------------


def _split_args(argv: list[str]) -> tuple[dict, list[str], list[str]]:
    """把命令行拆成（全局选项, 路径, 表达式记号）。

    GNU 的规则：路径是开头连续的、不以 '-' 开头且不是 '(' / '!' 的参数；
    从第一个像选项的参数开始就算表达式。-maxdepth/-mindepth/-depth 是全局选项，
    写在路径后面也认（GNU 实测 `find tree -maxdepth 2` 生效）。
    """
    options: dict = {
        "maxdepth": None,
        "mindepth": 0,
        "depth": False,
        "follow": False,
    }
    paths: list[str] = []
    index = 0
    total = len(argv)

    def take_option_value(name: str, value: str) -> None:
        if name == "-maxdepth":
            options["maxdepth"] = _parse_depth(value, name)
        else:
            options["mindepth"] = _parse_depth(value, name)

    while index < total:
        arg = argv[index]
        if arg in ("-H", "-L", "-P"):
            options["follow"] = arg == "-L"
            index += 1
            continue
        if arg in ("-maxdepth", "-mindepth"):
            if index + 1 >= total:
                raise UsageError(f"选项 '{arg}' 缺少参数")
            take_option_value(arg, argv[index + 1])
            index += 2
            continue
        if arg == "-depth":
            options["depth"] = True
            index += 1
            continue
        if arg == "--":
            index += 1
            break
        break

    while index < total:
        arg = argv[index]
        if arg.startswith("-") or arg in ("(", "!"):
            break
        paths.append(arg)
        index += 1

    tokens: list[str] = []
    while index < total:
        arg = argv[index]
        if arg in ("-maxdepth", "-mindepth"):
            if index + 1 >= total:
                raise UsageError(f"选项 '{arg}' 缺少参数")
            take_option_value(arg, argv[index + 1])
            index += 2
            continue
        if arg == "-depth":
            options["depth"] = True
            index += 1
            continue
        tokens.append(arg)
        index += 1

    return options, paths, tokens


def _parse_depth(value: str, name: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise UsageError(f"选项 '{name}' 需要一个非负整数，收到 '{value}'") from None
    if number < 0:
        raise UsageError(f"选项 '{name}' 需要一个非负整数，收到 '{value}'")
    return number


# --------------------------------------------------------------------------
# 表达式解析
# --------------------------------------------------------------------------


class _ExprParser:
    """递归下降解析 find 表达式。

    优先级：! 最高，其次 -a，最后 -o；相邻的两个谓词默认是 -a。
    """

    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> str | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def take(self) -> str | None:
        token = self.peek()
        if token is not None:
            self.pos += 1
        return token

    def parse(self) -> _Node | None:
        if not self.tokens:
            return None
        node = self.parse_or()
        if self.pos != len(self.tokens):
            leftover = self.tokens[self.pos]
            raise UsageError(f"表达式里有多余的 '{leftover}'")
        return node

    def parse_or(self) -> _Node:
        node = self.parse_and()
        while self.peek() in _OR_OPS:
            self.take()
            node = _Or(node, self.parse_and())
        return node

    def parse_and(self) -> _Node:
        node = self.parse_not()
        while True:
            token = self.peek()
            if token is None or token in _OR_OPS or token == ")":
                break
            if token in _AND_OPS:
                self.take()
            node = _And(node, self.parse_not())
        return node

    def parse_not(self) -> _Node:
        if self.peek() in _NOT_OPS:
            self.take()
            return _Not(self.parse_not())
        return self.parse_primary()

    def parse_primary(self) -> _Node:
        token = self.take()
        if token is None:
            raise UsageError("表达式意外结束")
        if token == "(":
            node = self.parse_or()
            if self.take() != ")":
                raise UsageError("表达式无效：期待 ')' 但没有找到")
            return node
        if token == ")":
            raise UsageError("表达式里有多余的 ')'")
        return _build_leaf(self, token)

    def argument(self, name: str) -> str:
        token = self.take()
        if token is None:
            raise UsageError(f"选项 '{name}' 缺少参数")
        return token


def _parse_expression(tokens: list[str]) -> _Node | None:
    return _ExprParser(tokens).parse()


def _build_leaf(parser: _ExprParser, token: str) -> _Node:
    """把一个谓词/动作记号变成节点。"""
    if token in ("-name", "-iname", "-path", "-ipath"):
        pattern = parser.argument(token)
        return _Test(_make_glob_test(token, pattern))
    if token in ("-regex", "-iregex"):
        pattern = parser.argument(token)
        return _Test(_make_regex_test(token, pattern))
    if token == "-type":
        kind = parser.argument(token)
        return _Test(_make_type_test(kind))
    if token == "-size":
        spec = parser.argument(token)
        return _Test(_make_size_test(spec))
    if token == "-mtime":
        spec = parser.argument(token)
        return _Test(_make_time_test(spec, _DAY, minutes=False))
    if token == "-mmin":
        spec = parser.argument(token)
        return _Test(_make_time_test(spec, 60, minutes=True))
    if token == "-newer":
        reference = parser.argument(token)
        return _Test(_make_newer_test(reference))
    if token == "-empty":
        return _Test(_make_empty_test)
    if token == "-true":
        return _Test(lambda item, state: True)
    if token == "-false":
        return _Test(lambda item, state: False)
    if token == "-prune":
        return _Action(_make_prune_action, name="prune")
    if token == "-print":
        return _Action(lambda item, state: state.write(item.display + "\n"), name="print")
    if token == "-print0":
        return _Action(lambda item, state: state.write(item.display + "\0"), name="print0")
    if token == "-printf":
        fmt = parser.argument(token)
        return _Action(_make_printf_action(fmt), name="printf")
    if token == "-exec":
        return _make_exec_action(parser)
    if token == "-delete":
        return _Action(_make_delete_action, name="delete")
    if not token.startswith("-"):
        raise UsageError(f"路径必须写在表达式前面：'{token}'")
    raise UsageError(f"未知谓词 '{token}'")


def _has_print_action(node: _Node) -> bool:
    """表达式里是否已经有会打印的动作（决定要不要补隐式 -print）。

    -prune 不算：GNU 手册明确说「表达式里除了 -prune 或 -print 之外没有动作」时才补 -print，
    所以 `find . -type d -prune` 仍然会把命中的目录打印出来。
    """
    if isinstance(node, _Action):
        return node.name in _PRINT_SUPPRESSORS
    if isinstance(node, _And):
        return _has_print_action(node.left) or _has_print_action(node.right)
    if isinstance(node, _Or):
        return _has_print_action(node.left) or _has_print_action(node.right)
    if isinstance(node, _Not):
        return _has_print_action(node.child)
    return False


def _has_delete_action(node: _Node) -> bool:
    """表达式里是否有 -delete（有的话必须按 -depth 的后序遍历，否则删不干净目录）。"""
    if isinstance(node, _Action):
        return node.name == "delete"
    if isinstance(node, _And):
        return _has_delete_action(node.left) or _has_delete_action(node.right)
    if isinstance(node, _Or):
        return _has_delete_action(node.left) or _has_delete_action(node.right)
    if isinstance(node, _Not):
        return _has_delete_action(node.child)
    return False


# --------------------------------------------------------------------------
# 谓词
# --------------------------------------------------------------------------


def _make_glob_test(option: str, pattern: str) -> Callable[[_Item, _State], bool]:
    ignore_case = option in ("-iname", "-ipath")
    whole_path = option in ("-path", "-ipath")
    matcher = fnmatch.fnmatchcase if not ignore_case else fnmatch.fnmatch

    def test(item: _Item, state: _State) -> bool:
        target = item.display if whole_path else item.basename
        return matcher(target, pattern)

    return test


def _make_regex_test(option: str, pattern: str) -> Callable[[_Item, _State], bool]:
    flags = re.IGNORECASE if option == "-iregex" else 0
    try:
        compiled = re.compile(pattern, flags)
    except re.error as exc:
        raise UsageError(f"无效的正则表达式 '{pattern}': {exc}") from exc

    def test(item: _Item, state: _State) -> bool:
        return compiled.match(item.display) is not None

    return test


def _make_type_test(kind: str) -> Callable[[_Item, _State], bool]:
    if kind not in ("f", "d", "l"):
        raise UsageError(f"-type 的参数无效：'{kind}'（本实现支持 f 普通文件、d 目录、l 符号链接）")
    if kind == "f":
        return lambda item, state: stat.S_ISREG(item.st.st_mode)
    if kind == "d":
        return lambda item, state: stat.S_ISDIR(item.st.st_mode)
    return lambda item, state: stat.S_ISLNK(item.st.st_mode)


def _effective_size(item: _Item) -> int:
    """文件大小；目录一律算 0。

    Windows 的目录 st_size 不稳定（空目录是 0，条目一多就变成 4096），
    而 GNU find 看到的目录大小恒为 0（MSYS 的 stat 对目录返回 0）。
    这里统一按 0 处理，既和 GNU 一致，也避免同一条命令的结果随目录内容变化。
    """
    if item.is_dir:
        return 0
    return item.st.st_size


def _make_size_test(spec: str) -> Callable[[_Item, _State], bool]:
    op, number, unit = _parse_number_spec(spec, "-size")
    size_unit = _SIZE_UNITS.get(unit, _BLOCK)

    def test(item: _Item, state: _State) -> bool:
        blocks = -(-_effective_size(item) // size_unit)  # 向上取整
        return _compare(op, blocks, number)

    return test


def _make_time_test(spec: str, unit: int, minutes: bool) -> Callable[[_Item, _State], bool]:
    op, number, _ = _parse_number_spec(spec, "-mtime" if not minutes else "-mmin")

    def test(item: _Item, state: _State) -> bool:
        age = state.now - item.st.st_mtime
        if minutes:
            # GNU findutils 4.10 的 -mmin 精确形式把「当前这一分钟」算作第 1 分钟，
            # 所以整分钟计数比 -mtime 的天数计数多 1（实测 90 秒的文件落在 -mmin 2）。
            count = age // 60 + 1
        else:
            count = age // unit
        if op == "eq":
            return count == number
        if op == "gt":
            return count > number
        return count <= number if minutes else count < number

    return test


def _make_newer_test(reference: str) -> Callable[[_Item, _State], bool]:
    """-newer FILE：修改时间比 FILE 新的文件。"""
    reported = False

    def test(item: _Item, state: _State) -> bool:
        nonlocal reported
        # 参照文件按运行上下文的当前目录解析（相对路径要跟着 cwd 走）
        path = Path(reference)
        if not path.is_absolute():
            path = state.ctx.cwd / path
        try:
            stamp = path.stat().st_mtime
        except OSError as exc:
            if not reported:
                reported = True
                state.ctx.stderr.write(f"find: 无法访问 '{reference}': {exc.strerror or exc}\n")
            state.had_error = True
            return False
        return item.st.st_mtime > stamp

    return test


def _make_empty_test(item: _Item, state: _State) -> bool:
    if item.is_dir:
        try:
            with os.scandir(item.fs_path) as scanner:
                return next(scanner, None) is None
        except OSError:
            return False
    return item.st.st_size == 0


def _make_prune_action(item: _Item, state: _State) -> bool:
    state.pruned = True
    return True


# --------------------------------------------------------------------------
# 动作
# --------------------------------------------------------------------------


def _make_printf_action(fmt: str) -> Callable[[_Item, _State], bool]:
    def action(item: _Item, state: _State) -> bool:
        state.write(_format_printf(fmt, item))
        return True

    return action


def _format_printf(fmt: str, item: _Item) -> str:
    out: list[str] = []
    index = 0
    length = len(fmt)
    while index < length:
        char = fmt[index]
        if char == "\\" and index + 1 < length:
            nxt = fmt[index + 1]
            mapping = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "0": "\0", "a": "\a", "b": "\b"}
            out.append(mapping.get(nxt, "\\" + nxt))
            index += 2
            continue
        if char == "%" and index + 1 < length:
            directive = fmt[index + 1]
            # 时间类指令带 @ 后缀（%T@ 是纪元秒数），要当成两个字符的指令读
            if directive in ("T", "A", "C") and fmt[index + 2 : index + 3] == "@":
                out.append(_printf_directive(directive + "@", item))
                index += 3
                continue
            out.append(_printf_directive(directive, item))
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _format_epoch(st: os.stat_result) -> str:
    """把文件时间按 GNU %T@ 的样子打印：秒 + 小数点后 10 位。

    用 st_mtime_ns（整数纳秒）而不是浮点秒：浮点尾数带二进制噪声，
    而 Windows 的文件时间是 100 纳秒精度，浮点算出来的末几位会差 1。
    实测 GNU findutils 4.10 的 MSYS 构建小数点后印 10 位，这里按同样口径输出。
    """
    seconds, fraction = divmod(st.st_mtime_ns, 10**9)
    return f"{seconds}.{fraction:09d}0"


def _printf_directive(directive: str, item: _Item) -> str:
    if directive == "p":
        return item.display
    if directive == "f":
        return item.basename
    if directive == "h":
        return item.dirname
    if directive == "s":
        return str(_effective_size(item))
    if directive == "y":
        return "d" if item.is_dir else "f"
    if directive == "T@":
        # GNU 的 %T@ 是「纪元以来的秒数」带小数。实测 GNU findutils 4.10 的 MSYS 构建
        # 小数点后印 10 位（纳秒被算大了 10 倍，末位多一个 0），这里按实测口径输出。
        # 单独的 %T 在 GNU 那边是坏的（会报 memory exhausted），所以只支持 %T@
        return _format_epoch(item.st)
    if directive == "t":
        return time.strftime("%b %e %H:%M", time.localtime(item.st.st_mtime))
    if directive == "%":
        return "%"
    return "%" + directive


def _make_exec_action(parser: _ExprParser) -> _Node:
    """解析 -exec CMD ... ; 或 -exec CMD ... +。"""
    command_args: list[str] = []
    terminator = None
    while True:
        token = parser.take()
        if token is None:
            raise UsageError("选项 '-exec' 缺少参数")
        if token in (";", "+"):
            terminator = token
            break
        command_args.append(token)

    if terminator is None:
        raise UsageError("选项 '-exec' 缺少结尾的 ';' 或 '+'")
    if not command_args:
        raise UsageError("选项 '-exec' 缺少要执行的命令")

    uses_placeholder = any("{}" in arg for arg in command_args)

    if terminator == ";":
        def action(item: _Item, state: _State) -> bool:
            args = _expand_placeholder(command_args, [item.display], uses_placeholder)
            _run_command(args, state)
            return True
    else:
        def action(item: _Item, state: _State) -> bool:
            if state.pending_cmd is None:
                state.pending_cmd = list(command_args)
                state.pending_uses_placeholder = uses_placeholder
            state.pending.append(item.display)
            return True

    return _Action(action, name="exec")


def _expand_placeholder(command_args: list[str], paths: list[str], uses_placeholder: bool) -> list[str]:
    if uses_placeholder:
        expanded: list[str] = []
        for arg in command_args:
            if "{}" in arg:
                expanded.extend(path for path in paths)
            else:
                expanded.append(arg)
        return expanded
    return list(command_args) + list(paths)


def _run_command(args: list[str], state: _State) -> None:
    """执行 -exec 的命令。

    GNU 直接 fork/exec 目标程序，不经过 shell。Windows 上很多常用命令是内建的
    （echo、dir、type），这里在找不到可执行文件时退回 cmd /c 执行。

    退回时整条命令必须作为**一个**参数交给 cmd：拆成多个参数时 cmd 会按自己的
    编码重新拼命令行，中文路径会变成 GBK 字节；合成一个字符串则原样透传 UTF-8。
    """
    try:
        subprocess.run(args, check=False)
    except FileNotFoundError:
        if os.name != "nt":
            state.ctx.stderr.write(f"find: 无法执行 '{args[0]}': 没有那个文件或目录\n")
            state.had_error = True
            return
        try:
            subprocess.run(["cmd", "/c", subprocess.list2cmdline(args)], check=False)
        except OSError as exc:
            state.ctx.stderr.write(f"find: 无法执行 '{args[0]}': {exc.strerror or exc}\n")
            state.had_error = True


def _make_delete_action(item: _Item, state: _State) -> bool:
    try:
        if item.is_dir:
            os.rmdir(item.fs_path)
        else:
            os.remove(item.fs_path)
    except OSError as exc:
        state.ctx.stderr.write(f"find: 无法删除 '{item.display}': {exc.strerror or exc}\n")
        state.had_error = True
    return True


# --------------------------------------------------------------------------
# 遍历
# --------------------------------------------------------------------------


def _run_operand(operand: str, expression: _Node, options: dict, state: _State) -> None:
    """从一个操作数出发遍历。"""
    fs_path = Path(operand)
    if not fs_path.is_absolute():
        fs_path = state.ctx.cwd / fs_path
    display = operand.replace("\\", "/")
    try:
        st = os.lstat(fs_path)
    except OSError as exc:
        state.ctx.stderr.write(f"find: 无法访问 '{operand}': {exc.strerror or exc}\n")
        state.had_error = True
        return

    item = _Item(display, fs_path, st, 0)
    _walk(item, expression, options, state)


def _walk(item: _Item, expression: _Node, options: dict, state: _State) -> None:
    """先序遍历；-depth 改成后序（先处理子项再处理自己）。"""
    if options["depth"]:
        _walk_children_first(item, expression, options, state)
        return

    _evaluate(item, expression, options, state)
    if item.is_dir and not state.pruned:
        _walk_children(item, expression, options, state)


def _walk_children(item: _Item, expression: _Node, options: dict, state: _State) -> None:
    maxdepth = options["maxdepth"]
    if maxdepth is not None and item.depth >= maxdepth:
        return
    try:
        with os.scandir(item.fs_path) as scanner:
            children = list(scanner)
    except OSError as exc:
        state.ctx.stderr.write(f"find: 无法打开目录 '{item.display}': {exc.strerror or exc}\n")
        state.had_error = True
        return
    for entry in children:
        child_path = Path(entry.path)
        try:
            child_st = entry.stat(follow_symlinks=False)
        except OSError as exc:
            state.ctx.stderr.write(f"find: 无法访问 '{item.display}': {exc.strerror or exc}\n")
            state.had_error = True
            continue
        child = _Item(_child_display(item.display, entry.name), child_path, child_st, item.depth + 1)
        _walk(child, expression, options, state)


def _walk_children_first(item: _Item, expression: _Node, options: dict, state: _State) -> None:
    if item.is_dir:
        _walk_children(item, expression, options, state)
    _evaluate(item, expression, options, state)


def _child_display(parent: str, name: str) -> str:
    if parent.endswith("/"):
        return parent + name
    return parent + "/" + name


def _evaluate(item: _Item, expression: _Node, options: dict, state: _State) -> None:
    """判定一个文件；深度不足 mindepth 时直接跳过。"""
    state.pruned = False
    if item.depth < options["mindepth"]:
        return
    try:
        if expression.evaluate(item, state):
            state.matched += 1
    except OSError as exc:
        state.ctx.stderr.write(f"find: 无法访问 '{item.display}': {exc.strerror or exc}\n")
        state.had_error = True


# --------------------------------------------------------------------------
# 辅助
# --------------------------------------------------------------------------


def _parse_number_spec(spec: str, option: str) -> tuple[str, int, str]:
    """解析带 +/- 前缀和单位后缀的数值参数。

    返回 (比较符, 数值, 单位)。比较符是 eq / gt / lt。
    """
    text = spec
    op = "eq"
    if text.startswith("+"):
        op = "gt"
        text = text[1:]
    elif text.startswith("-"):
        op = "lt"
        text = text[1:]

    unit = ""
    if text and text[-1].isalpha():
        unit = text[-1]
        text = text[:-1]
    if unit and unit not in _SIZE_UNITS:
        raise UsageError(f"选项 '{option}' 的单位后缀无效：'{unit}'")

    try:
        number = int(text)
    except ValueError:
        raise UsageError(f"选项 '{option}' 的参数无效：'{spec}'") from None
    if number < 0:
        raise UsageError(f"选项 '{option}' 的参数无效：'{spec}'")
    return op, number, unit


def _compare(op: str, left: int, right: int) -> bool:
    if op == "eq":
        return left == right
    if op == "gt":
        return left > right
    return left < right
