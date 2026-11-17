"""AI/脚本/_t621_check_progress_tick13.py —— 核对 tick #13 日志是否完整落盘。

查三件事:
1. 文件是合法 UTF-8
2. tick #13 段的六行结构齐全、顺序正确
3. 历史段落没被动过（tick #12 段仍在原样）
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
PROGRESS = AI_DIR / "阅读进度.md"

EXPECTED_KEYS = ["选本理由", "产出", "关键收获", "负面结果", "剩余待决"]


def main() -> int:
    raw = PROGRESS.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        print(f"不是合法 UTF-8: {exc}")
        return 1
    print(f"字节数 = {len(raw)}")
    print(f"行数 = {len(text.splitlines())}")

    blocks = re.findall(r"^#### tick #(\d+)[^\n]*\n(.*?)(?=^#### tick #|\Z)", text, re.M | re.S)
    print(f"段落数 = {len(blocks)}")
    print("各段 tick 号 =", [num for num, _ in blocks])

    numbers = [int(num) for num, _ in blocks]
    if numbers != list(range(1, len(numbers) + 1)):
        print("✗ 段号不连续")
        return 1
    print("✓ 段号连续")

    last_num, last_body = blocks[-1]
    if last_num != "13":
        print(f"✗ 最后一段不是 tick #13，而是 #{last_num}")
        return 1
    print(f"✓ 最后一段是 tick #{last_num}")

    for key in EXPECTED_KEYS:
        line = f"- **{key}**："
        if line not in last_body:
            print(f"✗ tick #13 缺「{key}」")
            return 1
        print(f"✓ 有「{key}」")

    positions = [last_body.index(f"- **{key}**：") for key in EXPECTED_KEYS]
    if positions != sorted(positions):
        print("✗ 六行的顺序不对")
        return 1
    print("✓ 六行顺序正确")

    prev_num, prev_body = blocks[-2]
    if "cp 的 -n/-i 顺序与 GNU 对齐" not in prev_body:
        print("✗ tick #12 的内容被动过")
        return 1
    print(f"✓ tick #{prev_num} 仍在原样")

    # 标题行里的主题也要在
    title = re.search(r"^#### tick #13（.*?— (.*)$", text, re.M)
    if not title or "rm" not in title.group(1):
        print("✗ 标题行不对")
        return 1
    print(f"✓ 标题 = {title.group(0)}")

    print("### 全部核对通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
