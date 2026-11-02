"""探针第八轮：用「文件不存在」这个错误区分后缀是否合法。

head 解析数字在前、打开文件在后，所以：
- 报 invalid number of bytes  → 该后缀非法
- 报 Value too large        → 合法但超出 intmax
- 报 cannot open             → 合法

这样不用真的搬运 GB 级数据就能把整张后缀表测出来。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

GNU_HEAD = r"C:\Program Files\Git\usr\bin\head.exe"


def locate_head() -> str:
    candidate = shutil.which("head")
    if candidate and "System32" not in candidate:
        return candidate
    return GNU_HEAD


def classify(suffix: str) -> str:
    proc = subprocess.run(
        [locate_head(), "-c", f"1{suffix}", "__no_such_file__"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    err = proc.stderr.decode("utf-8", "replace").strip()
    if "invalid number" in err:
        return "非法"
    if "Value too large" in err:
        return "合法但溢出"
    if "cannot open" in err:
        return "合法"
    return f"其他: {err}"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    plain = ["b", "c", "k", "K", "m", "M", "g", "G", "t", "T", "p", "P", "e", "E", "z", "Z", "y", "Y"]
    binary = [f"{c}B" for c in ("b", "k", "K", "m", "M", "G", "T", "P", "E", "Z", "Y")]
    iext = [f"{c}iB" for c in ("k", "K", "m", "M", "G", "T", "P", "E")]

    print("--- 单字母后缀（1024 进制形式）")
    for suffix in plain:
        print(f"  1{suffix:<4} {classify(suffix)}")

    print("--- 字母 + B（1000 进制形式）")
    for suffix in binary:
        print(f"  1{suffix:<4} {classify(suffix)}")

    print("--- 字母 + iB（二进制前缀形式）")
    for suffix in iext:
        print(f"  1{suffix:<4} {classify(suffix)}")

    print("--- 其他")
    for suffix in ["", "B", "iB", "ib", "KIB", "kib", "kBi", "BB", "kb", "Kb"]:
        print(f"  1{suffix:<4} {classify(suffix)}")

    print("--- -n 与 -c 是否同表")
    for suffix in ["k", "kB", "M", "MB", "g", "GB", "b", "ZiB"]:
        proc = subprocess.run(
            [locate_head(), "-n", f"1{suffix}", "__no_such_file__"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        err = proc.stderr.decode("utf-8", "replace").strip()
        print(f"  -n 1{suffix:<4} {err.split(': ')[-1] if err else '(无错误)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
