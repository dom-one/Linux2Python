"""核对 teach/25 教程正文里的断言：行号引用、数字、表格。

核对器（_t12_verify_teach.py）只比对命令块与预期输出，正文里的行号引用与
数字它查不到，得单独写脚本复算。

用法:
    python AI/脚本/_t811_verify_teach25_claims.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = Path(os.path.dirname(os.path.dirname(HERE)))
DOC = ROOT / "teach" / "25-w2l-commands-tree.py-树形输出与画线规则.md"

failures: list[str] = []
checks = 0


def lines_of(rel: str) -> list[str]:
    return (ROOT / rel).read_text(encoding="utf-8").splitlines()


def expect(rel: str, lineno: int, needle: str) -> None:
    """断言某文件第 lineno 行（1 基）包含 needle。"""
    global checks
    checks += 1
    src = lines_of(rel)
    if lineno > len(src):
        failures.append(f"{rel}:{lineno} 行不存在（文件只有 {len(src)} 行）")
        return
    actual = src[lineno - 1]
    if needle not in actual:
        failures.append(f"{rel}:{lineno} 不含 {needle!r}，实际是 {actual.strip()!r}")


def expect_range(rel: str, start: int, end: int, needle: str) -> None:
    """断言某文件 [start, end] 行区间里出现过 needle。"""
    global checks
    checks += 1
    src = lines_of(rel)
    if end > len(src):
        failures.append(f"{rel}:{start}~{end} 区间越界（文件只有 {len(src)} 行）")
        return
    chunk = "\n".join(src[start - 1 : end])
    if needle not in chunk:
        failures.append(f"{rel}:{start}~{end} 区间不含 {needle!r}")


def doc_has(needle: str) -> None:
    global checks
    checks += 1
    text = DOC.read_text(encoding="utf-8")
    if needle not in text:
        failures.append(f"教程里找不到 {needle!r}")


def doc_lacks(needle: str) -> None:
    global checks
    checks += 1
    text = DOC.read_text(encoding="utf-8")
    if needle in text:
        failures.append(f"教程里不该出现 {needle!r}")


def main() -> None:
    tree = "w2l/commands/tree.py"

    # ---- 行号引用：tree.py ----
    expect(tree, 34, "from ..perms import canonical_mode, format_perms")
    expect_range(tree, 46, 59, '"vert": "│\\u00a0\\u00a0"')
    expect_range(tree, 46, 59, '"vert_left": "├──"')
    expect_range(tree, 46, 59, '"corner": "└──"')
    expect_range(tree, 46, 59, '"vert": "|  "')
    expect_range(tree, 46, 59, '"vert_left": "|--"')
    expect_range(tree, 46, 59, '"corner": "`--"')
    expect_range(tree, 61, 66, '"utf-8": "utf8"')
    expect(tree, 135, '@command("tree"')
    expect_range(tree, 135, 169, "return 2 if state.had_error else 0")
    expect(tree, 143, 'operands = list(args.paths) if args.paths else ["."]')
    expect(tree, 164, "state.root_dev = st.st_dev")
    expect(tree, 183, "pattern_active = not _matches_patterns")
    expect_range(tree, 185, 187, "return")
    expect(tree, 188, "state.dirs += 1")
    expect_range(tree, 192, 235, "def _list_dir(")
    expect(tree, 198, "ancestors: list[bool],")
    expect(tree, 214, "state.dirs += 1")
    expect(tree, 218, "children = _read_entries(entry.path, args, child_path, pattern_active, state)")
    expect_range(tree, 222, 224, "child_active = pattern_active and not _matches_patterns(")
    expect(tree, 231, "ancestors + [not is_last]")
    expect_range(tree, 247, 260, "def _build_prefix(")
    expect_range(tree, 247, 260, "return \"\".join(part + \" \" for part in parts)")
    expect_range(tree, 263, 277, "def _format_entry(")
    expect_range(tree, 280, 290, "def _format_meta(")
    expect_range(tree, 293, 295, "def _format_perms(")
    expect(tree, 295, "format_perms(st.st_mode)")
    expect_range(tree, 298, 316, "def _format_size(")
    expect(tree, 301, "if stat.S_ISDIR(st.st_mode):")
    expect_range(tree, 306, 316, "return f\" {number:.1f}{_SIZE_UNITS[index]}\"")
    expect_range(tree, 319, 326, "def _format_time(")
    expect_range(tree, 329, 342, "def _type_marker(")
    expect(tree, 340, "canonical_mode(mode) & 0o111")
    expect_range(tree, 345, 354, "def _format_report(")
    expect_range(tree, 362, 420, "def _read_entries(")
    expect(tree, 384, "st = item.stat(follow_symlinks=False)")
    expect_range(tree, 397, 397, "args.one_file_system and state.root_dev is not None")
    expect_range(tree, 423, 437, "def _sort_entries(")
    expect_range(tree, 467, 485, "def _matches_patterns(")
    expect_range(tree, 467, 485, 'candidates.append("/".join(parts[index:]))')
    expect_range(tree, 488, 501, "def _match_pattern(")
    expect_range(tree, 504, 538, "def _compile_pattern(")
    expect(tree, 154, "stat.S_ISLNK(st.st_mode)")
    expect(tree, 387, "is_link = stat.S_ISLNK(st.st_mode)")
    expect(tree, 39, "_SIX_MONTHS = 6 * 31 * 24 * 60 * 60")

    # ---- 行号引用：du.py 与 README ----
    expect_range("w2l/commands/du.py", 391, 396, "st_dev 与 st_ino 全是 0")
    expect_range("w2l/commands/du.py", 391, 396, "os.stat(item.path, follow_symlinks=follow)")
    expect("README.md", 415, "-t` 是旧的在前")
    expect("README.md", 418, "某个目录命中 `-P` 时它下面的内容全部列出")
    expect("README.md", 429, "drwxrwxrwx")
    expect("README.md", 433, "`-x` 实际是不跨盘符")

    # ---- 数字断言 ----
    src = lines_of(tree)
    global checks
    checks += 1
    if len(src) != 575:
        failures.append(f"tree.py 是 {len(src)} 行，教程写的是 575 行")

    checks += 1
    if 6 * 31 != 186:
        failures.append("6*31 不是 186 天")

    # fnmatch 在 Windows 上抹平大小写
    import fnmatch

    checks += 1
    if not fnmatch.fnmatch("B.TXT", "*.txt"):
        failures.append("fnmatch.fnmatch('B.TXT', '*.txt') 实测不是 True")

    # ---- 教程正文里的选项数量 ----
    parser_calls = re.findall(r"parser\.add_argument\(", "\n".join(src))
    option_calls = len(parser_calls) - 1  # 减去位置参数 paths
    doc_lacks("20 个选项")
    doc_has("21 个选项")

    # ---- 教程里不能有会被 markdown 表格吃掉的裸竖线 ----
    for row in DOC.read_text(encoding="utf-8").splitlines():
        if row.startswith("| ") and "FIFO" in row:
            checks += 1
            if "`|`" in row:
                failures.append("选项表里 FIFO 的竖线没转义，会把 markdown 表格拆坏")

    print(f"共 {checks} 项断言")
    if failures:
        print(f"不通过 {len(failures)} 项：")
        for item in failures:
            print(f"  - {item}")
        sys.exit(1)
    print("全部通过")


if __name__ == "__main__":
    main()
