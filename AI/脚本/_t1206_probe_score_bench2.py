#!/usr/bin/env python
"""探针：编码打分的定稿基准（上一支的 S3 计时被正确性预热污染了，重测）。

要回答三件事：
1. 纯 ASCII 快速路径（**可证明逐位等价**）能省多少？
2. Counter 打分（浮点求和顺序不同，分值末位可能差 ~1e-13）还能再省多少？
3. 按样本内容缓存能再省多少？

候选：
  s0  现状（逐字符循环）
  sA  ASCII 快速路径 + 非 ASCII 仍走 s0 打分   → 逐位等价
  sB  ASCII 快速路径 + Counter 打分            → 分值末位可能差
  sC  sB + 内容缓存
  sD  sA + 内容缓存                             → 逐位等价

计时纪律：每档独立进程状态、缓存每轮清空后再量，取两轮较小值。
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = HERE.parent / "数据"
DATA.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT))

from w2l.commands import grep as grep_mod  # noqa: E402

TARGET = sys.argv[1] if len(sys.argv) > 1 else "E:/1"


def _weight(code: int) -> float:
    if 32 <= code < 127:
        return 1.0
    if 0x3400 <= code <= 0x4DBF or 0x4E00 <= code <= 0x9FFF:
        return 3.0
    if 0x3000 <= code <= 0x303F or 0xFF00 <= code <= 0xFFEF:
        return 1.0
    if code in (9, 10, 13):
        return 0.5
    if code >= 0x80:
        return 0.2
    return 0.0


def score_counter(text: str) -> float:
    if not text:
        return 0.0
    total = 0.0
    for char, count in Counter(text).items():
        total += _weight(ord(char)) * count
    return total / len(text)


def detect_scorer(sample: bytes, scorer) -> str:
    best_encoding = "utf-8"
    best_score = -1.0
    for encoding in grep_mod._candidate_encodings():
        text = grep_mod._decode_sample(sample, encoding)
        if text is None:
            continue
        score = scorer(text)
        if score > best_score + grep_mod._SCORE_MARGIN:
            best_score = score
            best_encoding = encoding
    return best_encoding


def s0(sample: bytes) -> str:
    return grep_mod._detect_encoding(sample)


def sA(sample: bytes) -> str:
    if sample.isascii():
        return "utf-8"
    return detect_scorer(sample, grep_mod._text_score)


def sB(sample: bytes) -> str:
    if sample.isascii():
        return "utf-8"
    return detect_scorer(sample, score_counter)


_CACHE_C: dict[bytes, str] = {}
_CACHE_D: dict[bytes, str] = {}


def sC(sample: bytes) -> str:
    hit = _CACHE_C.get(sample)
    if hit is not None:
        return hit
    result = sB(sample)
    if len(_CACHE_C) < 200000:
        _CACHE_C[sample] = result
    return result


def sD(sample: bytes) -> str:
    hit = _CACHE_D.get(sample)
    if hit is not None:
        return hit
    result = sA(sample)
    if len(_CACHE_D) < 200000:
        _CACHE_D[sample] = result
    return result


def collect_samples(root: str) -> list[bytes]:
    samples: list[bytes] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            try:
                with open(os.path.join(dirpath, name), "rb") as handle:
                    samples.append(handle.read(grep_mod._SNIFF_SIZE))
            except OSError:
                continue
    return samples


def main() -> int:
    samples = collect_samples(TARGET)
    report: dict = {"target": TARGET, "samples": len(samples)}

    # 正确性：五个实现的判定必须与 s0 完全一致
    mismatches: list[dict] = []
    for index, sample in enumerate(samples):
        base = s0(sample)
        for name, func in (("sA", sA), ("sB", sB), ("sC", sC), ("sD", sD)):
            got = func(sample)
            if got != base:
                mismatches.append({"index": index, "impl": name, "base": base, "got": got})
        if mismatches:
            break
    report["mismatches"] = mismatches
    report["correct"] = not mismatches
    if mismatches:
        print("[不一致] " + json.dumps(mismatches[:5], ensure_ascii=False))

    # 计时：每档每轮清空缓存，独立预热，取两轮较小值
    variants = (("s0", s0), ("sA", sA), ("sB", sB), ("sC", sC), ("sD", sD))
    timings: dict = {}
    for name, func in variants:
        best = None
        for round_index in range(2):
            _CACHE_C.clear()
            _CACHE_D.clear()
            func(samples[0]) if samples else None  # 预热：把代码路径跑热
            start = time.perf_counter()
            for sample in samples:
                func(sample)
            elapsed = time.perf_counter() - start
            best = elapsed if best is None else min(best, elapsed)
        timings[name] = round(best, 3)
    report["timings"] = timings
    report["speedup"] = {k: round(timings["s0"] / v, 2) for k, v in timings.items() if v}

    # 缓存命中与内存
    distinct = len(set(samples))
    report["distinct_samples"] = distinct
    report["cache_hit_ratio"] = round(1 - distinct / len(samples), 6)
    report["cache_bytes_if_raw"] = distinct * 8192

    out = DATA / "t1206_score_bench2.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[写入] {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
