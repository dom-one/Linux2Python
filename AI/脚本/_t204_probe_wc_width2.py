"""探针五：把 GNU wc 的列宽规则与计数语义钉死。

前四个探针已经归纳出的规则（待验证）：

- 输出列序固定：行数 → 词数 → 字符数(-m) → 字节数(-c) → 最长行(-L)
- 只给 -m 时不出字节列；默认是 行/词/字节
- 整个输出只有一个数字时（单文件或标准输入 + 单列）不补空格
- 其余情况列宽 W = max(隐藏字节数的位数, 已打印列的位数, total 行的位数)
- 标准输入出现时 W 至少是 7

这一轮逐条验证：

1. 只有一个数字时到底补不补空格
2. total 行的隐藏字节数（198 比 99 多一位）算不算进 W
3. total 行的行数（10 比 5 多一位）算不算进 W
4. 隐藏的字符数（3 位）算不算进 W
5. 标准输入的宽度下限是不是 7
6. -L 到底按显示宽度还是按字符数还是按字节
7. 词/行的空白判定
8. 多文件时 total 行的最长行怎么来
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc5"
TMP.mkdir(exist_ok=True)


def setup() -> None:
    # 1. 单文件单列：字节 5 位、行 1 位
    (TMP / "big.txt").write_bytes(b"x" * 12345 + b"\n")
    # 2. 两个文件各 99 字节各 1 行 → total 198（3 位），单文件 99（2 位）
    (TMP / "n1.txt").write_bytes(b"a" * 98 + b"\n")
    (TMP / "n2.txt").write_bytes(b"b" * 98 + b"\n")
    # 3. 两个文件各 5 行，total 10 行（2 位）；字节数保持 1 位
    (TMP / "p1.txt").write_bytes(b"a\n" * 5)
    (TMP / "p2.txt").write_bytes(b"b\n" * 5)
    # 4. 字符 3 位、字节 2 位：ASCII 3 个字符 + 1 个多字节字符
    #    "é" 在 UTF-8 是 2 字节，所以 3 字符 4 字节；这里造 100 个 2 字节字符
    (TMP / "ch.txt").write_bytes(("é" * 100 + "\n").encode("utf-8"))
    # 5. 小数值文件
    (TMP / "s.txt").write_bytes(b"a b\n")
    # 6. -L 的各种行
    (TMP / "l1.txt").write_bytes("abc中文\n".encode("utf-8"))
    (TMP / "l2.txt").write_bytes("中文测试\n第二行\n".encode("utf-8"))
    (TMP / "l3.txt").write_bytes(b"a\r\nbb\r\n")
    (TMP / "l4.txt").write_bytes(b"\n")
    (TMP / "l5.txt").write_bytes(b"")
    (TMP / "l6.txt").write_bytes("ab\n\ncd\n".encode("utf-8"))
    # 7. 各种空白
    (TMP / "w1.txt").write_bytes(b"a b\tc\r\nd\x0be\x0cf")
    (TMP / "w2.txt").write_bytes(b"   \n\t\n")


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

    print("== 1. 只有一个数字时补不补空格 ==")
    show("big.txt 只打 -l（字节 5 位）", ["-l", "big.txt"])
    show("big.txt 打 -lw", ["-lw", "big.txt"])
    show("s.txt 打 -lw", ["-lw", "s.txt"])
    show("s.txt 只打 -l", ["-l", "s.txt"])
    show("s.txt 只打 -w", ["-w", "s.txt"])
    show("s.txt 只打 -c", ["-c", "s.txt"])
    show("s.txt 默认", ["s.txt"])
    print()

    print("== 2. total 行的隐藏字节数算不算进 W ==")
    # n1/n2 各 99 字节 1 行，total = 198 字节 2 行
    show("n1+n2 只打 -l", ["-l", "n1.txt", "n2.txt"])
    show("n1+n2 打 -lwc", ["-lwc", "n1.txt", "n2.txt"])
    show("n1+n2 打 -lw", ["-lw", "n1.txt", "n2.txt"])
    print()

    print("== 3. total 行的行数算不算进 W ==")
    # p1/p2 各 5 行，total 10 行；各 10 字节，total 20 字节
    show("p1+p2 只打 -l", ["-l", "p1.txt", "p2.txt"])
    show("p1+p2 打 -lw", ["-lw", "p1.txt", "p2.txt"])
    print()

    print("== 4. 隐藏的字符数算不算进 W ==")
    # ch.txt: 101 字符、202 字节、1 行、1 词
    show("ch.txt 只打 -l", ["-l", "ch.txt"])
    show("ch.txt 打 -lw", ["-lw", "ch.txt"])
    show("ch.txt 打 -lwc", ["-lwc", "ch.txt"])
    show("ch.txt 打 -lwcm", ["-lwcm", "ch.txt"])
    print()

    print("== 5. 标准输入的宽度下限 ==")
    show("stdin -lw", ["-lw"], b"a b\nc\n")
    show("stdin -lwcm", ["-lwcm"], b"a b\nc\n")
    show("stdin -lwcL", ["-lwcL"], b"a b\nc\n")
    show("stdin + s.txt -lwc", ["-lwc", "-", "s.txt"], b"q\n")
    show("stdin + n1.txt -lwc", ["-lwc", "-", "n1.txt"], b"q\n")
    show("stdin + big.txt -lwc", ["-lwc", "-", "big.txt"], b"q\n")
    show("stdin 单列 -l", ["-l"], b"a b\nc\n")
    show("stdin 单列 -c", ["-c"], b"a b\nc\n")
    print()

    print("== 6. -L 的算法 ==")
    show("l1.txt (abc中文) -L", ["-L", "l1.txt"])
    show("l1.txt -L C locale", ["-L", "l1.txt"], loc="C")
    show("l2.txt (中文测试/第二行) -L", ["-L", "l2.txt"])
    show("l2.txt -L C locale", ["-L", "l2.txt"], loc="C")
    show("l3.txt (CRLF) -L", ["-L", "l3.txt"])
    show("l3.txt -lc", ["-lc", "l3.txt"])
    show("l3.txt -lw", ["-lw", "l3.txt"])
    show("l4.txt (只有换行) -lwcL", ["-lwcL", "l4.txt"])
    show("l5.txt (空) -lwcL", ["-lwcL", "l5.txt"])
    show("l6.txt (ab/空/cd) -lwcL", ["-lwcL", "l6.txt"])
    print()

    print("== 7. 词与行的空白判定 ==")
    show("w1.txt -lw", ["-lw", "w1.txt"])
    show("w2.txt -lw", ["-lw", "w2.txt"])
    show("w1.txt -m C locale", ["-m", "w1.txt"], loc="C")
    show("w1.txt -m C.UTF-8", ["-m", "w1.txt"])
    print()

    print("== 8. 多文件 total 的最长行 ==")
    show("l1+l6 -L", ["-L", "l1.txt", "l6.txt"])
    show("l2+l1 -L", ["-L", "l2.txt", "l1.txt"])
    print()

    print("== 9. 多文件时 total 行是否存在（单文件时不存在） ==")
    show("单文件 s.txt", ["s.txt"])
    show("两文件 s.txt n1.txt", ["s.txt", "n1.txt"])


if __name__ == "__main__":
    main()
