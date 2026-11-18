"""差分脚本：连跑两遍进度更新脚本，逐行对比，找出字节数漂移的位置。

用法:
    python AI/脚本/_t813_diff_progress_update.py
"""

from __future__ import annotations

import difflib
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = Path(os.path.dirname(os.path.dirname(HERE)))
TARGET = ROOT / "AI" / "教程进度.md"
SCRIPT = ROOT / "AI" / "脚本" / "_t812_update_teach_progress.py"
SNAP_A = ROOT / "AI" / "数据" / "_progress_a.txt"
SNAP_B = ROOT / "AI" / "数据" / "_progress_b.txt"


def main() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], check=True, capture_output=True)
    shutil.copyfile(TARGET, SNAP_A)
    size_a = SNAP_A.stat().st_size

    subprocess.run([sys.executable, str(SCRIPT)], check=True, capture_output=True)
    shutil.copyfile(TARGET, SNAP_B)
    size_b = SNAP_B.stat().st_size

    a = SNAP_A.read_text(encoding="utf-8").splitlines()
    b = SNAP_B.read_text(encoding="utf-8").splitlines()
    print(f"A {size_a} 字节 / {len(a)} 行，B {size_b} 字节 / {len(b)} 行")

    diff = list(difflib.unified_diff(a, b, "A", "B", lineterm="", n=2))
    if not diff:
        print("两遍完全一样")
        return
    print(f"差异 {len(diff)} 行，前 60 行：")
    for line in diff[:60]:
        print("  " + line)


if __name__ == "__main__":
    main()
