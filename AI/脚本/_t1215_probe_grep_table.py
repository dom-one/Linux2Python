#!/usr/bin/env python
"""探针：重测 grep 的串行/并行对照表（README「分片并行搜索」那张表）。

编码判定提速之后，串行耗时整体下来了，README 里的旧数字已经过期，
所以按同口径重测一遍：

  - 本项目串行 / -j 4 / -j 8
  - GNU grep（Git Bash 自带）

每个口径跑两轮取最小值（机器上别的负载会让两次差 45%）；
先预热一次再量（Defender 扫新文件要 141s，不预热量到的是杀毒时间）。
输出重定向到 DEVNULL：只关心耗时和命中数，不把 12000 多行结果收进管道。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = HERE.parent / "数据"
DATA.mkdir(parents=True, exist_ok=True)

TARGET = sys.argv[1] if len(sys.argv) > 1 else "E:/1"
PATTERN = "import"


def count_files(root: str) -> int:
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        total += len(filenames)
    return total


def run(cmd: list[str]) -> tuple[float, int]:
    """跑一次命令，返回 (耗时秒, 命中行数)。

    命中行数用管道数出来的：直接读 stdout 会把 12000 多行收进内存，
    改成边跑边数更省。
    """
    start = time.perf_counter()
    proc = subprocess.Popen(
        cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8", errors="replace",
    )
    hits = 0
    assert proc.stdout is not None
    for _ in proc.stdout:
        hits += 1
    proc.wait()
    return time.perf_counter() - start, hits


def main() -> int:
    report: dict = {"target": TARGET, "pattern": PATTERN, "files": count_files(TARGET)}

    variants = {
        "w2l_serial": ["python", "main.py", "grep", "-r", PATTERN, TARGET],
        "w2l_j4": ["python", "main.py", "grep", "-r", "-j", "4", PATTERN, TARGET],
        "w2l_j8": ["python", "main.py", "grep", "-r", "-j", "8", PATTERN, TARGET],
        "gnu_grep": ["grep", "-r", PATTERN, TARGET],
    }

    # 预热：只跑前一小段，让 Defender 先把这棵树扫过一遍
    warm = ["python", "main.py", "grep", "-r", PATTERN, str(ROOT / "w2l")]
    run(warm)

    runs: list[dict] = []
    for round_index in range(2):
        for name, cmd in variants.items():
            elapsed, hits = run(cmd)
            runs.append({"variant": name, "round": round_index,
                         "seconds": round(elapsed, 2), "hits": hits})
            print(f"[{round_index}] {name}: {elapsed:.2f}s hits={hits}", flush=True)
    report["runs"] = runs

    best: dict = {}
    hits_by: dict = {}
    for name in variants:
        values = [r["seconds"] for r in runs if r["variant"] == name]
        best[name] = min(values)
        hits_by[name] = sorted({r["hits"] for r in runs if r["variant"] == name})
    report["best_seconds"] = best
    report["hit_counts"] = hits_by
    if best.get("gnu_grep"):
        report["serial_vs_gnu"] = round(best["w2l_serial"] / best["gnu_grep"], 2)
        report["j8_vs_gnu"] = round(best["w2l_j8"] / best["gnu_grep"], 2)

    out = DATA / "t1215_grep_table.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[写入] {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
