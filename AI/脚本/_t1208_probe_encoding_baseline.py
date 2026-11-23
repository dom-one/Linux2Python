#!/usr/bin/env python
"""探针：测共享编码模块的建表开销，并固化「改前」输出基线。

两件事：
1. c2 方案要给 str.translate 准备一张约 2.7 万项的码位→标记表，
   这张表在进程启动时建一次会拖慢每条指令，所以要量它的建表时间与内存，
   决定是「启动即建」还是「首次用到再建」。
2. 改动前把 7 个指令在混合语料上的输出（字节级）存下来，
   改完再跑一遍逐字节比对——这是「行为不变」的唯一硬证据。
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

MAIN = str(ROOT / "main.py")


# ---------------------------------------------------------------------------
# 1. 建表开销
# ---------------------------------------------------------------------------
def build_big_table() -> dict[int, str]:
    table: dict[int, str] = {}
    for code in range(0x20):
        table[code] = "t" if code in (9, 10, 13) else "x"
    for code in range(0x20, 0x7F):
        table[code] = "a"
    table[0x7F] = "x"
    for low, high in ((0x3000, 0x303F), (0xFF00, 0xFFEF)):
        for code in range(low, high + 1):
            table[code] = "f"
    for low, high in ((0x3400, 0x4DBF), (0x4E00, 0x9FFF)):
        for code in range(low, high + 1):
            table[code] = "c"
    return table


def measure_table() -> dict:
    """建表开销：时间 + 表项数。

    内存不量了：resource 是 Unix 专有模块，Windows 上没有；
    换个思路看建表是否值得——表项数固定（约 2.7 万），
    建一次大约几毫秒，而每条指令都会用到，所以「首次用到再建」更划算。
    """
    start = time.perf_counter()
    table = build_big_table()
    elapsed = time.perf_counter() - start
    return {
        "entries": len(table),
        "build_seconds": round(elapsed, 4),
    }


# ---------------------------------------------------------------------------
# 2. 混合语料
# ---------------------------------------------------------------------------
def make_corpus(base: Path) -> Path:
    corpus = base / "enc_corpus"
    corpus.mkdir(parents=True, exist_ok=True)

    (corpus / "ascii.txt").write_bytes(b"hello world\nplain ascii text\nline three\n")
    (corpus / "utf8_cn.txt").write_bytes("中文内容\n这是 UTF-8 编码的正文\n第三行\n".encode("utf-8"))
    (corpus / "gbk_cn.txt").write_bytes("中文内容\n这是 GBK 编码的正文\n第三行\n".encode("gb18030"))
    (corpus / "mixed.txt").write_bytes("ascii line\n中文混合\n".encode("gb18030"))
    (corpus / "fullwidth.txt").write_bytes("全角标点，测试。\n".encode("utf-8"))
    (corpus / "binary.bin").write_bytes(bytes(range(256)) * 4)
    (corpus / "nul.txt").write_bytes(b"has nul\x00inside\nsecond line\n")
    (corpus / "empty.txt").write_bytes(b"")
    (corpus / "latin.txt").write_bytes("café naïve\n".encode("latin-1"))
    (corpus / "big_ascii.txt").write_bytes((b"x" * 100 + b"\n") * 500)
    (corpus / "big_gbk.txt").write_bytes(("中文" * 50 + "\n").encode("gb18030") * 200)
    return corpus


# ---------------------------------------------------------------------------
# 3. 基线捕获
# ---------------------------------------------------------------------------
CASES: list[list[str]] = []


def build_cases(corpus: Path) -> list[list[str]]:
    c = str(corpus)
    return [
        ["cat", f"{c}/ascii.txt"],
        ["cat", f"{c}/utf8_cn.txt"],
        ["cat", f"{c}/gbk_cn.txt"],
        ["cat", f"{c}/mixed.txt"],
        ["cat", f"{c}/fullwidth.txt"],
        ["cat", f"{c}/binary.bin"],
        ["cat", f"{c}/nul.txt"],
        ["cat", f"{c}/empty.txt"],
        ["cat", f"{c}/latin.txt"],
        ["cat", "-n", f"{c}/utf8_cn.txt"],
        ["cat", "-v", f"{c}/gbk_cn.txt"],
        ["head", "-n", "2", f"{c}/utf8_cn.txt"],
        ["head", "-c", "20", f"{c}/gbk_cn.txt"],
        ["head", f"{c}/binary.bin"],
        ["tail", "-n", "2", f"{c}/utf8_cn.txt"],
        ["tail", "-c", "20", f"{c}/gbk_cn.txt"],
        ["wc", "-m", f"{c}/utf8_cn.txt"],
        ["wc", "-c", "-L", f"{c}/gbk_cn.txt"],
        ["wc", "-l", "-w", f"{c}/binary.bin"],
        ["grep", "中文", f"{c}/utf8_cn.txt"],
        ["grep", "中文", f"{c}/gbk_cn.txt"],
        ["grep", "-n", "line", f"{c}/ascii.txt"],
        ["grep", "-c", "a", f"{c}/ascii.txt"],
        ["sed", "s/中/中/g", f"{c}/utf8_cn.txt"],
        ["sed", "-n", "2p", f"{c}/gbk_cn.txt"],
        ["awk-lite", "{print $1}", f"{c}/ascii.txt"],
        ["awk-lite", "-F", ",", "{print $2}", f"{c}/gbk_cn.txt"],
        ["find", c, "-name", "*.txt"],
        ["find", c, "-type", "f", "-name", "*.cn.txt"],
        ["ls", "-l", c],
    ]


def run_case(args: list[str]) -> dict:
    proc = subprocess.run(
        [sys.executable, MAIN, *args],
        capture_output=True,
    )
    return {
        "args": args,
        "code": proc.returncode,
        "stdout": proc.stdout.hex(),
        "stderr": proc.stderr.hex(),
    }


def main() -> int:
    table_info = measure_table()
    corpus = make_corpus(DATA)
    cases = build_cases(corpus)
    results = [run_case(args) for args in cases]

    out = DATA / "t1208_encoding_baseline.json"
    payload = {
        "table": table_info,
        "corpus": str(corpus),
        "cases": results,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[建表] " + json.dumps(table_info, ensure_ascii=False))
    print(f"[基线] {len(results)} 组用例 → {out}")
    for item in results:
        print(f"  code={item['code']} stdout={len(item['stdout'])//2}B {' '.join(item['args'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
