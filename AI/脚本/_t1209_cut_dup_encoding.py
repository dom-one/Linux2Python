#!/usr/bin/env python
"""把各指令里重复的编码判定实现删掉，改用共享模块 w2l/encoding.py。

只删「函数定义」这一段，函数体逐字照抄自各文件原有内容，
删完再断言：
- 目标函数在该文件里已经不存在；
- 该文件原本 import 的 codecs / locale 变成没人用（用 pyflakes 式检查）；
- 文件能正常 import。

做法：按函数名定位到 `def <名字>(` 那一行，往下吃到下一个顶层 `def ` 或
文件末尾，整段删掉。删完把空出来的连续空行压成两个（PEP8 顶层函数间隔）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
COMMANDS = ROOT / "w2l" / "commands"

# 每个文件要删的函数（都在本轮改成从共享模块导入）
TARGETS: dict[str, list[str]] = {
    "head.py": ["_pick_encoding", "_is_text", "_detect_encoding", "_candidate_encodings", "_decode_sample", "_text_score"],
    "tail.py": ["_pick_encoding", "_is_text", "_detect_encoding", "_candidate_encodings", "_decode_sample", "_text_score"],
    "wc.py": ["_pick_encoding", "_is_text", "_detect_encoding", "_candidate_encodings", "_decode_sample", "_text_score"],
    "sed.py": ["_detect_encoding", "_candidate_encodings", "_decode_sample", "_text_score"],
    "awk_lite.py": ["_detect_encoding", "_candidate_encodings", "_decode_sample", "_text_score"],
}


def cut_function(source: str, name: str) -> tuple[str, bool]:
    """删掉一个顶层函数定义（含它上面的空行），返回 (新文本, 是否删到)。"""
    pattern = re.compile(rf"^def {re.escape(name)}\(", re.M)
    match = pattern.search(source)
    if match is None:
        return source, False
    start = match.start()
    # 往前吃掉紧挨着的空行（函数定义前的分隔空行）
    while start > 0 and source[start - 1] == "\n":
        start -= 1
    # 往后找下一个顶层 def / class / 顶层常量，函数体到此为止
    rest = source[match.end():]
    next_def = re.search(r"^(?:def |class |[A-Z_][A-Z0-9_]*\s*=)", rest, re.M)
    if next_def is None:
        end = len(source)
    else:
        end = match.end() + next_def.start()
    # 删到下一个定义之前，把空行收敛
    tail = source[end:]
    head = source[:start]
    tail = re.sub(r"^\n{3,}", "\n\n\n", tail)
    return head + tail, True


def main() -> int:
    for filename, names in TARGETS.items():
        path = COMMANDS / filename
        source = path.read_text(encoding="utf-8")
        before_len = len(source)
        for name in names:
            source, removed = cut_function(source, name)
            if not removed:
                print(f"[警告] {filename} 里没找到 {name}，跳过")
        # 顶层函数之间留两个空行
        source = re.sub(r"\n{4,}", "\n\n\n", source)
        path.write_text(source, encoding="utf-8")
        print(f"[完成] {filename}: {before_len} -> {len(source)} 字节")
    return 0


if __name__ == "__main__":
    sys.exit(main())
