#!/usr/bin/env python
"""全量核对：新共享模块的判定结果必须与「改前的原始实现」逐文件一致。

基准实现从 git 里取改前的 `w2l/commands/grep.py`（权威「改前」版本），
但**只抽取编码相关的函数与常量**再执行——整文件 import 会因 `from ..context`
这类包内相对导入失败（按路径加载的模块没有包上下文）。

核对两条：
1. detect_encoding：真实文件 + 中文语料，判定必须完全相同；
2. text_score：分值允许末位差异（浮点求和顺序不同），但差异必须远小于门槛 0.3。
   同时另算一遍「按新分值重新判定」的结果，确认仍然一致。
"""

from __future__ import annotations

import ast
import json
import locale
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = HERE.parent / "数据"

sys.path.insert(0, str(ROOT))

from w2l import encoding as new_mod  # noqa: E402

TARGET = sys.argv[1] if len(sys.argv) > 1 else "E:/1"

WANT_FUNCS = ("_detect_encoding", "_candidate_encodings", "_decode_sample", "_text_score")
WANT_CONSTS = ("_SNIFF_SIZE", "_FALLBACK_ENCODINGS", "_SCORE_MARGIN", "_CJK_RANGES")


def load_original() -> dict:
    """从 git 取改前的 grep.py，抽出编码函数执行，返回命名空间。"""
    source = subprocess.run(
        ["git", "show", "HEAD:w2l/commands/grep.py"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
    )
    if source.returncode != 0:
        raise RuntimeError(f"取不到改前的 grep.py：{source.stderr}")
    text = source.stdout
    (DATA / "_orig_grep_for_compare.py").write_text(text, encoding="utf-8")

    tree = ast.parse(text)
    chunks: list[str] = ["import codecs", "import locale", ""]
    found_funcs: list[str] = []
    found_consts: list[str] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in WANT_FUNCS:
            segment = ast.get_source_segment(text, node)
            assert segment is not None
            chunks.append(segment)
            chunks.append("")
            found_funcs.append(node.name)
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(n in WANT_CONSTS for n in names):
                segment = ast.get_source_segment(text, node)
                assert segment is not None
                chunks.append(segment)
                found_consts.extend(n for n in names if n in WANT_CONSTS)

    missing = [n for n in WANT_FUNCS if n not in found_funcs]
    missing_c = [n for n in WANT_CONSTS if n not in found_consts]
    if missing or missing_c:
        raise RuntimeError(f"改前源码里没抽到：函数 {missing} 常量 {missing_c}")

    namespace: dict = {"__name__": "orig_encoding"}
    exec(compile("\n".join(chunks), "<orig_grep_encoding>", "exec"), namespace)
    for name in WANT_FUNCS:
        if name not in namespace:
            raise RuntimeError(f"抽取后命名空间里缺 {name}")
    return namespace


def collect_samples(root: str) -> list[bytes]:
    samples: list[bytes] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            try:
                with open(os.path.join(dirpath, name), "rb") as handle:
                    samples.append(handle.read(new_mod.SNIFF_SIZE))
            except OSError:
                continue
    return samples


def make_cjk_corpus() -> list[bytes]:
    hanzi = (
        "中文编码判定测试文件内容样本汉字繁體字體コード性能优化提速共享模块抽取重复实现"
        "逐字符打分循环统计计数桶标记字符类别权重换行制表符控制字符边界情况随机二进制数据"
    )
    samples = []
    for index in range(200):
        body = (hanzi * 40)[: 3000 + index]
        samples.append(body.encode("gb18030"))
    samples.extend([("ascii english text " + hanzi * 20).encode("gb18030")] * 20)
    return samples


def main() -> int:
    old = load_original()
    old_detect = old["_detect_encoding"]
    old_candidates = old["_candidate_encodings"]
    old_decode = old["_decode_sample"]
    old_score = old["_text_score"]

    report: dict = {"target": TARGET}

    real = collect_samples(TARGET)
    cjk = make_cjk_corpus()
    report["real_samples"] = len(real)
    report["cjk_samples"] = len(cjk)

    mismatches: list[dict] = []
    max_delta = 0.0
    exact = 0
    total = 0

    for label, samples in (("real", real), ("cjk", cjk)):
        for index, sample in enumerate(samples):
            base = old_detect(sample)
            got = new_mod.detect_encoding(sample)
            if base != got:
                mismatches.append({"corpus": label, "index": index, "base": base, "got": got})
                if len(mismatches) >= 20:
                    break
            for encoding in old_candidates():
                text = old_decode(sample, encoding)
                if text is None:
                    continue
                score_old = old_score(text)
                score_new = new_mod.text_score(text)
                total += 1
                if score_old == score_new:
                    exact += 1
                else:
                    max_delta = max(max_delta, abs(score_old - score_new))
        if len(mismatches) >= 20:
            break

    report["mismatches"] = mismatches
    report["identical"] = not mismatches
    report["score_exact_ratio"] = round(exact / total, 6) if total else 1.0
    report["score_max_delta"] = max_delta
    report["score_compared"] = total
    report["margin"] = new_mod.SCORE_MARGIN
    report["delta_vs_margin"] = (max_delta / new_mod.SCORE_MARGIN) if new_mod.SCORE_MARGIN else 0

    # 计时：改前 vs 改后（判定本身）。每轮取最小值，且改前改后紧挨着跑。
    subset = [s for s in real if not s.isascii()][:3000]
    timings: dict = {}
    for name, func in (("original", old_detect), ("new", new_mod.detect_encoding)):
        best = None
        for _ in range(2):
            start = time.perf_counter()
            for sample in subset:
                func(sample)
            elapsed = time.perf_counter() - start
            best = elapsed if best is None else min(best, elapsed)
        timings[name] = round(best, 4)
    report["timings_non_ascii"] = timings
    report["timings_non_ascii_samples"] = len(subset)
    report["speedup_non_ascii"] = round(timings["original"] / timings["new"], 2) if timings["new"] else 0

    out = DATA / "t1213_encoding_equiv.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[写入] {out}")
    return 0 if not mismatches else 1


if __name__ == "__main__":
    sys.exit(main())
