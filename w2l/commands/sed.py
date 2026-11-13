"""sed：按脚本对输入做流式编辑（GNU sed 风格子集）。

覆盖 GNU sed 的常用部分：s / y / p / d / n / N / q / Q / = / a / i / c / b / t / T / : ，
地址支持行号、$、正则、first~step、范围以及相对范围（,+N 与 ,~N）。

正则默认基本正则（BRE），与 GNU sed 一致；-r 切换为扩展正则（ERE）。
文件编码按文本可信度择优判定，GBK 文件在英文 Windows 上也能正确编辑。

退出码：0 成功，1 由 q 指令指定，2 用法或运行错误。
"""

from __future__ import annotations

import argparse
import codecs
import locale
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Sequence

from ..context import RunContext
from ..entry import command_prog
from ..errors import UsageError
from ..registry import command

_SNIFF_SIZE = 8192
_FALLBACK_ENCODINGS = ("utf-8", "gb18030", "latin-1")
_SCORE_MARGIN = 0.3
_CJK_RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF))

# 只支持这些指令，其余给明确报错而不是悄悄忽略
_UNSUPPORTED_COMMANDS = {
    "P": "P（打印到最后一个换行符）",
    "D": "D（删除到最后一个换行符）",
    "h": "h（把模式空间存进保留区）",
    "H": "H（把模式空间追加进保留区）",
    "g": "g（把保留区取回模式空间）",
    "G": "G（把保留区追加到模式空间）",
    "x": "x（交换模式空间与保留区）",
    "l": "l（打印不可见字符）",
    "r": "r（把文件读进模式空间）",
    "R": "R（把文件逐行读进模式空间）",
    "w": "w（把模式空间写进文件）",
    "W": "W（把模式空间追加写进文件）",
    "e": "e（把模式空间当命令执行）",
    "z": "z（清空模式空间）",
    "F": "F（把文件名追加进模式空间）",
}


# --------------------------------------------------------------------------
# 地址与命令
# --------------------------------------------------------------------------


@dataclass
class _Address:
    """一条地址。kind 决定怎么求值。"""

    kind: str  # line / last / regex / step / plus / tilde
    number: int = 0
    regex: re.Pattern[str] | None = None
    step: int = 0


@dataclass
class _BlockState:
    """``{ ... }`` 命令块的状态。

    GNU sed 把整个块编译成一条命令：块的地址只在进入块时求值一次，
    块里的命令各自再用自己的地址。所以块里的命令改过模式空间之后，
    块地址不会跟着重新判定。
    """

    addr1: _Address | None = None
    addr2: _Address | None = None
    negate: bool = False
    in_range: bool = False
    end_line: int = 0
    base_line: int = 0
    matches: int = 0
    matched: bool | None = None


@dataclass
class _Command:
    name: str
    addr1: _Address | None = None
    addr2: _Address | None = None
    payload: object = None
    negate: bool = False
    block: _BlockState | None = None
    # 范围状态：每条指令各自维护
    in_range: bool = False
    end_line: int = 0
    base_line: int = 0
    matches: int = 0


@dataclass
class _Substitution:
    regex: re.Pattern[str]
    chunks: list[tuple[str, str, int]]
    global_flag: bool = False
    print_flag: bool = False
    occurrence: int = 0  # 0 表示只换第一个


_MODE_NONE = 0
_MODE_UPPER = 1
_MODE_LOWER = 2
_MODE_UPPER_ONCE = 3
_MODE_LOWER_ONCE = 4


# --------------------------------------------------------------------------
# 脚本解析
# --------------------------------------------------------------------------


class _ScriptParser:
    """把 sed 脚本切成一条条命令。"""

    def __init__(self, script: str, extended: bool) -> None:
        self.text = script
        self.pos = 0
        self.extended = extended
        self.commands: list[_Command] = []
        self.labels: dict[str, int] = {}

    # -- 主循环 ---------------------------------------------------------

    def parse(self) -> tuple[list[_Command], dict[str, int]]:
        self._parse_commands(None, None, None, False)
        return self.commands, self.labels

    def _parse_commands(
        self,
        block_addr1: _Address | None,
        block_addr2: _Address | None,
        block: _BlockState | None,
        in_block: bool,
    ) -> None:
        """解析一串命令。

        block_addr1/block_addr2/block 是外层 ``{ }`` 的地址与状态；
        块里的命令不用再继承这个地址（由块状态统一判定一次）。
        """
        while True:
            self._skip_separators()
            if self.pos >= len(self.text):
                if in_block:
                    raise UsageError("命令块缺少右花括号 '}'")
                return
            if self.text[self.pos] == "#":
                self._skip_line()
                continue
            own1 = self._parse_address()
            own2 = None
            if own1 is not None and self.pos < len(self.text) and self.text[self.pos] == ",":
                self.pos += 1
                own2 = self._parse_address(allow_relative=True)
                if own2 is None:
                    raise UsageError("逗号后面缺少地址")
            if self.pos >= len(self.text):
                raise UsageError("脚本末尾缺少命令")
            negate = False
            if self.pos < len(self.text) and self.text[self.pos] == "!":
                self.pos += 1
                negate = True
            name = self.text[self.pos]
            self.pos += 1
            if name == "}":
                if not in_block:
                    raise UsageError("多了一个右花括号 '}'")
                return
            if name == ":":
                label = self._read_label()
                self.labels[label] = len(self.commands)
                continue
            if name == "{":
                inner = _BlockState(addr1=own1, addr2=own2, negate=negate)
                self._parse_commands(own1, own2, inner, True)
                continue
            command = _Command(
                name=name,
                addr1=own1,
                addr2=own2,
                negate=negate,
                block=block,
            )
            self._parse_payload(command)
            self.commands.append(command)

    # -- 基础工具 -------------------------------------------------------

    def _skip_separators(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] in " \t\r\n;":
            self.pos += 1

    def _skip_line(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] != "\n":
            self.pos += 1

    def _at_separator(self) -> bool:
        return self.pos >= len(self.text) or self.text[self.pos] in ";\n"

    def _read_label(self) -> str:
        start = self.pos
        while self.pos < len(self.text) and not self._at_separator():
            if self.text[self.pos] == "}":
                break
            self.pos += 1
        return self.text[start : self.pos].strip()

    def _read_number(self) -> int:
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos].isdigit():
            self.pos += 1
        if start == self.pos:
            raise UsageError("这里应该是一个数字")
        return int(self.text[start : self.pos])

    # -- 地址 -----------------------------------------------------------

    def _parse_address(self, allow_relative: bool = False) -> _Address | None:
        if self.pos >= len(self.text):
            return None
        char = self.text[self.pos]
        if char.isdigit():
            number = self._read_number()
            if self.pos < len(self.text) and self.text[self.pos] == "~":
                self.pos += 1
                step = self._read_number()
                return _Address("step", number=number, step=step)
            return _Address("line", number=number)
        if allow_relative and char == "+":
            self.pos += 1
            return _Address("plus", number=self._read_number())
        if allow_relative and char == "~":
            self.pos += 1
            return _Address("tilde", step=self._read_number())
        if char == "$":
            self.pos += 1
            return _Address("last")
        if char == "/" or self.text.startswith("\\c", self.pos) or (
            char == "\\" and self.pos + 1 < len(self.text)
        ):
            return self._parse_regex_address()
        return None

    def _parse_regex_address(self) -> _Address:
        if self.text.startswith("\\c", self.pos):
            # \cRE：正则一直到行尾（GNU 行为，后面不能再跟命令）
            self.pos += 2
            start = self.pos
            while self.pos < len(self.text) and self.text[self.pos] != "\n":
                self.pos += 1
            pattern = self.text[start : self.pos]
            return _Address("regex", regex=self._compile(pattern))
        if self.text[self.pos] == "\\":
            # \|RE| 这种写法：分隔符可以是任意字符
            delimiter = self.text[self.pos + 1]
            self.pos += 2
        else:
            delimiter = self.text[self.pos]
            self.pos += 1
        pattern = self._read_delimited(delimiter)
        return _Address("regex", regex=self._compile(pattern))

    def _read_delimited(self, delimiter: str) -> str:
        """读到未转义的分隔符为止；被转义的分隔符还原成字面量。"""
        out: list[str] = []
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char == "\\" and self.pos + 1 < len(self.text):
                nxt = self.text[self.pos + 1]
                if nxt == delimiter:
                    out.append(delimiter)
                    self.pos += 2
                    continue
                out.append(char)
                out.append(nxt)
                self.pos += 2
                continue
            if char == delimiter:
                self.pos += 1
                return "".join(out)
            out.append(char)
            self.pos += 1
        raise UsageError(f"命令没有闭合，缺少分隔符 '{delimiter}'")

    def _compile(self, pattern: str) -> re.Pattern[str]:
        source = _translate_posix_classes(pattern)
        if not self.extended:
            source = _translate_bre(source)
        try:
            return re.compile(source, re.MULTILINE)
        except re.error as exc:
            raise UsageError(f"无效的正则表达式 '{pattern}': {exc}") from exc

    # -- 各命令的参数 ---------------------------------------------------

    def _parse_payload(self, command: _Command) -> None:
        name = command.name
        if name == "s":
            command.payload = self._parse_substitution()
            return
        if name == "y":
            command.payload = self._parse_transliterate()
            return
        if name in ("a", "i", "c"):
            command.payload = self._parse_text_block()
            return
        if name in ("b", "t", "T"):
            command.payload = self._read_label()
            return
        if name == "q":
            start = self.pos
            while self.pos < len(self.text) and self.text[self.pos].isspace():
                self.pos += 1
            digits = self.pos
            while self.pos < len(self.text) and self.text[self.pos].isdigit():
                self.pos += 1
            if digits == self.pos:
                self.pos = start
                command.payload = 0
            else:
                command.payload = int(self.text[digits : self.pos])
            return
        if name in ("p", "d", "n", "N", "=", "Q"):
            return
        if name in _UNSUPPORTED_COMMANDS:
            raise UsageError(f"暂不支持 sed 指令 {name}（{_UNSUPPORTED_COMMANDS[name]}）")
        raise UsageError(f"未知的 sed 指令 '{name}'")

    def _parse_substitution(self) -> _Substitution:
        if self.pos >= len(self.text):
            raise UsageError("`s' 命令没有闭合")
        delimiter = self.text[self.pos]
        if delimiter.isalnum() or delimiter.isspace():
            raise UsageError(f"`s' 命令的分隔符 '{delimiter}' 不合法")
        self.pos += 1
        pattern = self._read_delimited(delimiter)
        replacement = self._read_delimited(delimiter)
        flags_text = ""
        # 标志是一串字母数字，遇到空格、分号、右花括号或换行就停
        while self.pos < len(self.text) and self.text[self.pos].isalnum():
            flags_text += self.text[self.pos]
            self.pos += 1
        return _build_substitution(pattern, replacement, flags_text, self.extended)

    def _parse_transliterate(self) -> tuple[str, str]:
        if self.pos >= len(self.text):
            raise UsageError("`y' 命令没有闭合")
        delimiter = self.text[self.pos]
        self.pos += 1
        source = self._read_delimited(delimiter)
        target = self._read_delimited(delimiter)
        if len(source) != len(target):
            raise UsageError("`y' 命令的两个字符串长度不同")
        return source, target

    def _parse_text_block(self) -> list[str]:
        """读取 a / i / c 后面要插入的文本。"""
        # GNU 的反斜杠续行形式：a\\ + 换行 + 若干行
        if self.text.startswith("\\\n", self.pos) or self.text.startswith("\\\r\n", self.pos):
            self.pos += 1
            lines: list[str] = []
            while True:
                if self.pos >= len(self.text):
                    break
                start = self.pos
                while self.pos < len(self.text) and self.text[self.pos] != "\n":
                    self.pos += 1
                line = self.text[start : self.pos]
                if self.pos < len(self.text):
                    self.pos += 1
                if line.endswith("\\"):
                    lines.append(line[:-1])
                    continue
                lines.append(line)
                break
            return [_expand_text_escapes(line) for line in lines]
        # GNU 的单行形式：a 文本（也接受 a\\文本 这种同行写法）
        start = self.pos
        while self.pos < len(self.text) and not self._at_separator():
            self.pos += 1
        text = self.text[start : self.pos]
        if text.startswith("\\"):
            text = text[1:]
        if text.startswith(" "):
            text = text[1:]
        return [_expand_text_escapes(text)] if text else []


def _expand_text_escapes(text: str) -> str:
    """处理 a / i / c 文本里的转义：\\n 换行、\\t 制表符、\\\\ 反斜杠。"""
    out: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == "\\" and index + 1 < length:
            nxt = text[index + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            elif nxt == "\\":
                out.append("\\")
            else:
                out.append(char)
                out.append(nxt)
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _build_substitution(
    pattern: str, replacement: str, flags_text: str, extended: bool
) -> _Substitution:
    source = _translate_posix_classes(pattern)
    if not extended:
        source = _translate_bre(source)
    ignore_case = False
    global_flag = False
    print_flag = False
    occurrence = 0
    for flag in flags_text:
        if flag == "g":
            global_flag = True
        elif flag == "p":
            print_flag = True
        elif flag in ("i", "I"):
            ignore_case = True
        elif flag.isdigit():
            if occurrence:
                raise UsageError("`s' 命令只能给一个匹配序号")
            occurrence = int(flag)
            if occurrence == 0:
                raise UsageError("`s' 命令的匹配序号不能是 0")
        elif flag in ("w", "e"):
            raise UsageError(f"暂不支持 `s' 命令的 {flag} 标志")
        else:
            raise UsageError(f"`s' 命令不支持的标志 '{flag}'")
    regex_flags = re.MULTILINE | (re.IGNORECASE if ignore_case else 0)
    try:
        regex = re.compile(source, regex_flags)
    except re.error as exc:
        raise UsageError(f"无效的正则表达式 '{pattern}': {exc}") from exc
    chunks = _parse_replacement(replacement)
    return _Substitution(
        regex=regex,
        chunks=chunks,
        global_flag=global_flag,
        print_flag=print_flag,
        occurrence=occurrence,
    )


def _parse_replacement(text: str) -> list[tuple[str, str, int]]:
    """把替换串拆成 (kind, value, mode) 列表。

    kind 取 text / amp / ref；mode 表示大小写转换方式。
    """
    items: list[tuple[str, str, int]] = []
    buffer: list[str] = []
    mode = _MODE_NONE
    once = _MODE_NONE

    def take_mode() -> int:
        """取本次片段用的大小写模式，一次性的 \\u / \\l 用完即失效。"""
        nonlocal once
        effective = once if once != _MODE_NONE else mode
        once = _MODE_NONE
        return effective

    def flush() -> None:
        if not buffer:
            return
        items.append(("text", "".join(buffer), take_mode()))
        buffer.clear()

    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == "\\" and index + 1 < length:
            nxt = text[index + 1]
            if nxt in "ULulE":
                flush()
                if nxt == "E":
                    mode = _MODE_NONE
                    once = _MODE_NONE
                elif nxt == "U":
                    mode = _MODE_UPPER
                    once = _MODE_NONE
                elif nxt == "L":
                    mode = _MODE_LOWER
                    once = _MODE_NONE
                elif nxt == "u":
                    once = _MODE_UPPER_ONCE
                else:
                    once = _MODE_LOWER_ONCE
                index += 2
                continue
            flush()
            if nxt == "n":
                items.append(("text", "\n", take_mode()))
            elif nxt == "t":
                items.append(("text", "\t", take_mode()))
            elif nxt == "r":
                items.append(("text", "\r", take_mode()))
            elif nxt == "a":
                items.append(("text", "\a", take_mode()))
            elif nxt == "f":
                items.append(("text", "\f", take_mode()))
            elif nxt == "v":
                items.append(("text", "\v", take_mode()))
            elif nxt == "&":
                items.append(("amp", "", take_mode()))
            elif nxt.isdigit():
                items.append(("ref", nxt, take_mode()))
            else:
                items.append(("text", nxt, take_mode()))
            index += 2
            continue
        if char == "&":
            flush()
            items.append(("amp", "", take_mode()))
            index += 1
            continue
        buffer.append(char)
        index += 1
    flush()
    return items


def _apply_mode(text: str, mode: int) -> str:
    if mode == _MODE_UPPER:
        return text.upper()
    if mode == _MODE_LOWER:
        return text.lower()
    if mode == _MODE_UPPER_ONCE:
        return text[:1].upper() + text[1:]
    if mode == _MODE_LOWER_ONCE:
        return text[:1].lower() + text[1:]
    return text


# --------------------------------------------------------------------------
# BRE 翻译
# --------------------------------------------------------------------------

_BRE_GROUP_OPENERS = "(|"

# POSIX 字符类：Python 的 re 不认，翻译成等价的范围写法
_POSIX_CLASSES = {
    "alpha": "a-zA-Z",
    "digit": "0-9",
    "alnum": "a-zA-Z0-9",
    "upper": "A-Z",
    "lower": "a-z",
    "space": r" \t\n\r\f\v",
    "blank": r" \t",
    "punct": r"!\"#$%&'()*+,-./:;<=>?@\[\\\]^_`{|}~",
    "print": r"\x20-\x7e",
    "graph": r"\x21-\x7e",
    "cntrl": r"\x00-\x1f\x7f",
    "xdigit": "0-9A-Fa-f",
}


def _translate_posix_classes(pattern: str) -> str:
    """把 [[:alpha:]] 这类 POSIX 字符类换成等价的范围写法。"""

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        return _POSIX_CLASSES.get(name, match.group(0))

    return re.sub(r"\[:(\w+):\]", replace, pattern)


def _translate_bre(pattern: str) -> str:
    """把 GNU 基本正则翻译成 Python 正则。

    BRE 里 ``\\(`` ``\\)`` 是分组、``\\|`` 是或、``\\{`` ``\\}`` 是区间、
    ``\\+`` ``\\?`` 是量词；未转义的 ``( ) { } | + ?`` 都是字面量；
    行首（或分组之后）的 ``*`` 也是字面量。
    """
    out: list[str] = []
    index = 0
    length = len(pattern)
    after_group = True  # 下一个 * 是否为字面量
    while index < length:
        char = pattern[index]
        if char == "\\":
            if index + 1 >= length:
                raise UsageError("正则以孤立的反斜杠结尾")
            nxt = pattern[index + 1]
            if nxt in "(){}|+?":
                out.append(nxt)
                after_group = nxt in _BRE_GROUP_OPENERS
            elif nxt in "<>":
                out.append(r"\b")
                after_group = False
            elif nxt in "bBwWsS":
                out.append("\\" + nxt)
                after_group = False
            else:
                out.append("\\" + nxt)
                after_group = False
            index += 2
            continue
        if char == "*" and after_group:
            out.append(r"\*")
            after_group = False
            index += 1
            continue
        if char in "(){}|+?":
            out.append("\\" + char)
            after_group = False
            index += 1
            continue
        out.append(char)
        after_group = False
        index += 1
    return "".join(out)


# --------------------------------------------------------------------------
# 输入源
# --------------------------------------------------------------------------


class _LineSource:
    """按行喂数据，并能回答「当前行是不是最后一行」。

    靠一行前瞻判断末尾，这样 ``$`` 地址不用先把整个文件读进内存。
    喂进来的行保留行尾换行符，源会记住最后一行是不是缺换行。
    """

    def __init__(self, lines: Iterable[str], separator: str = "\n") -> None:
        self._iterator = iter(lines)
        self._separator = separator
        self._buffer: str | None = None
        self._has_buffer = False
        self._number = 0
        self._is_last = False
        self._last_has_newline = True

    def next_line(self) -> str | None:
        if not self._has_buffer:
            try:
                self._buffer = next(self._iterator)
            except StopIteration:
                self._is_last = True
                return None
            self._has_buffer = True
        raw = self._buffer
        self._has_buffer = False
        self._number += 1
        try:
            self._buffer = next(self._iterator)
            self._has_buffer = True
        except StopIteration:
            self._has_buffer = False
            self._is_last = True
        else:
            self._is_last = False
        if raw.endswith(self._separator):
            text = raw[: -len(self._separator)]
            self._last_has_newline = True
        else:
            text = raw
            self._last_has_newline = False
        return text

    @property
    def number(self) -> int:
        return self._number

    @property
    def is_last(self) -> bool:
        return self._is_last

    @property
    def last_has_newline(self) -> bool:
        return self._last_has_newline


class _Writer:
    """逐行输出，并把「最后一行没有换行」这个细节保留下来。

    同一行只写一次换行，所以末行缺换行时不会多补一个。
    """

    def __init__(self, write: Callable[[str], None], separator: str = "\n") -> None:
        self._write = write
        self._separator = separator
        self._pending: tuple[str, bool] | None = None

    def write(self, text: str, newline: bool = True) -> None:
        if self._pending is not None:
            body, had_newline = self._pending
            self._write(body + (self._separator if had_newline else ""))
        self._pending = (text, newline)

    def close(self) -> None:
        if self._pending is not None:
            body, had_newline = self._pending
            self._write(body + (self._separator if had_newline else ""))
            self._pending = None


# --------------------------------------------------------------------------
# 执行引擎
# --------------------------------------------------------------------------


class _Engine:
    def __init__(
        self,
        commands: Sequence[_Command],
        labels: dict[str, int],
        quiet: bool,
    ) -> None:
        self.commands = commands
        self.labels = labels
        self.quiet = quiet
        self.pattern = ""
        self.substituted = False
        self.appends: list[str] = []
        self.inserts: list[str] = []
        self.quit_code = 0
        self.quit_now = False
        self._no_newline = False
        # 命令块每轮都要重新判定一次地址
        self.blocks: list[_BlockState] = []
        seen: set[int] = set()
        for command in commands:
            block = command.block
            if block is not None and id(block) not in seen:
                seen.add(id(block))
                self.blocks.append(block)

    # -- 主循环 ---------------------------------------------------------

    def run(self, source: _LineSource, writer: _Writer) -> int:
        while not self.quit_now:
            line = source.next_line()
            if line is None:
                break
            self._run_cycle(line, source, writer)
            if self.quit_now:
                break
        writer.close()
        return self.quit_code

    def _run_cycle(self, line: str, source: _LineSource, writer: _Writer) -> None:
        self.pattern = line
        self.substituted = False
        self.appends = []
        self.inserts = []
        self._no_newline = source.is_last and not source.last_has_newline
        for block in self.blocks:
            block.matched = None
        index = 0
        while index < len(self.commands):
            command = self.commands[index]
            if not self._address_matches(command, source):
                index += 1
                continue
            action = self._execute(command, source, writer)
            if action == "jump":
                index = self._target_index(command.payload)
                continue
            if action == "quit":
                self.quit_now = True
                return
            if action == "stop":
                # 结束脚本，但这一轮的模式空间照常打印
                self.quit_now = True
                break
            if action == "cycle":
                return
            index += 1
        self._flush(writer)

    def _flush(self, writer: _Writer) -> None:
        for text in self.inserts:
            writer.write(text)
        if not self.quiet:
            writer.write(self.pattern, newline=not self._no_newline)
        for text in self.appends:
            writer.write(text)

    # -- 地址求值 -------------------------------------------------------

    def _address_matches(self, command: _Command, source: _LineSource) -> bool:
        # 命令块：块的地址只在进入块时求一次（GNU 把整块编译成一条命令）
        if command.block is not None:
            if command.block.matched is None:
                command.block.matched = self._match_block(command.block, source)
            if not command.block.matched:
                return False
        addr1 = command.addr1
        negate = command.negate
        if addr1 is None:
            # 没有地址时 ! 表示「永远不执行」
            return not negate
        if command.addr2 is None:
            matched = self._match_address(addr1, command, source)
        else:
            matched = self._match_range(command, source)
        return (not matched) if negate else matched

    def _match_block(self, block: _BlockState, source: _LineSource) -> bool:
        if block.addr1 is None:
            matched = True
        elif block.addr2 is None:
            matched = self._match_address(block.addr1, block, source)
        else:
            matched = self._match_range(block, source)
        return (not matched) if block.negate else matched

    def _match_range(self, command: Any, source: _LineSource) -> bool:
        """范围地址求值，同时维护范围状态。"""
        addr1 = command.addr1
        end = command.addr2
        assert addr1 is not None and end is not None
        if not command.in_range:
            if not self._match_address(addr1, command, source):
                return False
            command.in_range = True
            command.base_line = source.number
            command.matches = 0
            if end.kind == "plus":
                command.end_line = source.number + end.number
            # 数字终点在起始行就命中；正则终点不在同一行上试（GNU 行为）
            if end.kind == "line" and end.number == source.number:
                command.in_range = False
            return True
        if end.kind == "plus":
            if source.number <= command.end_line:
                return True
            command.in_range = False
            return False
        if end.kind == "tilde":
            if source.number > command.base_line and self._tilde_reached(command, end, source):
                command.in_range = False
            return True
        if self._match_address(end, command, source):
            command.in_range = False
        return True

    def _tilde_reached(self, command: _Command, end: _Address, source: _LineSource) -> bool:
        """addr1,~step：从起点到「按步长算的下一个同型行」。

        起点是行号时按行号差取模；起点是正则时数着第几次匹配。
        """
        step = max(end.step, 1)
        addr1 = command.addr1
        if addr1 is not None and addr1.kind == "regex":
            if addr1.regex is None or addr1.regex.search(self.pattern) is None:
                return False
            command.matches += 1
            return command.matches > step
        offset = source.number - command.base_line
        return offset > 0 and offset % step == 0

    def _match_address(self, address: _Address, command: Any, source: _LineSource) -> bool:
        if address.kind == "line":
            # 地址 0 表示「第一行之前」，所以 0,/re/ 这种范围从第 1 行开始
            if address.number == 0:
                return source.number == 1
            return source.number == address.number
        if address.kind == "last":
            return source.is_last
        if address.kind == "regex":
            return address.regex is not None and address.regex.search(self.pattern) is not None
        if address.kind == "step":
            if command.base_line == 0:
                if source.number != address.number:
                    return False
                command.base_line = source.number
                return True
            offset = source.number - command.base_line
            return offset >= 0 and offset % max(address.step, 1) == 0
        return False

    # -- 命令执行 -------------------------------------------------------

    def _execute(self, command: _Command, source: _LineSource, writer: _Writer) -> str:
        name = command.name
        if name == "s":
            self._do_substitute(command, writer)
            return "next"
        if name == "p":
            writer.write(self.pattern, newline=not self._no_newline)
            return "next"
        if name == "d":
            return "cycle"
        if name == "n":
            # GNU 的 n：先把当前模式空间打印出来（安静模式下不打印），
            # 再读下一行替换模式空间，接着往下走脚本。
            if not self.quiet:
                writer.write(self.pattern, newline=not self._no_newline)
            line = source.next_line()
            if line is None:
                self.quit_now = True
                return "quit"
            self.pattern = line
            self._no_newline = source.is_last and not source.last_has_newline
            return "next"
        if name == "N":
            line = source.next_line()
            if line is None:
                # 读到末尾：脚本就此结束，但当前模式空间照常打印
                self.quit_now = True
                return "stop"
            self.pattern = self.pattern + "\n" + line
            self._no_newline = source.is_last and not source.last_has_newline
            return "next"
        if name == "=":
            writer.write(str(source.number))
            return "next"
        if name == "q":
            self.quit_code = int(command.payload or 0)
            self._flush(writer)
            self.quit_now = True
            return "quit"
        if name == "Q":
            self.quit_now = True
            return "quit"
        if name == "y":
            source_text, target_text = command.payload  # type: ignore[misc]
            table = str.maketrans(source_text, target_text)
            self.pattern = self.pattern.translate(table)
            return "next"
        if name == "a":
            self.appends.extend(command.payload)  # type: ignore[arg-type]
            return "next"
        if name == "i":
            self.inserts.extend(command.payload)  # type: ignore[arg-type]
            return "next"
        if name == "c":
            text = "\n".join(command.payload)  # type: ignore[arg-type]
            for piece in text.split("\n"):
                writer.write(piece)
            return "cycle"
        if name == "b":
            return "jump"
        if name == "t":
            if self.substituted:
                self.substituted = False
                return "jump"
            return "next"
        if name == "T":
            if not self.substituted:
                return "jump"
            return "next"
        raise UsageError(f"未知的 sed 指令 '{name}'")

    def _do_substitute(self, command: _Command, writer: _Writer) -> None:
        substitution: _Substitution = command.payload  # type: ignore[assignment]
        regex = substitution.regex
        if substitution.global_flag:
            result = self._global_substitute(regex, substitution)
        elif substitution.occurrence > 1:
            result = self._replace_nth(regex, substitution)
        else:
            match = regex.search(self.pattern)
            if match is None:
                return
            result = (
                self.pattern[: match.start()]
                + self._expand(match, substitution.chunks)
                + self.pattern[match.end() :]
            )
        if result != self.pattern:
            self.substituted = True
            self.pattern = result
            if substitution.print_flag:
                writer.write(self.pattern, newline=not self._no_newline)

    def _iter_matches(self, regex: re.Pattern[str], space: str) -> Iterator[re.Match[str]]:
        """按 GNU 的规则产出匹配。

        GNU 的替换里，空匹配紧跟在非空匹配后面时不算一次匹配
        （``s/.*/X/g`` 只换一个 X，而不是两个），空匹配之后搜索位置前进一个字符。
        Python 的 re 不这么干，得自己走一遍。
        """
        position = 0
        length = len(space)
        previous_end = -1
        previous_empty = True
        while position <= length:
            match = regex.search(space, position)
            if match is None:
                return
            start, end = match.span()
            if start == end:
                if not previous_empty and end == previous_end:
                    position = end + 1
                    continue
                previous_empty = True
                previous_end = end
                position = end + 1
            else:
                previous_empty = False
                previous_end = end
                position = end
            yield match

    def _global_substitute(self, regex: re.Pattern[str], substitution: _Substitution) -> str:
        pieces: list[str] = []
        cursor = 0
        for match in self._iter_matches(regex, self.pattern):
            pieces.append(self.pattern[cursor : match.start()])
            pieces.append(self._expand(match, substitution.chunks))
            cursor = match.end()
        pieces.append(self.pattern[cursor:])
        return "".join(pieces)

    def _replace_nth(self, regex: re.Pattern[str], substitution: _Substitution) -> str:
        pieces: list[str] = []
        cursor = 0
        for index, match in enumerate(self._iter_matches(regex, self.pattern), 1):
            if index == substitution.occurrence:
                pieces.append(self.pattern[cursor : match.start()])
                pieces.append(self._expand(match, substitution.chunks))
                cursor = match.end()
                break
        pieces.append(self.pattern[cursor:])
        return "".join(pieces)

    def _expand(self, match: re.Match[str], chunks: Sequence[tuple[str, str, int]]) -> str:
        out: list[str] = []
        for kind, value, mode in chunks:
            if kind == "text":
                out.append(_apply_mode(value, mode))
            elif kind == "amp":
                out.append(_apply_mode(match.group(0), mode))
            else:
                index = int(value)
                try:
                    group = match.group(index) or ""
                except (IndexError, re.error):
                    group = ""
                out.append(_apply_mode(group, mode))
        return "".join(out)

    def _target_index(self, label: object) -> int:
        if not label:
            return len(self.commands)
        key = str(label)
        if key not in self.labels:
            raise UsageError(f"找不到标签 '{key}'")
        return self.labels[key]


# --------------------------------------------------------------------------
# 编码判定
# --------------------------------------------------------------------------


def _candidate_encodings() -> list[str]:
    candidates: list[str] = []
    preferred = locale.getpreferredencoding(False)
    for encoding in ("utf-8", preferred, *_FALLBACK_ENCODINGS):
        if encoding and encoding not in candidates:
            candidates.append(encoding)
    return candidates


def _decode_sample(sample: bytes, encoding: str) -> str | None:
    try:
        decoder = codecs.getincrementaldecoder(encoding)(errors="strict")
        return decoder.decode(sample, final=False)
    except (UnicodeDecodeError, LookupError, ValueError):
        return None


def _text_score(text: str) -> float:
    if not text:
        return 0.0
    score = 0.0
    for char in text:
        code = ord(char)
        if 32 <= code < 127:
            score += 1.0
        elif any(low <= code <= high for low, high in _CJK_RANGES):
            score += 3.0
        elif 0x3000 <= code <= 0x303F or 0xFF00 <= code <= 0xFFEF:
            score += 1.0
        elif code in (9, 10, 13):
            score += 0.5
        elif code >= 0x80:
            score += 0.2
    return score / len(text)


def _detect_encoding(sample: bytes) -> str:
    """按文本可信度选编码，而不是取第一个能解的。

    系统首选编码在英文 Windows 上是 cp1252，它几乎不报错，能把 GBK 字节解成乱码，
    按顺序取第一个可解码的编码会让中文内容彻底搜不到。
    """
    if b"\x00" in sample:
        return "latin-1"  # 二进制文件按字节处理，一个字节一个字符
    best_encoding = "utf-8"
    best_score = -1.0
    for encoding in _candidate_encodings():
        text = _decode_sample(sample, encoding)
        if text is None:
            continue
        score = _text_score(text)
        if score > best_score + _SCORE_MARGIN:
            best_score = score
            best_encoding = encoding
    return best_encoding


# --------------------------------------------------------------------------
# 读文件
# --------------------------------------------------------------------------


def _split_raw_lines(text: str, separator: str = "\n") -> list[str]:
    """按分隔符切行，保留分隔符，方便判断最后一行有没有换行。"""
    parts = text.split(separator)
    out: list[str] = []
    for index, part in enumerate(parts):
        if index < len(parts) - 1:
            out.append(part + separator)
        elif part:
            out.append(part)
    return out


def _read_file_lines(path: Path, args: argparse.Namespace) -> tuple[list[str], str]:
    """读文件并解码，返回 (原始行列表, 编码)。

    行尾的换行符要留着：输入源靠它判断「最后一行有没有换行」。
    """
    raw = path.read_bytes()
    encoding = _detect_encoding(raw[:_SNIFF_SIZE])
    text = raw.decode(encoding, errors="replace")
    if args.null_data:
        return _split_raw_lines(text, "\x00"), encoding
    lines = _split_raw_lines(text, "\n")
    if not args.binary:
        # 文本模式下去掉行尾的 CR（GNU sed 在 Windows 上默认按文本模式读）
        lines = [line[:-2] + "\n" if line.endswith("\r\n") else line for line in lines]
    return lines, encoding


def _stdin_lines(ctx: RunContext, args: argparse.Namespace) -> list[str]:
    if ctx.stdin is None:
        return []
    data = ctx.stdin.read()
    if args.null_data:
        return _split_raw_lines(data, "\x00")
    lines = _split_raw_lines(data, "\n")
    if not args.binary:
        lines = [line[:-2] + "\n" if line.endswith("\r\n") else line for line in lines]
    return lines


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    prog = command_prog("sed")
    parser = argparse.ArgumentParser(
        prog=prog,
        description="按脚本对输入做流式编辑",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            f"  {prog} 's/foo/bar/g' w2l/cli.py\n"
            f"  {prog} -n '/TODO/p' README.md\n"
            f"  {prog} -e 's/a/b/' -e 's/c/d/' notes.txt\n"
            f"  {prog} -i 's/[ \\t]*$//' app.log\n"
            f"  {prog} '2,5d' input.txt\n"
        ),
    )
    parser.add_argument("script", nargs="?", help="要执行的脚本")
    parser.add_argument("files", nargs="*", help="输入文件，不给则读标准输入")
    parser.add_argument("-e", "--expression", action="append", default=[], metavar="SCRIPT", help="追加一段脚本")
    parser.add_argument("-f", "--file", action="append", default=[], metavar="FILE", help="从文件读脚本")
    parser.add_argument("-n", "--quiet", "--silent", action="store_true", help="不自动打印每一行")
    parser.add_argument("-r", "-E", "--regexp-extended", action="store_true", help="使用扩展正则 ERE，默认基本正则 BRE")
    parser.add_argument("-s", "--separate", action="store_true", help="每个文件单独处理，不拼成一条流")
    parser.add_argument("--in-place", action="store_true", help="原地修改文件")
    parser.add_argument(
        "--in-place-suffix",
        dest="in_place_suffix",
        default=None,
        metavar="SUFFIX",
        help="原地修改时备份文件的后缀（等价于 GNU 的 -i.后缀）",
    )
    parser.add_argument("-b", "--binary", action="store_true", help="二进制模式，保留行尾的 CR")
    parser.add_argument("-z", "--null-data", action="store_true", help="用 NUL 而不是换行分隔输入行")
    parser.add_argument("--follow-symlinks", action="store_true", help="原地修改时跟随符号链接（Windows 上无效）")
    parser.add_argument("--unbuffered", "-u", action="store_true", help="少缓冲地读写（接受但不改变行为）")
    parser.add_argument("--posix", action="store_true", help="按 POSIX 模式（接受但不改变行为）")
    parser.add_argument("--debug", action="store_true", help="打印执行注解（接受但不改变行为）")
    parser.add_argument("--sandbox", action="store_true", help="沙箱模式，禁用 e/r/w（接受但不改变行为）")
    return parser


def split_inplace(argv: Sequence[str]) -> list[str]:
    """把 -i 及其后缀从短选项簇里拆出来。

    GNU 允许 ``-ni.bak`` 这种写法：``i`` 后面的部分整个当成备份后缀。
    后缀不能单独作为一个参数写（``-i .bak`` 在 GNU 里会把 .bak 当成文件名），
    所以这里统一改写成 --in-place 与 --in-place-suffix 两个独立选项。
    """
    out: list[str] = []
    for token in argv:
        if token == "--in-place":
            out.append(token)
            continue
        if token.startswith("--in-place="):
            out.append("--in-place-suffix=" + token[len("--in-place=") :])
            continue
        if not token.startswith("-") or token.startswith("--") or token == "-":
            out.append(token)
            continue
        index = 1
        while index < len(token):
            char = token[index]
            if char in "ef":
                out.append("-" + char + token[index + 1 :])
                break
            if char == "i":
                suffix = token[index + 1 :]
                if suffix:
                    out.append("--in-place-suffix=" + suffix)
                else:
                    out.append("--in-place")
                break
            out.append("-" + char)
            index += 1
    return out


def _resolve(ctx: RunContext, name: str) -> Path:
    """相对路径按运行上下文里的当前目录解析。"""
    path = Path(name)
    if path.is_absolute():
        return path
    return ctx.cwd / path


@command("sed", "按脚本对输入做流式编辑（GNU sed 风格子集）", build_parser)
def sed(args: argparse.Namespace, ctx: RunContext) -> int:
    parser_scripts = list(args.expression)
    for script_file in args.file:
        parser_scripts.append(_read_script_file(ctx, script_file))

    if parser_scripts:
        script_text = "\n".join(parser_scripts)
        files: list[str] = []
        if args.script is not None:
            files.append(args.script)
        files.extend(args.files)
    else:
        if args.script is None:
            raise UsageError("缺少脚本：用 -e/-f 指定，或把脚本作为第一个参数")
        script_text = args.script
        files = list(args.files)

    commands, labels = _ScriptParser(script_text, args.regexp_extended).parse()
    engine = _Engine(commands, labels, args.quiet)

    in_place = args.in_place or args.in_place_suffix is not None
    suffix = args.in_place_suffix or ""

    if not files:
        if in_place:
            raise UsageError("原地修改必须给出文件")
        separator = "\x00" if args.null_data else "\n"
        writer = _Writer(ctx.stdout.write, separator)
        engine.run(_LineSource(_stdin_lines(ctx, args), separator), writer)
        return engine.quit_code

    had_error = False
    if in_place or args.separate:
        for name in files:
            path = _resolve(ctx, name)
            try:
                if path.is_dir():
                    ctx.stderr.write(f"{name}: 是一个目录\n")
                    had_error = True
                    continue
                if in_place:
                    _process_in_place(engine, path, args, suffix)
                else:
                    _process_file(engine, path, args, ctx)
            except OSError as exc:
                ctx.stderr.write(f"{name}: {exc.strerror or exc}\n")
                had_error = True
    else:
        # 默认把所有文件拼成一条流，行号连续
        collected: list[str] = []
        encoding = "utf-8"
        for name in files:
            path = _resolve(ctx, name)
            try:
                if path.is_dir():
                    ctx.stderr.write(f"{name}: 是一个目录\n")
                    had_error = True
                    continue
                lines, encoding = _read_file_lines(path, args)
                collected.extend(lines)
            except OSError as exc:
                ctx.stderr.write(f"{name}: {exc.strerror or exc}\n")
                had_error = True
        separator = "\x00" if args.null_data else "\n"
        writer = _Writer(ctx.stdout.write, separator)
        engine.run(_LineSource(collected, separator), writer)
    if had_error:
        return 2
    return engine.quit_code


def _read_script_file(ctx: RunContext, name: str) -> str:
    try:
        return _resolve(ctx, name).read_text(encoding="utf-8")
    except OSError as exc:
        raise UsageError(f"读不了脚本文件 {name}: {exc.strerror or exc}") from exc
    except UnicodeDecodeError as exc:
        raise UsageError(f"脚本文件 {name} 不是 UTF-8 文本") from exc


def _process_file(engine: _Engine, path: Path, args: argparse.Namespace, ctx: RunContext) -> None:
    lines, _ = _read_file_lines(path, args)
    separator = "\x00" if args.null_data else "\n"
    writer = _Writer(ctx.stdout.write, separator)
    engine.run(_LineSource(lines, separator), writer)


def _process_in_place(engine: _Engine, path: Path, args: argparse.Namespace, suffix: str) -> None:
    lines, encoding = _read_file_lines(path, args)
    separator = "\x00" if args.null_data else "\n"
    collected: list[str] = []
    writer = _Writer(collected.append, separator)
    engine.run(_LineSource(lines, separator), writer)
    payload = "".join(collected)
    if suffix:
        backup = path.with_name(path.name + suffix)
        backup.write_bytes(path.read_bytes())
    temporary = path.with_name(path.name + ".w2l-sed.tmp")
    temporary.write_bytes(payload.encode(encoding, errors="replace"))
    os.replace(temporary, path)


# --------------------------------------------------------------------------
# 给测试与探针用的薄封装
# --------------------------------------------------------------------------


def run_sed(
    argv: Sequence[str],
    cwd: Path | None = None,
    stdin_text: str = "",
) -> tuple[int, str, str]:
    """跑一次 sed 指令，返回 (退出码, 标准输出, 标准错误)。"""
    import io

    namespace = build_parser().parse_args(split_inplace(list(argv)))
    out, err = io.StringIO(), io.StringIO()
    context = RunContext(
        cwd=cwd or Path.cwd(),
        stdout=out,
        stderr=err,
        stdin=io.StringIO(stdin_text),
    )
    code = sed(namespace, context)
    return code, out.getvalue(), err.getvalue()
