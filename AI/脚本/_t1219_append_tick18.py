#!/usr/bin/env python
"""追加 tick 日志到 AI/阅读进度.md（路径含中文，bash 写不了，用脚本走）。

内容从 AI/数据/tick18_content.json 读，逻辑复用 AI/脚本/_t11_progress.py：
tick 号在写入前一刻现算，只追加不重写。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = HERE.parent / "数据"
PROGRESS = HERE.parent / "阅读进度.md"
CONTENT = DATA / "tick18_content.json"

sys.path.insert(0, str(HERE))

from _t11_progress import build_block, next_tick  # noqa: E402


def main() -> int:
    payload = json.loads(CONTENT.read_text(encoding="utf-8"))
    tick = next_tick(str(PROGRESS))
    block = build_block(
        tick,
        payload["主题"],
        payload["理由"],
        payload["产出"],
        payload["收获"],
        payload["负面"],
        payload["剩余"],
    )
    with open(PROGRESS, "ab") as handle:
        handle.write(block.encode("utf-8"))
    print(f"tick #{tick} 已追加到 {PROGRESS}")
    print(f"新增字节数：{len(block.encode('utf-8'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
