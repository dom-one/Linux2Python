#!/usr/bin/env python
"""探针：grep 的端到端耗时里，编码判定到底占多少。

上一支探针测的是「判定内部」的占比（打分占判定的 97.5%），
这一支测的是「判定占整体」——读文件、正则搜索、判定各占多少。

做法：同一棵树上跑两种实现
  A. 现状（每个文件做编码判定）
  B. 把编码判定换成常量（跳过判定，代价最小化）
两者之差就是判定在整体里的真实占比。

预热后测量（Windows Defender 会扫新文件，不预热量到的是杀毒时间）。
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = HERE.parent / "数据"
DATA.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT))

from w2l.commands import grep as grep_mod  # noqa: E402

TARGET = sys.argv[1] if len(sys.argv) > 1 else "E:/1"


def collect_files(root: str) -> list[str]:
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            files.append(os.path.join(dirpath, name))
    files.sort()
    return files


def run_variant(files: list[str], pattern: str, stub_detect: bool) -> tuple[float, int]:
    """跑一遍搜索。stub_detect=True 时把编码判定换成常量 utf-8。"""
    regex = grep_mod.re.compile(pattern)
    original = grep_mod._detect_encoding
    if stub_detect:
        grep_mod._detect_encoding = lambda sample: "utf-8"
    hits = 0
    start = time.perf_counter()
    try:
        for raw in files:
            path = Path(raw)
            try:
                with path.open("rb") as handle:
                    sample = handle.read(grep_mod._SNIFF_SIZE)
                    if b"\x00" in sample:
                        continue
                    encoding = grep_mod._detect_encoding(sample)
                    handle.seek(0)
                    for line in handle:
                        text = line.decode(encoding, errors="replace")
                        if regex.search(text) is not None:
                            hits += 1
            except OSError:
                continue
    finally:
        grep_mod._detect_encoding = original
    return time.perf_counter() - start, hits


def main() -> int:
    files = collect_files(TARGET)
    report: dict = {"target": TARGET, "files": len(files)}

    # 预热（丢弃）
    run_variant(files[:200], "import", False)

    results = []
    for stub in (False, True):
        for round_index in range(2):
            elapsed, hits = run_variant(files, "import", stub)
            results.append({
                "stub_detect": stub,
                "round": round_index,
                "seconds": round(elapsed, 3),
                "hits": hits,
            })
    report["runs"] = results

    normal = [r["seconds"] for r in results if not r["stub_detect"]]
    stubbed = [r["seconds"] for r in results if r["stub_detect"]]
    report["normal_min"] = min(normal)
    report["stubbed_min"] = min(stubbed)
    report["detect_share"] = round((min(normal) - min(stubbed)) / min(normal), 4)

    out = DATA / "t1204_grep_endtoend.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[写入] {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
