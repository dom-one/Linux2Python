"""清理本 tick 的冒烟测试残留。

只删 AI/数据/ 下本轮临时产生的 _smoke_* 文件，不碰别的。
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据"


def main() -> int:
    if not DATA.exists():
        print("AI/数据/ 不存在，无需清理")
        return 0
    removed = []
    for path in sorted(DATA.iterdir()):
        if not path.name.startswith("_smoke_"):
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
        removed.append(path.name)
    print("已清理:", removed or "无")
    return 0


if __name__ == "__main__":
    sys.exit(main())
