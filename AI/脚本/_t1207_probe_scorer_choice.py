#!/usr/bin/env python
"""探针：给非 ASCII 样本选打分实现（Counter 逐类统计 vs translate 分桶）。

背景：t1206 定下「ASCII 快速路径 + 向量化打分」这条路线，
但向量化有两种做法，在中文语料上差别可能很大：
  c1  Counter：统计每个不同字符的出现次数，再按类别汇总
      → Python 层的循环长度是「不同字符数」，中文语料里接近总字数
  c2  translate：把字符按类别映射成标记字符，再用 str.count 数各类个数
      → Python 层的循环长度恒为 5，与语料无关
  c3  translate + 正则数高位区间（只建 128 项的小表，不建 2.7 万项大表）

语料：真实树 E:/1（以 ASCII 为主）+ 现场造的 GBK 中文语料（汉字为主）。
判据：三者判出的编码必须与现状（逐字符循环）完全一致。
"""

from __future__ import annotations

import json
import os
import re
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

# ---------------------------------------------------------------------------
# 权重表（与现状一致：可打印 ASCII 1.0，汉字 3.0，全角 1.0，换行类 0.5，高位 0.2）
# ---------------------------------------------------------------------------
_CJK_RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF))
_FULLWIDTH_RANGES = ((0x3000, 0x303F), (0xFF00, 0xFFEF))


def _weight(code: int) -> float:
    if 32 <= code < 127:
        return 1.0
    for low, high in _CJK_RANGES:
        if low <= code <= high:
            return 3.0
    for low, high in _FULLWIDTH_RANGES:
        if low <= code <= high:
            return 1.0
    if code in (9, 10, 13):
        return 0.5
    if code >= 0x80:
        return 0.2
    return 0.0


# ---------------------------------------------------------------------------
# c1：Counter
# ---------------------------------------------------------------------------
def score_c1(text: str) -> float:
    if not text:
        return 0.0
    total = 0.0
    for char, count in Counter(text).items():
        total += _weight(ord(char)) * count
    return total / len(text)


# ---------------------------------------------------------------------------
# c2：translate + 大表
# ---------------------------------------------------------------------------
def _build_big_table() -> dict[int, str]:
    table: dict[int, str] = {}
    for code in range(0x20):
        table[code] = "t" if code in (9, 10, 13) else "x"
    for code in range(0x20, 0x7F):
        table[code] = "a"
    table[0x7F] = "x"
    for low, high in _FULLWIDTH_RANGES:
        for code in range(low, high + 1):
            table[code] = "f"
    for low, high in _CJK_RANGES:
        for code in range(low, high + 1):
            table[code] = "c"
    return table


_BIG_TABLE = _build_big_table()


def score_c2(text: str) -> float:
    if not text:
        return 0.0
    marked = text.translate(_BIG_TABLE)
    n_a = marked.count("a")
    n_t = marked.count("t")
    n_x = marked.count("x")
    n_c = marked.count("c")
    n_f = marked.count("f")
    n_high = len(text) - n_a - n_t - n_x - n_c - n_f
    total = n_a * 1.0 + n_c * 3.0 + n_f * 1.0 + n_t * 0.5 + n_high * 0.2
    return total / len(text)


# ---------------------------------------------------------------------------
# c3：translate 小表（只 ASCII）+ 正则数高位区间
# ---------------------------------------------------------------------------
_SMALL_TABLE: dict[int, str] = {}
for _code in range(0x20):
    _SMALL_TABLE[_code] = "t" if _code in (9, 10, 13) else "x"
for _code in range(0x20, 0x7F):
    _SMALL_TABLE[_code] = "a"
_SMALL_TABLE[0x7F] = "x"

_CJK_RE = re.compile(r"[㐀-䶿一-鿿]")
_FULLWIDTH_RE = re.compile(r"[　-〿＀-￯]")


def score_c3(text: str) -> float:
    if not text:
        return 0.0
    marked = text.translate(_SMALL_TABLE)
    n_a = marked.count("a")
    n_t = marked.count("t")
    n_x = marked.count("x")
    n_c = len(_CJK_RE.findall(text))
    n_f = len(_FULLWIDTH_RE.findall(text))
    n_high = len(text) - n_a - n_t - n_x - n_c - n_f
    total = n_a * 1.0 + n_c * 3.0 + n_f * 1.0 + n_t * 0.5 + n_high * 0.2
    return total / len(text)


# ---------------------------------------------------------------------------
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


def make_scorer(scorer):
    def detect(sample: bytes) -> str:
        if sample.isascii():
            return "utf-8"
        return detect_with(sample, scorer)

    return detect


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


def make_cjk_corpus() -> list[bytes]:
    """现场造 GBK 中文语料（汉字占多数），模拟中文仓库。"""
    samples: list[bytes] = []
    hanzi = "中文编码判定测试文件内容样本汉字繁體字體コード性能优化提速共享模块抽取重复实现逐字符打分循环统计计数桶标记字符类别权重换行制表符控制字符边界情况随机二进制数据"
    for index in range(200):
        body = (hanzi * 40)[: 3000 + index]
        samples.append(body.encode("gb18030"))
    mixed = ("ascii english text " + hanzi * 20).encode("gb18030")
    samples.extend([mixed] * 20)
    return samples


def main() -> int:
    real = collect_samples(TARGET)
    cjk = make_cjk_corpus()
    report: dict = {"target": TARGET, "real_samples": len(real), "cjk_samples": len(cjk)}

    variants = {
        "c1_counter": make_scorer(score_c1),
        "c2_bigtable": make_scorer(score_c2),
        "c3_smalltable": make_scorer(score_c3),
    }

    # 正确性：判定必须与现状一致（真实语料 + 中文语料）
    mismatches: list[dict] = []
    for label, samples in (("real", real), ("cjk", cjk)):
        for index, sample in enumerate(samples):
            base = grep_mod._detect_encoding(sample)
            for name, func in variants.items():
                got = func(sample)
                if got != base:
                    mismatches.append({"corpus": label, "index": index, "impl": name, "base": base, "got": got})
                    if len(mismatches) >= 10:
                        break
            if len(mismatches) >= 10:
                break
        if len(mismatches) >= 10:
            break
    report["mismatches"] = mismatches
    report["correct"] = not mismatches
    if mismatches:
        print("[不一致] " + json.dumps(mismatches[:5], ensure_ascii=False))

    # 打分值与现状的差异（浮点求和顺序不同，末位可能差）
    max_delta = 0.0
    exact = 0
    total = 0
    for label, samples in (("real", real[:1500]), ("cjk", cjk)):
        for sample in samples:
            for encoding in grep_mod._candidate_encodings():
                text = grep_mod._decode_sample(sample, encoding)
                if text is None:
                    continue
                old = grep_mod._text_score(text)
                for name, scorer in (("c1", score_c1), ("c2", score_c2), ("c3", score_c3)):
                    new = scorer(text)
                    total += 1
                    if old == new:
                        exact += 1
                    else:
                        max_delta = max(max_delta, abs(old - new))
    report["score_exact_ratio"] = round(exact / total, 6) if total else 1.0
    report["score_max_delta"] = max_delta

    # 计时：只看非 ASCII 样本（ASCII 样本三档走同一条快速路径）
    non_ascii_real = [s for s in real if not s.isascii()]
    report["real_non_ascii"] = len(non_ascii_real)

    timings: dict = {}
    for name, func in variants.items():
        for label, samples in (("real_non_ascii", non_ascii_real), ("cjk", cjk)):
            best = None
            for _ in range(3):
                start = time.perf_counter()
                for sample in samples:
                    func(sample)
                elapsed = time.perf_counter() - start
                best = elapsed if best is None else min(best, elapsed)
            timings[f"{name}/{label}"] = round(best, 4)
    report["timings"] = timings

    # 现状在同样两批样本上的耗时，作为对照
    for label, samples in (("real_non_ascii", non_ascii_real), ("cjk", cjk)):
        best = None
        for _ in range(3):
            start = time.perf_counter()
            for sample in samples:
                grep_mod._detect_encoding(sample)
            elapsed = time.perf_counter() - start
            best = elapsed if best is None else min(best, elapsed)
        timings[f"baseline/{label}"] = round(best, 4)
    report["timings"] = timings
    for key in ("real_non_ascii", "cjk"):
        base = timings[f"baseline/{key}"]
        for name in ("c1_counter", "c2_bigtable", "c3_smalltable"):
            report.setdefault("speedup", {})[f"{name}/{key}"] = round(base / timings[f"{name}/{key}"], 2)

    out = DATA / "t1207_scorer_choice.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[写入] {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
