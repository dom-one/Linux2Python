#!/usr/bin/env python
"""探针：改后 grep 的端到端耗时——改前 / 改后 / 完全不判定，三个口径同场对比。

改前实现从 git HEAD 的 grep.py 里抽出来（AST 定位，只抽编码函数），
在同一进程里和改后的共享模块轮流跑同一棵目录树：

  A. 改前判定（逐字符 Python 打分）
  B. 改后判定（w2l/encoding.py，分桶计数）
  C. 不判定（编码固定 utf-8）——判定成本的下限

命中数必须一致，否则说明「提速」是靠少判内容换来的。
预热后测量：Windows Defender 会扫新文件，不预热量到的是杀毒时间。
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
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
PATTERN = "import"

WANT_FUNCS = ("_detect_encoding", "_candidate_encodings", "_decode_sample", "_text_score")
WANT_CONSTS = ("_SNIFF_SIZE", "_FALLBACK_ENCODINGS", "_SCORE_MARGIN", "_CJK_RANGES")


def load_original_detect():
    """从 git HEAD 的 grep.py 抽出改前的编码判定。"""
    source = subprocess.run(
        ["git", "show", "HEAD:w2l/commands/grep.py"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
    )
    if source.returncode != 0:
        raise RuntimeError(f"取不到改前的 grep.py：{source.stderr}")
    text = source.stdout
    tree = ast.parse(text)
    chunks = ["import codecs", "import locale", ""]
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in WANT_FUNCS:
            chunks.append(ast.get_source_segment(text, node))
            chunks.append("")
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(n in WANT_CONSTS for n in names):
                chunks.append(ast.get_source_segment(text, node))
    namespace: dict = {"__name__": "orig_encoding"}
    exec(compile("\n".join(chunks), "<orig_grep_encoding>", "exec"), namespace)
    return namespace["_detect_encoding"]


def collect_files(root: str) -> list[str]:
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            files.append(os.path.join(dirpath, name))
    files.sort()
    return files


def run_variant(files: list[str], detect) -> tuple[float, int]:
    """按给定判定函数跑一遍搜索，返回 (耗时, 命中数)。"""
    regex = re.compile(PATTERN)
    hits = 0
    start = time.perf_counter()
    for raw in files:
        path = Path(raw)
        try:
            with path.open("rb") as handle:
                sample = handle.read(grep_mod._SNIFF_SIZE)
                if b"\x00" in sample:
                    continue
                encoding = detect(sample)
                handle.seek(0)
                for line in handle:
                    text = line.decode(encoding, errors="replace")
                    if regex.search(text) is not None:
                        hits += 1
        except OSError:
            continue
    return time.perf_counter() - start, hits


def main() -> int:
    files = collect_files(TARGET)
    report: dict = {"target": TARGET, "files": len(files), "pattern": PATTERN}

    original_detect = load_original_detect()
    new_detect = grep_mod._detect_encoding  # 改后：共享模块那份
    stub_detect = lambda sample: "utf-8"  # noqa: E731

    # 预热（丢弃）
    run_variant(files[:200], new_detect)

    variants = {"before": original_detect, "after": new_detect, "stub": stub_detect}
    runs: list[dict] = []
    for round_index in range(2):
        for name, detect in variants.items():
            elapsed, hits = run_variant(files, detect)
            runs.append({"variant": name, "round": round_index,
                         "seconds": round(elapsed, 3), "hits": hits})
    report["runs"] = runs

    best: dict = {}
    hit_counts: dict = {}
    for name in variants:
        values = [r["seconds"] for r in runs if r["variant"] == name]
        best[name] = min(values)
        hit_counts[name] = {r["hits"] for r in runs if r["variant"] == name}
    report["best_seconds"] = best
    report["hit_counts"] = {k: sorted(v) for k, v in hit_counts.items()}
    report["hits_consistent"] = len({frozenset(v) for v in hit_counts.values()}) == 1
    report["speedup_endtoend"] = round(best["before"] / best["after"], 2) if best["after"] else 0
    report["detect_share_after"] = round((best["after"] - best["stub"]) / best["after"], 4)
    report["detect_share_before"] = round((best["before"] - best["stub"]) / best["before"], 4)

    out = DATA / "t1214_grep_endtoend_after.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[写入] {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
