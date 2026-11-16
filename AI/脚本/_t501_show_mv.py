"""摘要：把 mv 探针结果压成一张表（只挑关心的用例）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "mv_probe"

WANT = sys.argv[1:] or None


def main() -> int:
    path = DATA / "probe_mv.json"
    if not path.is_file():
        raise SystemExit(f"找不到 {path}，先跑 _t500_probe_mv.py")
    rows = json.loads(path.read_text(encoding="utf-8"))
    for row in rows:
        if WANT and row["name"] not in WANT:
            continue
        print("=" * 70)
        print(f"[{row['name']}] argv={' '.join(row['argv'])}  stdin={row['stdin']!r}")
        print(f"  rc  = {row['rc']}")
        print(f"  out = {row['out']!r}")
        print(f"  err = {row['err']!r}")
        for key, value in row["tree"].items():
            print(f"    {key}  ->  {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
