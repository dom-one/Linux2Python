#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复算 sed 教程正文里只有文字佐证的数字。

核对器只比对命令块与预期输出块，正文里的数字断言它查不到，
所以要另写脚本逐条复算。

用法：python AI/脚本/_t1012_verify_sed_claims.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

SRC = ROOT / "w2l" / "commands" / "sed.py"
TEST = ROOT / "tests" / "test_sed.py"

failures: list[str] = []
checks = 0


def check(label: str, actual, expected) -> None:
    global checks
    checks += 1
    if actual != expected:
        failures.append(f"{label}: 期望 {expected!r}，实际 {actual!r}")
        print(f"  [FAIL] {label}: 期望 {expected!r}，实际 {actual!r}")
    else:
        print(f"  [ok]   {label} = {actual!r}")


def literal_string(pattern: str, text: str) -> str | None:
    """从源码里取出一个字符串字面量的内容（避免正则里转义元字符出错）。"""
    m = re.search(pattern, text)
    if not m:
        return None
    return m.group(1)


def main() -> int:
    src = SRC.read_text(encoding="utf-8")
    lines = src.splitlines()

    print("一、行数")
    check("sed.py 行数", len(lines), 1390)

    tree = ast.parse(src)
    funcs: dict[str, int] = {}
    classes: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.setdefault(node.name, node.lineno)
        elif isinstance(node, ast.ClassDef):
            classes.setdefault(node.name, node.lineno)

    print("\n二、关键函数的起始行号")
    func_lines = {
        "_parse_address": 228, "_parse_substitution": 339, "_parse_replacement": 466,
        "_translate_bre": 589, "_translate_posix_classes": 579, "_match_range": 832,
        "_tilde_reached": 862, "_match_address": 877, "_execute": 899,
        "_do_substitute": 970, "_iter_matches": 992, "_global_substitute": 1021,
        "_replace_nth": 1031, "_expand": 1043, "_detect_encoding": 1109,
        "_text_score": 1090, "_read_file_lines": 1147, "split_inplace": 1221,
        "build_parser": 1181, "sed": 1266, "run_sed": 1373,
    }
    for name, expected in func_lines.items():
        check(f"{name} 起始行", funcs.get(name), expected)

    print("\n三、关键类的起始行号")
    for name, expected in (("_Address", 59), ("_BlockState", 69), ("_Command", 88),
                           ("_Substitution", 103), ("_ScriptParser", 123),
                           ("_LineSource", 641), ("_Writer", 697), ("_Engine", 726)):
        check(f"{name} 起始行", classes.get(name), expected)

    print("\n四、不支持的指令清单")
    body = re.search(r"_UNSUPPORTED_COMMANDS = \{(.*?)\n\}", src, re.DOTALL).group(1)
    names = re.findall(r'"([A-Za-z])":', body)
    check("不支持的指令个数", len(names), 15)
    check("不支持的指令清单", names,
          ["P", "D", "h", "H", "g", "G", "x", "l", "r", "R", "w", "W", "e", "z", "F"])

    print("\n五、POSIX 字符类表")
    posix_body = re.search(r"_POSIX_CLASSES = \{(.*?)\n\}", src, re.DOTALL).group(1)
    posix = re.findall(r'"(\w+)":', posix_body)
    check("POSIX 字符类个数", len(posix), 12)
    check("POSIX 字符类清单", posix,
          ["alpha", "digit", "alnum", "upper", "lower", "space", "blank",
           "punct", "print", "graph", "cntrl", "xdigit"])

    print("\n六、命令行选项")
    opts: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "add_argument":
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if arg.value.startswith("-"):
                            opts.add(arg.value)
    expected_opts = sorted({
        "-e", "--expression", "-f", "--file", "-n", "--quiet", "--silent",
        "-r", "-E", "--regexp-extended", "-s", "--separate", "--in-place",
        "--in-place-suffix", "-b", "--binary", "-z", "--null-data",
        "--follow-symlinks", "--unbuffered", "-u", "--posix", "--debug", "--sandbox",
    })
    check("选项串清单", sorted(opts), expected_opts)
    check("选项串个数（去重后）", len(opts), 24)

    print("\n七、测试用例数")
    test_src = TEST.read_text(encoding="utf-8")
    test_tree = ast.parse(test_src)
    test_funcs = [n.name for n in test_tree.body
                  if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    check("tests/test_sed.py 用例数", len(test_funcs), 44)
    check("test_sed.py 行数", len(test_src.splitlines()), 393)

    print("\n八、脚本解析的细节")
    repl_body = re.search(
        r"def _parse_replacement\(.*?\n    return items", src, re.DOTALL
    ).group(0)
    check("替换串里的转义字符", sorted(set(re.findall(r'nxt == "(\w)"', repl_body))),
          ["E", "L", "U", "a", "f", "n", "r", "t", "u", "v"])
    check("大小写修饰符集合",
          literal_string(r'nxt in "([A-Za-z]+)":', repl_body), "ULulE")
    check("s 标志 g", 'flag == "g"' in src, True)
    check("s 标志 p", 'flag == "p"' in src, True)
    check("s 标志 i/I",
          literal_string(r'flag in \("(\w)", "(\w)"\)', src) is not None
          or literal_string(r'flag in \("(\w)",(\s*)"(\w)"\)', src) is not None
          or ('flag in ("i", "I")' in src), True)

    print("\n九、编码判定的常量")
    check("_SNIFF_SIZE", re.search(r"_SNIFF_SIZE = (\d+)", src).group(1), "8192")
    check("_SCORE_MARGIN", re.search(r"_SCORE_MARGIN = ([\d.]+)", src).group(1), "0.3")
    check("_FALLBACK_ENCODINGS",
          literal_string(r"_FALLBACK_ENCODINGS = \((.*?)\)", src),
          '"utf-8", "gb18030", "latin-1"')
    check("_CJK_RANGES 的区间数",
          len(re.findall(r"0x[0-9A-Fa-f]+, 0x[0-9A-Fa-f]+", src)), 2)

    print("\n十、BRE 翻译的规则")
    bre_body = re.search(
        r"def _translate_bre\(.*?\n    return \"\".join\(out\)", src, re.DOTALL
    ).group(0)
    check("BRE 里裸元字符被转义的集合",
          literal_string(r'if char in "(.*?)":', bre_body), "(){}|+?")
    check("BRE 分组开头符集合",
          literal_string(r'_BRE_GROUP_OPENERS = "(.*?)"', src), "(|")
    check("BRE 里 * 的字面量判定标志 after_group", "after_group" in bre_body, True)
    check("BRE 里转义后当量词处理的集合",
          literal_string(r'if nxt in "(.*?)":', bre_body), "(){}|+?")
    check("BRE 里 < > 翻成 \\b",
          literal_string(r'elif nxt in "(.*?)":', bre_body), "<>")
    check("BRE 里 \\b \\B \\w \\W \\s \\S 原样保留",
          literal_string(r'elif nxt in "([bBwWsS]+)":', bre_body), "bBwWsS")

    print("\n十一、正文里引用的行号区间（逐行核对内容）")

    def line_has(no: int, needle: str) -> bool:
        return needle in lines[no - 1]

    def range_has(start: int, end: int, needle: str) -> bool:
        return any(needle in lines[i - 1] for i in range(start, end + 1))

    # 入口与数据流
    check("sed() 区间 1266~1334 含 def sed(",
          range_has(1266, 1334, "def sed("), True)
    check("引擎在 1284 行建", line_has(1284, "_Engine("), True)
    check("_ScriptParser 在 123 行", line_has(123, "class _ScriptParser"), True)
    check("_parse_address 区间 228~252", range_has(228, 252, "def _parse_address"), True)
    check("_parse_regex_address 区间 254~271",
          range_has(254, 271, "def _parse_regex_address"), True)
    check("_read_delimited 区间 273~293",
          range_has(273, 293, "def _read_delimited"), True)
    check("_compile 区间 295~302", range_has(295, 302, "def _compile"), True)
    check("_parse_payload 区间 306~337",
          range_has(306, 337, "def _parse_payload"), True)
    check("_parse_substitution 在 339 行",
          line_has(339, "def _parse_substitution"), True)
    check("_parse_replacement 在 466 行",
          line_has(466, "def _parse_replacement"), True)
    check("_translate_posix_classes 区间 579~586",
          range_has(579, 586, "def _translate_posix_classes"), True)
    check("_translate_bre 区间 589~633",
          range_has(589, 633, "def _translate_bre"), True)
    check("_Engine 在 726 行", line_has(726, "class _Engine"), True)
    check("_match_range 区间 832~860",
          range_has(832, 860, "def _match_range"), True)
    check("_tilde_reached 区间 862~875",
          range_has(862, 875, "def _tilde_reached"), True)
    check("_match_address 区间 877~895",
          range_has(877, 895, "def _match_address"), True)
    check("_execute 在 899 行", line_has(899, "def _execute"), True)
    check("_do_substitute 在 970 行", line_has(970, "def _do_substitute"), True)
    check("_replace_nth 在 1031 行", line_has(1031, "def _replace_nth"), True)
    check("_expand 在 1043 行", line_has(1043, "def _expand"), True)
    check("_text_score 区间 1090~1106",
          range_has(1090, 1106, "def _text_score"), True)
    check("_detect_encoding 区间 1109~1127",
          range_has(1109, 1127, "def _detect_encoding"), True)
    check("_read_file_lines 区间 1147~1161",
          range_has(1147, 1161, "def _read_file_lines"), True)
    check("build_parser 区间 1181~1218",
          range_has(1181, 1218, "def build_parser"), True)
    check("split_inplace 在 1221 行", line_has(1221, "def split_inplace"), True)
    check("_process_in_place 区间 1353~1365",
          range_has(1353, 1365, "def _process_in_place"), True)

    # 关键单行
    check("_Address 区间 59~65", range_has(59, 65, "kind: str"), True)
    check("_Command 范围状态字段在 95~99 行",
          range_has(95, 99, "in_range") and "matches: int = 0" in lines[98], True)
    check("数字终点在起始行就命中（846 行）",
          line_has(846, 'end.kind == "line"'), True)
    check("plus 终点行号算法（843~844 行）",
          line_has(843, 'end.kind == "plus"')
          and line_has(844, "command.end_line = source.number + end.number"), True)
    check("after_group 置位在 608 行",
          line_has(608, "_BRE_GROUP_OPENERS"), True)
    check("BRE 默认分支在 630~631 行",
          line_has(630, "out.append(char)") and line_has(631, "after_group = False"), True)
    check("step 分支 max(..., 1) 在 887~894 行",
          range_has(887, 894, "address.kind"), True)
    check("max(address.step, 1) 兜底在 894 行",
          line_has(894, "max(address.step, 1)"), True)

    print("\n十二、跨文件断言")
    du = (ROOT / "w2l" / "commands" / "du.py").read_text(encoding="utf-8")
    du_lines = du.splitlines()
    check("du.py 的 _DuParser 在 117 行",
          "_DuParser" in du_lines[116], True)
    cli = (ROOT / "w2l" / "cli.py").read_text(encoding="utf-8")
    cli_lines = cli.splitlines()
    check("cli.py 第 82~83 行是 parse_args",
          "parser_factory()" in cli_lines[81] and "parse_args" in cli_lines[82], True)
    check("cli.py 里没有调用 split_inplace",
          "split_inplace" in cli, False)
    # sed.py 是 w2l/commands/ 下最长的指令实现
    sizes = {}
    for path in (ROOT / "w2l" / "commands").glob("*.py"):
        sizes[path.name] = len(path.read_text(encoding="utf-8").splitlines())
    longest = max(sizes, key=lambda k: sizes[k])
    check("最长的指令实现是 sed.py", longest, "sed.py")
    check("第二长是 tail.py 且 1140 行",
          sorted(sizes.items(), key=lambda kv: -kv[1])[1], ("tail.py", 1140))

    print("\n" + "=" * 60)
    if failures:
        print("复算 %d 项，%d 项不符" % (checks, len(failures)))
        for line in failures:
            print("  " + line)
        return 1
    print("复算 %d 项，全部相符" % checks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
