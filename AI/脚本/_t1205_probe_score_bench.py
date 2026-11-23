#!/usr/bin/env python
"""探针：给编码打分找更快的实现，并与现有实现逐文件比对结果。

背景：t1203 测出「逐字符 Python 循环打分」占编码判定的 97.5%，
t1204 测出编码判定占 grep 端到端耗时的 74.5%。这一支要回答：
哪套打分实现更快，且**判定结果与现状完全一致**。

候选实现：
  S0  现状：逐字符 Python 循环
  S1  Counter：一次 C 层统计，按不同字符的权重汇总
  S2  S1 + 纯 ASCII 快速路径（ASCII 样本一律判 utf-8）
  S3  S2 + 按样本内容缓存（同样内容只判一次）

判据：对每一份真实文件，四个实现判出的编码必须与 S0 完全一致，
有任何一条不同就报错退出。
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

_CJK = grep_mod._CJK_RANGES


# ---------------------------------------------------------------------------
# S0：现状（直接复用 grep.py 里的实现，保证基线就是线上代码）
# ---------------------------------------------------------------------------
def s0(sample: bytes) -> str:
    return grep_mod._detect_encoding(sample)


# ---------------------------------------------------------------------------
# S1：Counter 版打分
# ---------------------------------------------------------------------------
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


def detect_with(sample: bytes, scorer) -> str:
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


def s1(sample: bytes) -> str:
    return detect_with(sample, score_counter)


# ---------------------------------------------------------------------------
# S2：S1 + 纯 ASCII 快速路径
# ---------------------------------------------------------------------------
def s2(sample: bytes) -> str:
    if sample.isascii():
        # 全 ASCII 时各候选编码解出的文本完全相同，打分相同，
        # 第一个候选 utf-8 必然胜出，与逐个打分的结论一致。
        return "utf-8"
    return detect_with(sample, score_counter)


# ---------------------------------------------------------------------------
# S3：S2 + 按样本内容缓存
# ---------------------------------------------------------------------------
_CACHE: dict[bytes, str] = {}


def s3(sample: bytes) -> str:
    hit = _CACHE.get(sample)
    if hit is not None:
        return hit
    result = s2(sample)
    if len(_CACHE) < 100000:
        _CACHE[sample] = result
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
    print(f"[收集] 扫描 {TARGET} ...")
    samples = collect_samples(TARGET)
    print(f"[收集] {len(samples)} 个样本")

    report: dict = {"target": TARGET, "samples": len(samples)}

    # 正确性：四个实现必须给出完全一致的判定
    mismatches: list[dict] = []
    for index, sample in enumerate(samples):
        base = s0(sample)
        for name, func in (("s1", s1), ("s2", s2), ("s3", s3)):
            got = func(sample)
            if got != base:
                mismatches.append({"index": index, "impl": name, "base": base, "got": got})
                if len(mismatches) >= 20:
                    break
        if len(mismatches) >= 20:
            break
    report["mismatches"] = mismatches
    report["correct"] = not mismatches
    if mismatches:
        print("[不一致] 判定结果与现状不同：")
        for item in mismatches[:10]:
            print("  " + json.dumps(item, ensure_ascii=False))
        (DATA / "t1205_score_bench.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return 1

    # 打分值是否逐位一致（顺序不同可能带来末位差异，记下来）
    exact = 0
    total = 0
    max_delta = 0.0
    for sample in samples[:2000]:
        for encoding in grep_mod._candidate_encodings():
            text = grep_mod._decode_sample(sample, encoding)
            if text is None:
                continue
            old = grep_mod._text_score(text)
            new = score_counter(text)
            total += 1
            if old == new:
                exact += 1
            else:
                max_delta = max(max_delta, abs(old - new))
    report["score_exact_ratio"] = round(exact / total, 6) if total else 1.0
    report["score_max_delta"] = max_delta
    report["score_compared"] = total

    # 性能：预热后各跑两遍取较小值
    timings: dict = {}
    for name, func in (("s0", s0), ("s1", s1), ("s2", s2), ("s3", s3)):
        func(samples[0]) if samples else None
        best = None
        for _ in range(2):
            start = time.perf_counter()
            for sample in samples:
                func(sample)
            elapsed = time.perf_counter() - start
            best = elapsed if best is None else min(best, elapsed)
        timings[name] = round(best, 3)
    report["timings"] = timings
    if timings.get("s0"):
        report["speedup"] = {k: round(timings["s0"] / v, 2) for k, v in timings.items() if v}

    # 缓存命中率
    distinct = len({sample for sample in samples})
    report["distinct_samples"] = distinct
    report["cache_hit_ratio"] = round(1 - distinct / len(samples), 6) if samples else 0

    # ASCII 占比
    report["ascii_ratio"] = round(sum(1 for s in samples if s.isascii()) / len(samples), 4)

    out = DATA / "t1205_score_bench.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[写入] {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
