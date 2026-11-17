"""统计 find.py 与 test_find.py 的结构事实（行数、段落占比、函数行号）。

用法:
    python AI/脚本/_t704_probe_find_facts.py
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = Path(ROOT) / "w2l" / "commands" / "find.py"
TEST = Path(ROOT) / "tests" / "test_find.py"

BANNER = re.compile(r"^# -{10,}$")


def sections(lines: list[str]) -> list[tuple[str, int, int]]:
    """按注释横幅切段，返回 (标题, 内容起行, 内容止行)。

    横幅是三行一组：上横幅 / 标题 / 下横幅。内容从下横幅的下一行开始。
    """
    banners = [i for i, line in enumerate(lines, 1) if BANNER.match(line)]
    marks = []
    for i in range(len(banners) - 1):
        if banners[i + 1] == banners[i] + 2:
            title = lines[banners[i]].strip().lstrip("#").strip()
            marks.append((title, banners[i + 1] + 1))
    out = []
    for idx, (title, start) in enumerate(marks):
        end = (marks[idx + 1][1] - 1) if idx + 1 < len(marks) else len(lines)
        out.append((title, start, end))
    return out


def top_level(lines: list[str]) -> list[tuple[str, int, int, str]]:
    """用 ast 找顶层 def/class，返回 (名字, 起行, 止行, 类型)。"""
    tree = ast.parse("\n".join(lines))
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append((node.name, node.lineno, node.end_lineno, "def"))
        elif isinstance(node, ast.ClassDef):
            out.append((node.name, node.lineno, node.end_lineno, "class"))
    return out


def main() -> None:
    src_lines = SRC.read_text(encoding="utf-8").splitlines()
    test_lines = TEST.read_text(encoding="utf-8").splitlines()
    total = len(src_lines)

    print(f"w2l/commands/find.py  {total} 行")
    print(f"tests/test_find.py    {len(test_lines)} 行")
    print()

    print("== 段落（注释横幅） ==")
    for title, start, end in sections(src_lines):
        span = end - start + 1
        pct = span / total * 100
        print(f"  {start:4}~{end:4}  {span:4} 行 ({pct:4.1f}%)  {title}")
    print()

    print("== 顶层定义 ==")
    for name, start, end, kind in top_level(src_lines):
        span = end - start + 1
        print(f"  {start:4}~{end:4}  {span:4} 行  {kind} {name}")
    print()

    tree = ast.parse("\n".join(test_lines))
    tests = [n.name for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    print(f"== 测试用例 {len(tests)} 个 ==")
    for name in tests:
        print(f"  {name}")
    print()

    # 谓词/动作的字面清单
    text = "\n".join(src_lines)
    for pattern, label in [
        (r'-name|-iname|-path|-ipath|-regex|-iregex', "名字/路径匹配"),
        (r'-type', "类型"),
        (r'-size', "大小"),
        (r'-mtime|-mmin', "时间"),
        (r'-newer', "参照时间"),
        (r'-empty|-true|-false', "布尔"),
        (r'-prune', "剪枝"),
        (r'-print|-print0|-printf', "打印"),
        (r'-exec', "执行"),
        (r'-delete', "删除"),
    ]:
        n = len(re.findall(pattern, text))
        print(f"  {label:12} 字面出现 {n} 次")


if __name__ == "__main__":
    main()
