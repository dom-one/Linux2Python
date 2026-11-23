#!/usr/bin/env python
"""检查 AI/脚本 下新旧脚本的换行符是否一致。

用法: python AI/脚本/_t1218_check_scripts_eol.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SCRIPT_DIR = HERE

# 本轮新增
NEW = [
    "_t1201_probe_find_baseline.py",
    "_t1203_probe_grep_profile.py",
    "_t1204_probe_grep_endtoend.py",
    "_t1205_probe_score_bench.py",
    "_t1207_probe_scorer_choice.py",
    "_t1208_probe_encoding_baseline.py",
    "_t1210_cut_dup_encoding.py",
    "_t1211_health_check.py",
    "_t1212_diff_encoding.py",
    "_t1213_verify_equivalence.py",
    "_t1214_probe_grep_after.py",
    "_t1215_probe_grep_table.py",
    "_t1216_check_eol.py",
    "_t1217_normalize_lf.py",
]


def stats(data: bytes) -> str:
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    return f"CRLF={crlf} LF={lf}"


def main() -> int:
    # 先看仓库里已跟踪脚本的口径
    sample = "_t1101_probe_parallel_baseline.py"
    got = subprocess.run(["git", "show", f"HEAD:AI/脚本/{sample}"],
                         cwd=str(ROOT), capture_output=True)
    if got.returncode == 0:
        print(f"[仓库口径] {sample}: {stats(got.stdout)}")
    print("[本轮新增]")
    mixed = []
    for name in NEW:
        path = SCRIPT_DIR / name
        if not path.exists():
            print(f"  {name}: 缺失")
            continue
        data = path.read_bytes()
        line = f"  {name}: {stats(data)}"
        if b"\r\n" in data:
            mixed.append(name)
        print(line)
    if mixed:
        print(f"\n有 CRLF 的脚本：{mixed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
