#!/usr/bin/env python
"""差分验证：改前与改后的输出必须逐字节一致。

做法：把 AI/数据/t1208_encoding_baseline.json 里存下的「改前」基线
与「改后」重跑的结果逐条比对（stdout / stderr / 退出码三项都要一样）。

基线是改代码之前抓的，覆盖 cat/head/tail/wc/grep/sed/awk-lite/find/ls
在 ASCII、UTF-8 中文、GBK 中文、混合、全角、二进制、含 NUL、空文件、
latin-1 等语料上的行为。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = HERE.parent / "数据"

BASELINE = DATA / "t1208_encoding_baseline.json"
MAIN = str(ROOT / "main.py")


def run_case(args: list[str]) -> dict:
    proc = subprocess.run([sys.executable, MAIN, *args], capture_output=True)
    return {
        "args": args,
        "code": proc.returncode,
        "stdout": proc.stdout.hex(),
        "stderr": proc.stderr.hex(),
    }


def main() -> int:
    if not BASELINE.exists():
        print(f"[缺] 基线文件不存在：{BASELINE}")
        return 1

    payload = json.loads(BASELINE.read_text(encoding="utf-8"))
    cases = payload["cases"]
    print(f"[基线] {len(cases)} 组用例")

    mismatches: list[dict] = []
    for item in cases:
        now = run_case(item["args"])
        diffs = []
        for key in ("code", "stdout", "stderr"):
            if item[key] != now[key]:
                diffs.append(key)
        if diffs:
            mismatches.append({
                "args": item["args"],
                "fields": diffs,
                "before": {k: item[k] for k in diffs},
                "after": {k: now[k] for k in diffs},
            })

    out = DATA / "t1212_encoding_diff.json"
    out.write_text(json.dumps({
        "cases": len(cases),
        "mismatches": mismatches,
        "identical": not mismatches,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    if mismatches:
        print(f"[不一致] {len(mismatches)} 组：")
        for item in mismatches:
            print("  " + json.dumps(item, ensure_ascii=False)[:400])
        print(f"\n[写入] {out}")
        return 1

    print(f"[通过] {len(cases)} 组用例的 stdout/stderr/退出码全部逐字节一致")
    print(f"[写入] {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
