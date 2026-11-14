"""awk-lite：按字段取值（GNU awk 风格子集）。

覆盖 GNU awk 日常最常用的一小块：

- 动作：``{print $1}``、``{print $NF, $2}``、``{print}``（等价于 ``{print $0}``）
- 模式：``/ERROR/``（按正则筛行）、``/ERROR/ {print $1}``
- 字段分隔符：``-F,``；默认按空白串（空格与制表符的连续段）切分
- 内建变量：``NR``、``NF``、``FNR``、``FILENAME``、``FS``、``OFS``、``ORS``
- 变量赋值：``-v name=value``

不支持的写法（算术、字符串拼接、BEGIN/END、函数、数组、printf 等）一律明确报错，
不静默忽略。文件按顺序处理，行号 ``NR`` 连续、``FNR`` 每个文件重新计数。

退出码：0 正常处理完（没有输出也是 0，与 GNU awk 一致），2 用法或运行错误。
"""

from __future__ import annotations

import argparse
import codecs
import locale
import re
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Callable, Iterator, Sequence

from ..context import RunContext
from ..entry import command_prog
from ..errors import UsageError
from ..registry import command

_SNIFF_SIZE = 8192
_FALLBACK_ENCODINGS = ("utf-8", "gb18030", "latin-1")
_SCORE_MARGIN = 0.3
_CJK_RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF))
_DEFAULT_OFS = " "
_DEFAULT_ORS = "\n"
_IDENT = re.compile(r"[^\W\d]\w*", re.UNICODE)

# GNU awk 默认分隔符认的空白：空格、制表符、换行、回车、竖直制表符、换页符。
# 不用 str.split()，因为它还认 NBSP 之类的 Unicode 空白，GNU 不认。
_WHITESPACE = " \t\n\r\v\f"
_WHITESPACE_RE = re.compile(r"[ \t\n\r\v\f]+")


# --------------------------------------------------------------------------
# 程序结构
# --------------------------------------------------------------------------


@dataclass
class _Item:
    """print 的一个参数。"""

    kind: str  # field / var / number / string
    text: str
    number: float | None = None


@dataclass
class _Program:
    """解析后的 awk 程序。"""

    pattern: re.Pattern[str] | None = None
    items: list[_Item] | None = None  # None 表示裸 print（打整行）


@dataclass
class _Record:
    """一条输入记录及其上下文。"""

    line: str
    fields: list[str]
    nr: int
    fnr: int
    filename: str


# --------------------------------------------------------------------------
# 参数解析
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    prog = command_prog("awk-lite")
    parser = argparse.ArgumentParser(
        prog=prog,
        description="按字段取值：{print $1}、/ERROR/、-F,、-v name=value",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            f"  {prog} '{{print $1}}' app.log\n"
            f"  {prog} -F, '{{print $NF}}' access.csv\n"
            f"  {prog} '/ERROR/ {{print $2}}' app.log\n"
            f"  {prog} -v n=2 '{{print $n}}' app.log\n"
        ),
    )
    parser.add_argument("program", help="要执行的程序，形如 {print $1} 或 /正则/ {print $1}")
    parser.add_argument("files", nargs="*", help="输入文件，不给则读标准输入")
    parser.add_argument(
        "-F",
        "--field-separator",
        dest="field_separator",
        default=None,
        metavar="SEP",
        help="字段分隔符，默认按空白串切分",
    )
    parser.add_argument(
        "-v",
        "--assign",
        dest="assign",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="给变量赋值，可给多次",
    )
    return parser


@command("awk-lite", "按字段取值（GNU awk 风格子集）", build_parser)
def awk_lite(args: argparse.Namespace, ctx: RunContext) -> int:
    program = _parse_program(args.program)
    variables = _parse_assignments(args.assign)

    separator = variables.get("FS")
    if args.field_separator is not None:
        separator = _decode_separator(args.field_separator)
    split = _make_splitter(separator)

    ofs = variables.get("OFS", _DEFAULT_OFS)
    ors = variables.get("ORS", _DEFAULT_ORS)

    files = list(args.files)
    had_error = False
    nr = 0

    if not files:
        for record in _iter_stdin(ctx, split):
            nr += 1
            _emit(record, program, variables, ofs, ors, ctx)
        return 0

    for name in files:
        if name == "-":
            for record in _iter_stdin(ctx, split, nr):
                nr += 1
                _emit(record, program, variables, ofs, ors, ctx)
            continue
        path = _resolve(ctx.cwd, name)
        if path.is_dir():
            ctx.stderr.write(f"{name}: 是一个目录\n")
            had_error = True
            continue
        try:
            handle = path.open("rb")
        except OSError as exc:
            ctx.stderr.write(f"{name}: {exc.strerror or exc}\n")
            had_error = True
            continue
        with handle:
            encoding = _detect_encoding(handle.read(_SNIFF_SIZE))
            handle.seek(0)
            fnr = 0
            for line in _decode_lines(handle, encoding):
                fnr += 1
                nr += 1
                _emit(
                    _Record(line, split(line), nr, fnr, name),
                    program,
                    variables,
                    ofs,
                    ors,
                    ctx,
                )

    return 2 if had_error else 0


# --------------------------------------------------------------------------
# 程序解析
# --------------------------------------------------------------------------


def _parse_program(text: str) -> _Program:
    source = text.strip()
    if not source:
        raise UsageError("程序是空的：写成 {print $1} 或 /正则/ 的形式")

    if source.startswith("{"):
        return _Program(pattern=None, items=_parse_action(source))

    if source.startswith("/"):
        pattern_text, rest = _split_regex(source)
        regex = _compile_regex(pattern_text)
        rest = rest.strip()
        if not rest:
            return _Program(pattern=regex, items=None)
        if not rest.startswith("{"):
            raise UsageError(f"模式后面只跟 {{...}} 动作：{rest!r}")
        return _Program(pattern=regex, items=_parse_action(rest))

    raise UsageError(
        f"看不懂的程序 {text!r}：只支持 {{print ...}} 动作或 /正则/ 模式"
        "（在 Git Bash 里以 / 开头的参数会被 MSYS 改写成路径，试 MSYS_NO_PATHCONV=1）"
    )


def _split_regex(source: str) -> tuple[str, str]:
    """拆出 `/正则/` 里的正则部分，正则里的 `/` 用 `\\/` 转义。"""
    index = 1
    buffer: list[str] = []
    while index < len(source):
        char = source[index]
        if char == "\\" and index + 1 < len(source):
            nxt = source[index + 1]
            if nxt == "/":
                buffer.append("/")
            else:
                buffer.append(char)
                buffer.append(nxt)
            index += 2
            continue
        if char == "/":
            return "".join(buffer), source[index + 1 :]
        buffer.append(char)
        index += 1
    raise UsageError(f"正则没有收尾的 /：{source!r}")


def _compile_regex(pattern: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise UsageError(f"无效的正则表达式 '{pattern}': {exc}") from exc


def _parse_action(source: str) -> list[_Item] | None:
    """解析 `{print ...}` 动作块，返回 print 的参数列表；裸 print 返回 None。"""
    body = _strip_braces(source).strip()
    if body.endswith(";"):
        body = body[:-1].strip()
    if not body:
        raise UsageError("动作块是空的：只支持 print")

    if body.startswith("print("):
        if not body.endswith(")"):
            raise UsageError(f"print 的括号没闭合：{body!r}")
        body = "print " + body[len("print(") : -1]
    elif not body.startswith("print"):
        raise UsageError(f"动作只支持 print：{body!r}")

    rest = body[len("print") :].strip()
    if rest.startswith("(") and rest.endswith(")"):
        rest = rest[1:-1].strip()
    if not rest:
        return None

    items: list[_Item] = []
    for piece in _split_commas(rest):
        items.append(_parse_item(piece))
    return items


def _strip_braces(source: str) -> str:
    if not source.startswith("{") or not source.endswith("}"):
        raise UsageError(f"动作块要用 {{...}} 包起来：{source!r}")
    return source[1:-1]


def _split_commas(text: str) -> list[str]:
    """按顶层逗号切分，字符串字面量里的逗号不算。"""
    parts: list[str] = []
    buffer: list[str] = []
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            buffer.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            buffer.append(char)
            continue
        if char == ",":
            parts.append("".join(buffer))
            buffer = []
            continue
        buffer.append(char)
    parts.append("".join(buffer))
    return parts


def _parse_item(text: str) -> _Item:
    piece = text.strip()
    if not piece:
        raise UsageError("print 的参数是空的")
    if piece.startswith("$"):
        field = piece[1:].strip()
        if not field:
            raise UsageError("字段引用缺少字段号：$")
        if not (field.isdigit() or field == "NF" or _IDENT.fullmatch(field)):
            raise UsageError(f"看不懂的字段引用 {piece!r}")
        return _Item(kind="field", text=field)
    if piece.startswith('"'):
        if len(piece) < 2 or not piece.endswith('"'):
            raise UsageError(f"字符串没闭合：{piece!r}")
        return _Item(kind="string", text=_decode_string(piece[1:-1]))
    if _IDENT.fullmatch(piece):
        return _Item(kind="var", text=piece)
    number = _to_number(piece)
    if number is not None:
        return _Item(kind="number", text=piece, number=number)
    raise UsageError(f"看不懂的 print 参数：{piece!r}")


def _decode_string(text: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            nxt = text[index + 1]
            out.append(
                {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}.get(nxt, "\\" + nxt)
            )
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _parse_assignments(assignments: Sequence[str]) -> dict[str, str]:
    variables: dict[str, str] = {}
    for item in assignments:
        if "=" not in item:
            raise UsageError(f"-v 的参数要写成 name=value：{item!r}")
        name, _, value = item.partition("=")
        name = name.strip()
        if not name:
            raise UsageError(f"-v 的参数要写成 name=value：{item!r}")
        variables[name] = value
    return variables


# --------------------------------------------------------------------------
# 取值
# --------------------------------------------------------------------------


def _emit(
    record: _Record,
    program: _Program,
    variables: dict[str, str],
    ofs: str,
    ors: str,
    ctx: RunContext,
) -> None:
    if program.pattern is not None and program.pattern.search(record.line) is None:
        return
    if program.items is None:
        ctx.stdout.write(record.line + ors)
        return
    pieces = [_value_of(item, record, variables) for item in program.items]
    ctx.stdout.write(ofs.join(pieces) + ors)


def _value_of(item: _Item, record: _Record, variables: dict[str, str]) -> str:
    if item.kind == "string":
        return item.text
    if item.kind == "number":
        return _format_number(item.number or 0.0)
    if item.kind == "var":
        return _lookup(item.text, record, variables)
    return _field_value(item.text, record, variables)


def _lookup(name: str, record: _Record, variables: dict[str, str]) -> str:
    if name == "NR":
        return str(record.nr)
    if name == "NF":
        return str(len(record.fields))
    if name == "FNR":
        return str(record.fnr)
    if name == "FILENAME":
        return record.filename
    if name == "OFS":
        return variables.get("OFS", _DEFAULT_OFS)
    if name == "ORS":
        return variables.get("ORS", _DEFAULT_ORS)
    if name == "FS":
        return variables.get("FS", " ")
    if name in variables:
        return _as_text(variables[name])
    raise UsageError(f"变量 {name!r} 没有赋值：先用 -v {name}=... 赋值")


def _field_value(spec: str, record: _Record, variables: dict[str, str]) -> str:
    if spec == "0":
        return record.line
    if spec.isdigit():
        index = int(spec)
        if index == 0:
            return record.line
        if index > len(record.fields):
            return ""
        return record.fields[index - 1]
    if spec == "NF":
        return _field_value(str(len(record.fields)), record, variables)
    if spec in variables:
        value = variables[spec]
        number = _to_number(value)
        if number is not None:
            return _field_value(str(int(number)), record, variables)
        # 变量不是数字就当字段名；本实现没有具名字段，按整行处理（与 GNU 一致）
        return record.line
    raise UsageError(f"变量 {spec!r} 没有赋值：先用 -v {spec}=... 赋值")


def _as_text(value: str) -> str:
    number = _to_number(value)
    if number is None:
        return value
    return _format_number(number)


def _to_number(text: str) -> float | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError:
        return None


def _format_number(number: float) -> str:
    """按 GNU awk 的 CONVFMT（默认 %.6g）把数字转成字符串。"""
    if number == int(number) and abs(number) < 1e16:
        return str(int(number))
    return "%.6g" % number


# --------------------------------------------------------------------------
# 切分与读取
# --------------------------------------------------------------------------


def _decode_separator(value: str) -> str:
    """-F 的值：转义序列先解开。"""
    out: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value):
            nxt = value[index + 1]
            out.append({"t": "\t", "n": "\n", "r": "\r", "\\": "\\"}.get(nxt, nxt))
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _make_splitter(separator: str | None) -> Callable[[str], list[str]]:
    """按 GNU awk 的规则做切分。

    - 没给分隔符（或者给的是单个空格）：按空白串切，连续空白算一个，两端空白不算字段
    - 单个字符：按字面量切（``.`` 就是一个点，不是任意字符），连续出现切出空字段
    - 多个字符：按正则切（GNU 的规则），所以 ``-F '..'`` 会把每两个字符切一刀
    """
    if separator is None or separator == "" or separator == " ":
        return _split_whitespace
    if len(separator) == 1:
        return lambda line: line.split(separator)
    try:
        pattern = re.compile(separator)
    except re.error as exc:
        raise UsageError(f"无效的分隔符正则 '{separator}': {exc}") from exc
    if pattern.search("") is not None:
        raise UsageError(f"分隔符正则 '{separator}' 能匹配空串，没法用来切字段")
    return lambda line: pattern.split(line)


def _split_whitespace(line: str) -> list[str]:
    stripped = line.strip(_WHITESPACE)
    if not stripped:
        return []
    return _WHITESPACE_RE.split(stripped)


def _resolve(cwd: Path, operand: str) -> Path:
    """相对路径按运行上下文里的当前目录解析，不是按进程的工作目录。"""
    target = Path(operand)
    if not target.is_absolute():
        target = cwd / target
    return target


def _iter_stdin(ctx: RunContext, split: Callable[[str], list[str]], nr: int = 0) -> Iterator[_Record]:
    if ctx.stdin is None:
        raise UsageError("没有可读取的标准输入")
    fnr = 0
    for raw in ctx.stdin:
        line = raw.rstrip("\n").rstrip("\r")
        fnr += 1
        nr += 1
        yield _Record(line, split(line), nr, fnr, "-")


def _decode_lines(handle: IO[bytes], encoding: str) -> Iterator[str]:
    for raw in handle:
        text = raw.decode(encoding, errors="replace")
        if text.endswith("\n"):
            text = text[:-1]
        if text.endswith("\r"):
            text = text[:-1]
        yield text


def _detect_encoding(sample: bytes) -> str:
    """按文本可信度选编码，而不是取第一个能解的。

    与 grep.py / cat.py / sed.py 里同一套判定：系统首选编码在英文 Windows 上
    是 cp1252，它几乎不报错，能把 GBK 字节解成乱码，按顺序取第一个可解码的
    编码会让中文内容彻底搜不到。
    """
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
