"""探针七：钉死列宽规则的两个悬案。

悬案 A：单文件单列（-l big.txt）输出 '1 big.txt' 不补空格，
        而多文件单列（-l a.txt b.txt）输出 ' 3 a.txt' 补到宽度 2。
        宽度到底怎么算？

悬案 B：标准输入出现时列宽至少是 7，为什么？
        是硬编码下限，还是跟别的什么有关？

这一轮用「宽窄字节差」构造判定：
- 60 字节 + 60 字节 = total 120（3 位），单文件 60（2 位）
  → 看宽度是 2 还是 3，能判定 total 行算不算
- 999999 字节单文件（6 位）与 5 字节单文件（1 位）
  → 看单文件多列时宽度取谁
- 标准输入喂 12345678 字节
  → 看 stdin 的宽度下限是固定 7 还是随内容长
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc7"
TMP.mkdir(exist_ok=True)


def setup() -> None:
    # 各 60 字节 1 行 → total 120 字节（3 位）
    (TMP / "m1.txt").write_bytes(b"a" * 59 + b"\n")
    (TMP / "m2.txt").write_bytes(b"b" * 59 + b"\n")
    # 6 位字节、1 行
    (TMP / "h6.txt").write_bytes(b"c" * 999998 + b"\n")
    # 1 位字节、1 行
    (TMP / "s1.txt").write_bytes(b"d\n")
    # 行数 3 位、字节 3 位、词数 3 位
    (TMP / "w3.txt").write_bytes(b"e f\n" * 100)
    # 行数 4 位、字节 4 位
    (TMP / "l4.txt").write_bytes(b"g\n" * 1000)


def wc(args, stdin_data=None, loc="C.UTF-8"):
    env = dict(os.environ)
    env["LC_ALL"] = loc
    proc = subprocess.run(
        [WC] + args,
        cwd=str(TMP),
        input=stdin_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr


def show(label, args, stdin_data=None, loc="C.UTF-8"):
    code, out, err = wc(args, stdin_data, loc)
    print(f"{label}")
    print(f"    args={args!r} rc={code}")
    for line in out.splitlines():
        edges = [m.end() for m in re.finditer(r"\d+", line)]
        print(f"    | {line!r}  右边界={edges}")
    if err:
        print(f"    err={err!r}")


def main() -> None:
    setup()

    print("== A1. total 行算不算进宽度 ==")
    show("m1+m2 只打 -l（各 60 字节，total 120 字节）", ["-l", "m1.txt", "m2.txt"])
    show("m1+m2 打 -lw", ["-lw", "m1.txt", "m2.txt"])
    show("m1+m2 打 -lwc", ["-lwc", "m1.txt", "m2.txt"])
    print()

    print("== A2. 单文件多列时宽度取谁 ==")
    show("h6.txt 只打 -l", ["-l", "h6.txt"])
    show("h6.txt 打 -lw", ["-lw", "h6.txt"])
    show("h6.txt 打 -lwc", ["-lwc", "h6.txt"])
    show("s1.txt 打 -lw", ["-lw", "s1.txt"])
    show("h6.txt + s1.txt 只打 -l", ["-l", "h6.txt", "s1.txt"])
    show("h6.txt + s1.txt 打 -lw", ["-lw", "h6.txt", "s1.txt"])
    print()

    print("== A3. 隐藏列的位数 ==")
    show("w3.txt 只打 -l（行 100 词 200 字节 600）", ["-l", "w3.txt"])
    show("w3.txt 打 -lw", ["-lw", "w3.txt"])
    show("l4.txt 只打 -l（行 1000 字节 2000）", ["-l", "l4.txt"])
    show("l4.txt 打 -lw", ["-lw", "l4.txt"])
    print()

    print("== B. 标准输入的宽度下限 ==")
    show("stdin 1 列 -l", ["-l"], b"a b\nc\n")
    show("stdin 2 列 -lw", ["-lw"], b"a b\nc\n")
    show("stdin 2 列大字节", ["-lw"], b"x" * 12345678 + b"\n")
    show("stdin 3 列大字节", ["-lwc"], b"x" * 12345678 + b"\n")
    show("stdin 3 列 9 位字节", ["-lwc"], b"x" * 123456789 + b"\n")
    show("stdin + s1.txt -lw", ["-lw", "-", "s1.txt"], b"a\n")
    show("stdin + h6.txt -lw", ["-lw", "-", "h6.txt"], b"a\n")
    show("stdin + h6.txt -lwc", ["-lwc", "-", "h6.txt"], b"a\n")
    print()

    print("== C. 单文件单列到底补不补 ==")
    show("h6.txt 只打 -c", ["-c", "h6.txt"])
    show("h6.txt 只打 -L", ["-L", "h6.txt"])
    show("h6.txt 只打 -m", ["-m", "h6.txt"])
    print()

    print("== D. -L 列宽与 tab ==")
    show("tab 文件 -lwcL", ["-lwcL", "tab9.txt"])
    print()

    print("== E. 缺文件的宽度 ==")
    show("存在+不存在 -lwc", ["-lwc", "s1.txt", "nope.txt"])
    show("存在+不存在+存在 -lwc", ["-lwc", "s1.txt", "nope.txt", "m1.txt"])


if __name__ == "__main__":
    main()
