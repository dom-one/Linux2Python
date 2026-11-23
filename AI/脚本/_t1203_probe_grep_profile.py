#!/usr/bin/env python
"""探针：两件事，用来决定这一 tick 做哪件事。

A. grep 的时间花在哪：读文件 / 解码 / 打分（逐字符 Python 循环）。
B. multiprocessing 在本机的起进程开销：用来判断「给 find 加 -j 并行」到底赚不赚。

结论写在 AI/数据/t1203_*.json。
"""

from __future__ import annotations

import json
import locale
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


def _noop(value: int) -> int:
    """spawn 的池要 pickle 任务函数，必须放在模块顶层（局部函数 pickle 不了）。"""
    return value


def profile_grep() -> dict:
    """把 grep 的每文件开销拆成：读字节 / 编码判定里的解码 / 编码判定里的打分。"""
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(TARGET):
        dirnames.sort()
        for name in sorted(filenames):
            files.append(os.path.join(dirpath, name))
    files.sort()

    sample_limit = 400
    subset = files[:sample_limit]

    read_bytes = 0
    decode_seconds = 0.0
    score_seconds = 0.0
    ascii_samples = 0
    sizes = 0

    for raw in subset:
        path = Path(raw)
        try:
            with path.open("rb") as handle:
                sample = handle.read(grep_mod._SNIFF_SIZE)
        except OSError:
            continue
        sizes += 1
        read_bytes += len(sample)
        if sample.isascii():
            ascii_samples += 1
        for encoding in grep_mod._candidate_encodings():
            start = time.perf_counter()
            text = grep_mod._decode_sample(sample, encoding)
            decode_seconds += time.perf_counter() - start
            if text is None:
                continue
            start = time.perf_counter()
            grep_mod._text_score(text)
            score_seconds += time.perf_counter() - start

    return {
        "total_files": len(files),
        "sampled_files": sizes,
        "ascii_samples": ascii_samples,
        "ascii_ratio": round(ascii_samples / sizes, 4) if sizes else 0,
        "avg_sample_bytes": round(read_bytes / sizes, 1) if sizes else 0,
        "decode_seconds_400files": round(decode_seconds, 4),
        "score_seconds_400files": round(score_seconds, 4),
        "score_share": round(score_seconds / (decode_seconds + score_seconds), 4),
        "preferred_encoding": locale.getpreferredencoding(False),
        "candidates": grep_mod._candidate_encodings(),
    }


def measure_spawn_overhead() -> dict:
    """量一次 multiprocessing spawn 池的起停开销（本机是 Windows，只有 spawn）。"""
    import multiprocessing

    result: dict = {}
    for workers in (1, 4, 8):
        start = time.perf_counter()
        context = multiprocessing.get_context("spawn")
        pool = context.Pool(processes=workers)
        pool.map(_noop, range(workers))
        pool.terminate()
        pool.join()
        result[f"pool_{workers}"] = round(time.perf_counter() - start, 3)
    return result


def main() -> int:
    report = {"grep_profile": profile_grep(), "spawn_overhead": measure_spawn_overhead()}
    out = DATA / "t1203_profile.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[写入] {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
