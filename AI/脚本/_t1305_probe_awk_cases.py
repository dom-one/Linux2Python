#!/usr/bin/env python
"""从 AI/产物/awk-diff/cases.json 里查指定用例的逐条结果。

用法：
    python AI/脚本/_t1305_probe_awk_cases.py 关键字 [关键字...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CASES = ROOT / "AI" / "产物" / "awk-diff" / "cases.json"


def main() -> int:
    rows = json.loads(CASES.read_text(encoding="utf-8"))
    keys = sys.argv[1:]
    picked = rows
    if keys:
        picked = [
            r
            for r in rows
            if any(k in r["name"] or k in r["program"] for k in keys)
        ]
    for r in picked:
        mark = "一致" if (r["same_out"] and r["same_code"]) else "★差异"
        print(f"[{mark}] {r['name']}")
        print(f"  选项 {r['opts']} 程序 {r['program']!r} 文件 {r['files']}")
        print(f"  退出码 项目 {r['proj_code']} / GNU {r['gnu_code']}")
        print(f"  项目输出 {r['proj_out']!r}")
        print(f"  GNU 输出 {r['gnu_out']!r}")
        if r["proj_err"]:
            print(f"  项目错误 {r['proj_err']}")
        if r["gnu_err"]:
            print(f"  GNU 错误 {r['gnu_err']}")
        print()
    print(f"共 {len(picked)} 条（全量 {len(rows)} 条）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
