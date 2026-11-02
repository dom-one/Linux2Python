"""探针第十轮：整数上下界的边界。

GNU 对纯数字和对「数字+后缀」用的是两条不同的溢出路径：
乘后缀时按 intmax 算，纯数字时上界更松（2^63 竟然被接受）。
这里把边界量出来。
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


def check(spec: str) -> str:
    proc = subprocess.run(
        [locate_head(), "-c", spec, "__no_such_file__"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    err = proc.stderr.decode("utf-8", "replace").strip()
    if "Value too large" in err:
        return "溢出"
    if "invalid number" in err:
        return "语法非法"
    if "cannot open" in err:
        return "接受"
    return err or "(无 stderr)"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    print("--- 纯数字上界")
    for spec in [
        "9223372036854775807",   # 2^63 - 1
        "9223372036854775808",   # 2^63
        "18446744073709551615",  # 2^64 - 1
        "18446744073709551616",  # 2^64
        "18446744073709551617",  # 2^64 + 1
        "10000000000000000000",  # 10^19
        "100000000000000000000",  # 10^20
    ]:
        print(f"  {spec:<24} {check(spec)}")

    print("--- 负数下界")
    for spec in [
        "-9223372036854775808",
        "-9223372036854775809",
        "-18446744073709551616",
    ]:
        print(f"  {spec:<24} {check(spec)}")

    print("--- 乘后缀后的边界（1E=2^60 合法，1Z=2^70 溢出）")
    for spec in ["1E", "1EB", "1EiB", "1Z", "1ZB", "1ZiB", "3E", "9E", "18E"]:
        print(f"  {spec:<24} {check(spec)}")

    print("--- 数字里带下划线/空格")
    for spec in ["1_000", " 5", "5 ", "+5", "++5", "--5", "5-", "0x10"]:
        print(f"  {spec!r:<24} {check(spec)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
