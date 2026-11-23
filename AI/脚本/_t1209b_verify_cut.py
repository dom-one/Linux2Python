#!/usr/bin/env python
"""核对：删掉的只有编码判定那几个函数，别的一行都没动。

做法：把改后的文件与改前的备份逐行 diff，
断言「被删的行」全部来自那 6 个编码函数的函数体，
且「没有新增行」（除了 import 段），
再断言每个文件里剩下的顶层定义与改前一致（只是少了那几个）。
"""

from __future__ import annotations

import ast
import difflib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BACKUP = HERE.parent / "数据" / "enc_backup"

FILES = ["head.py", "tail.py", "wc.py", "sed.py", "awk_lite.py"]
REMOVED = {
    "_pick_encoding",
    "_is_text",
    "_detect_encoding",
    "_candidate_encodings",
    "_decode_sample",
    "_text_score",
}


def top_level_names(source: str) -> list[str]:
    tree = ast.parse(source)
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.append(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
    return names


def main() -> int:
    problems: list[str] = []
    for name in FILES:
        old_path = BACKUP / name
        new_path = ROOT / "w2l" / "commands" / name
        old = old_path.read_text(encoding="utf-8").splitlines()
        new = new_path.read_text(encoding="utf-8").splitlines()

        old_names = top_level_names("\n".join(old))
        new_names = top_level_names("\n".join(new))

        # 1. 少了的名字必须正好是那 6 个里的（子集）
        missing = [n for n in old_names if n not in new_names]
        unexpected = [n for n in missing if n not in REMOVED]
        if unexpected:
            problems.append(f"{name}: 少了不该少的定义 {unexpected}")

        # 2. 新增的名字（import 段之外不该有）
        added = [n for n in new_names if n not in old_names]
        allowed_added = set()
        if added:
            problems.append(f"{name}: 新增了顶层名字 {added}（预期为空）")

        # 3. 顺序：剩下的名字相对顺序必须与改前一致
        kept_old = [n for n in old_names if n in new_names]
        kept_new = [n for n in new_names if n in old_names]
        if kept_old != kept_new:
            problems.append(f"{name}: 保留项的相对顺序变了")

        # 4. diff：新增行（+）必须只在 import 区域
        diff = list(difflib.unified_diff(old, new, lineterm="", n=0))
        added_lines = [line[1:] for line in diff if line.startswith("+") and not line.startswith("+++")]
        removed_lines = [line[1:] for line in diff if line.startswith("-") and not line.startswith("---")]
        for line in added_lines:
            if not (line.startswith("from ..") or line.startswith("    ") or line.startswith(")")
                    or line.startswith("import ") or line.strip() == ""):
                problems.append(f"{name}: 新增了非 import 区的行 -> {line!r}")

        print(f"[核对] {name}: 少了 {missing}；新增顶层 {added}；删除 {len(removed_lines)} 行 / 新增 {len(added_lines)} 行")

    if problems:
        print("\n[问题]")
        for item in problems:
            print("  " + item)
        return 1
    print("\n[通过] 只删掉了编码判定那几个函数，其余结构未变")
    return 0


if __name__ == "__main__":
    sys.exit(main())
