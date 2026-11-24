"""在 tick 日志末尾补一行「推送状态」（推送失败时用）。

用法:
    python AI/脚本/_t1512_append_push_status.py --说明 "..."

做法: 字节追加，不动已有内容（进度文件的历史只能追加）。
幂等: 已存在同一行就不重复加。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DOC = ROOT / "AI" / "教程进度.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="补记推送状态")
    parser.add_argument("--进度", default="AI/教程进度.md")
    parser.add_argument("--说明", required=True)
    args = parser.parse_args()

    path = ROOT / args.进度
    text = path.read_text(encoding="utf-8")
    line = f"- **推送状态**：{args.说明}"

    if line in text:
        print("该推送状态已在位，跳过")
        return 0

    raw_before = path.read_bytes()
    crlf_before = raw_before.count(b"\r\n")
    with path.open("a", encoding="utf-8", newline="") as fh:
        fh.write(line + "\n")

    raw_after = path.read_bytes()
    if raw_after.count(b"\r\n") != crlf_before:
        print("!! 换行风格被改了，已回滚")
        path.write_bytes(raw_before)
        return 1

    print(f"推送状态已追加: {line[:60]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
