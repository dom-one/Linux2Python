"""清理探针脚本遗留在 AI/数据/ 下的临时目录。

只删 AI/数据/ 下的临时目录，不碰源码与其它目录。
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "AI" / "数据"


def main() -> int:
    if not DATA.is_dir():
        print("AI/数据/ 不存在，无需清理")
        return 0
    removed = 0
    for entry in sorted(DATA.iterdir()):
        if not entry.is_dir():
            continue
        shutil.rmtree(entry, ignore_errors=True)
        print("已删除临时目录: %s" % entry.name)
        removed += 1
    print("共清理 %d 个临时目录" % removed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
