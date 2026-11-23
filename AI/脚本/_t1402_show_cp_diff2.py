"""读 _t1401 的差分结果，把关键用例的两侧原文打出来。

用法:
    python AI/脚本/_t1402_show_cp_diff2.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1] / "AI" / "数据" / "cp_probe2"
REPORT = DATA / "diff_cp2.json"

WATCH = [
    "preserve-bare-then-operand",
    "noclobber-then-interactive",
    "interactive-then-noclobber",
    "dest-trailing-slash-new",
    "parents-with-no-target-dir",
    "dir-into-itself",
    "dir-into-own-subdir",
    "junction-in-tree",
    "junction-in-tree-archive",
    "loop-junction",
]


def main() -> int:
    cases = json.loads(REPORT.read_text(encoding="utf-8"))
    for case in cases:
        if case["name"] not in WATCH:
            continue
        print("=" * 70)
        print(f"用例 {case['name']}  argv={case['argv']}  setup={case['setup']}")
        for side in ("gnu", "mine"):
            info = case[side]
            print(f"  --- {side} ---")
            print(f"  rc={info['rc']}")
            print(f"  out={info['out']!r}")
            print(f"  err={info['err']!r}")
        for problem in case["problems"]:
            print("  !! ", problem)
    return 0


if __name__ == "__main__":
    sys.exit(main())
