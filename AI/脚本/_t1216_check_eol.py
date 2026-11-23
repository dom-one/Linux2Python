#!/usr/bin/env python
"""检查工作区与 HEAD 的换行符差异（整文件 diff 的成因）。

用法: python AI/脚本/_t1216_check_eol.py
输出每个文件的: 工作区 CRLF/LF 行数、HEAD 版本 CRLF/LF 行数。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

FILES = [
    "README.md",
    "w2l/encoding.py",
    "w2l/commands/awk_lite.py",
    "w2l/commands/cat.py",
    "w2l/commands/grep.py",
    "w2l/commands/head.py",
    "w2l/commands/sed.py",
    "w2l/commands/tail.py",
    "w2l/commands/wc.py",
    "tests/test_encoding.py",
]


def counts(data: bytes) -> tuple[int, int]:
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    return crlf, lf


def main() -> int:
    print(f"{'文件':28} {'工作区(CRLF/LF)':>18} {'HEAD(CRLF/LF)':>18}  判定")
    for name in FILES:
        path = ROOT / name
        work = path.read_bytes() if path.exists() else b""
        got = subprocess.run(
            ["git", "show", f"HEAD:{name}"], cwd=str(ROOT),
            capture_output=True,
        )
        head = got.stdout if got.returncode == 0 else b""
        wc, wl = counts(work)
        hc, hl = counts(head)
        if not head:
            verdict = "新文件"
        elif (wc > 0) == (hc > 0):
            verdict = "一致"
        else:
            verdict = "★翻转"
        print(f"{name:28} {wc:>8}/{wl:<9} {hc:>8}/{hl:<9}  {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
