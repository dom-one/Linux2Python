#!/usr/bin/env python
"""把各指令里重复的编码判定实现删掉，改用共享模块 w2l/encoding.py。

第一版（_t1209_cut_dup_encoding.py）用正则找「下一个顶层 def」来切函数体，
结果把前一个函数最后一行和下一个函数的 def 粘在了一起（少了一个换行），
造成语法错误。这一版改成**按行**处理：

1. 用 ast 解析出每个目标函数的起止行号（def 行到函数体最后一行）；
2. 删掉 [起, 止] 这段行，并把紧邻上方的空行一起收掉；
3. 删完重新 ast.parse，语法不通过就报错退出。

只删函数，不碰别的；删完由 _t1209b_verify_cut.py 做结构核对。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
COMMANDS = ROOT / "w2l" / "commands"

TARGETS: dict[str, list[str]] = {
    "head.py": ["_pick_encoding", "_is_text", "_detect_encoding", "_candidate_encodings", "_decode_sample", "_text_score"],
    "tail.py": ["_pick_encoding", "_is_text", "_detect_encoding", "_candidate_encodings", "_decode_sample", "_text_score"],
    "wc.py": ["_pick_encoding", "_is_text", "_detect_encoding", "_candidate_encodings", "_decode_sample", "_text_score"],
    "sed.py": ["_detect_encoding", "_candidate_encodings", "_decode_sample", "_text_score"],
    "awk_lite.py": ["_detect_encoding", "_candidate_encodings", "_decode_sample", "_text_score"],
}


def function_line_ranges(source: str) -> dict[str, tuple[int, int]]:
    """返回 {函数名: (起始行号, 结束行号)}，行号从 0 开始，含首含尾。"""
    tree = ast.parse(source)
    ranges: dict[str, tuple[int, int]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # end_lineno 是函数体最后一行；装饰器在 node.lineno 之前，这里没有装饰器
            ranges[node.name] = (node.lineno - 1, node.end_lineno)
    return ranges


def cut_functions(source: str, names: list[str]) -> tuple[str, list[str]]:
    lines = source.splitlines(keepends=True)
    ranges = function_line_ranges(source)
    removed: list[str] = []
    to_drop: set[int] = set()

    for name in names:
        if name not in ranges:
            continue
        start, end = ranges[name]
        removed.append(name)
        index = start
        # 连同函数上方的空行一起删（顶层函数之间留两个空行）
        while index - 1 >= 0 and lines[index - 1].strip() == "":
            index -= 1
        to_drop.update(range(index, end + 1))

    kept = [line for number, line in enumerate(lines) if number not in to_drop]
    result = "".join(kept)
    # 顶层定义之间统一留两个空行
    while "\n\n\n\n" in result:
        result = result.replace("\n\n\n\n", "\n\n\n")
    return result, removed


def main() -> int:
    for filename, names in TARGETS.items():
        path = COMMANDS / filename
        source = path.read_text(encoding="utf-8")
        result, removed = cut_functions(source, names)
        # 语法自检：删完必须还能解析
        try:
            ast.parse(result)
        except SyntaxError as exc:
            print(f"[失败] {filename} 删完语法不通过：{exc}")
            print(f"        已删除：{removed}")
            return 1
        path.write_text(result, encoding="utf-8")
        print(f"[完成] {filename}: 删除 {removed}，{len(source)} -> {len(result)} 字节")
    return 0


if __name__ == "__main__":
    sys.exit(main())
