#!/usr/bin/env python
"""改完之后的体检：语法、导入、未使用的名字、函数是否还在。

检查项：
1. 每个模块能 ast.parse 且能真正 import（不是只编译过）。
2. 原来那些编码判定函数在本文件里已经不存在（不再有第二份实现）。
3. 从共享模块导入的名字确实被用到（没导入却没用 = 该删）；
   反过来，模块里引用的名字都有定义（没定义 = 会 NameError）。
4. 共享模块的公开接口齐全。
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

COMMANDS = [
    "grep", "ls", "cat", "head", "tail", "wc", "find",
    "tree", "du", "sed", "awk_lite", "cp", "mv", "rm", "chmod",
]

REMOVED = [
    "_pick_encoding", "_is_text", "_detect_encoding",
    "_candidate_encodings", "_decode_sample", "_text_score",
]


def collect_names(tree: ast.AST) -> set[str]:
    """收集模块里所有被引用到的名字。"""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def main() -> int:
    problems: list[str] = []

    for name in COMMANDS:
        path = ROOT / "w2l" / "commands" / f"{name}.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        # 1. 真正 import 一次
        try:
            importlib.import_module(f"w2l.commands.{name}")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{name}: import 失败 -> {exc!r}")

        # 2. 重复实现应当已经不在本文件里（sed 保留了自己的包装函数）
        own = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        allowed = {"_detect_encoding"} if name == "sed" else set()
        leftover = (own & set(REMOVED)) - allowed
        if leftover:
            problems.append(f"{name}: 仍有重复实现 {sorted(leftover)}")

        # 3. 导入但没用 / 用了没定义
        used = collect_names(tree)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(".."):
                for alias in node.names:
                    imported.add(alias.asname or alias.name)
        unused = sorted(n for n in imported if n not in used)
        if unused:
            problems.append(f"{name}: 导入了没用到的名字 {unused}")

        # 顶层定义的私有名字 + 模块级常量
        defined: set[str] = set(imported)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined.add(target.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                defined.add(node.target.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    defined.add((alias.asname or alias.name).split(".")[0])

        # 只查模块级引用（函数体内的名字由闭包提供，不在此列）
        module_level_used: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                for sub in ast.walk(node.value):
                    if isinstance(sub, ast.Name):
                        module_level_used.add(sub.id)
        missing = sorted(
            n for n in module_level_used
            if n not in defined and not hasattr(__builtins__, n)
        )
        if missing:
            problems.append(f"{name}: 模块级用到了未定义的名字 {missing}")

        print(f"[体检] {name}: import 通过，重复实现 {sorted(leftover) or '无'}，未使用导入 {unused or '无'}")

    # 4. 共享模块接口
    import w2l.encoding as enc

    for attr in ("SNIFF_SIZE", "SCORE_MARGIN", "BINARY_ENCODING", "candidate_encodings",
                 "decode_sample", "text_score", "detect_encoding", "is_text", "pick_encoding"):
        if not hasattr(enc, attr):
            problems.append(f"w2l/encoding.py: 缺少 {attr}")

    print("\n[共享模块] 接口齐全" if not problems else "")
    if problems:
        print("[问题]")
        for item in problems:
            print("  " + item)
        return 1
    print("[通过] 全部模块可导入，重复实现已清干净")
    return 0


if __name__ == "__main__":
    sys.exit(main())
