"""探针十一：钉死列宽模型里最后两处。

已归纳的模型：
- 列序固定：行数 → 词数 → 字符数(-m) → 字节数(-c) → 最长行(-L)
- 不给选项时默认 行/词/字节；给了就只打印给的
- 整个输出只有一个数字时（一个操作数 + 一列）不补空格
- 其余情况补到统一宽度 W，W = max(未知大小操作数带来的下限, 已知文件的字节数位数)
  - 标准输入的字节数不参与 W 的计算
  - 目录与标准输入都算「未知大小」，带来下限 7

待验证：
1. 目录/标准输入带来的下限是不是恰好 7（配 6 位数字的文件看是 6 还是 7）
2. 标准输入的字节数确实不参与 W（换个组合再验一次）
3. 已知文件的字节数参与 W，但 total 行是否也算
4. 单操作数 + 单列不补空格的规则，与下限 7 谁优先
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc11"
TMP.mkdir(exist_ok=True)
(TMP / "adir").mkdir(exist_ok=True)


def setup() -> None:
    # 6 位字节
    (TMP / "b6.txt").write_bytes(b"g" * 999999)
    # 5 位字节
    (TMP / "b5.txt").write_bytes(b"h" * 99999)
    # 7 位字节
    (TMP / "b7.txt").write_bytes(b"i" * 9999999)
    # 1 位
    (TMP / "b1.txt").write_bytes(b"j\n")
    # 两个各 50000 字节 → total 100000（6 位）
    (TMP / "c1.txt").write_bytes(b"k" * 49999 + b"\n")
    (TMP / "c2.txt").write_bytes(b"l" * 49999 + b"\n")


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

    print("== 1. 下限是不是恰好 7 ==")
    show("目录 + 6位文件 -lw", ["-lw", "adir", "b6.txt"])
    show("目录 + 5位文件 -lw", ["-lw", "adir", "b5.txt"])
    show("stdin + 6位文件 -lw", ["-lw", "-", "b6.txt"], b"a\n")
    show("stdin + 5位文件 -lw", ["-lw", "-", "b5.txt"], b"a\n")
    show("stdin + 7位文件 -lw", ["-lw", "-", "b7.txt"], b"a\n")
    show("stdin + 8位文件 -lw", ["-lw", "-", "b6.txt"], b"a\n")
    print()

    print("== 2. 标准输入的字节数不参与 W ==")
    show("stdin 6字节 + 6位文件 -lwc", ["-lwc", "-", "b6.txt"], b"a\n")
    show("stdin 6字节 + 5位文件 -lwc", ["-lwc", "-", "b5.txt"], b"a\n")
    show("stdin 6字节 单独 -lwc", ["-lwc"], b"a\n")
    print()

    print("== 3. total 行算不算进 W ==")
    show("c1+c2 -lw（各 50000，total 100000）", ["-lw", "c1.txt", "c2.txt"])
    show("b5+b6 -lw（99999+999999）", ["-lw", "b5.txt", "b6.txt"])
    show("b1+b1 -lw", ["-lw", "b1.txt", "b1.txt"])
    print()

    print("== 4. 单操作数单列优先于下限 ==")
    show("目录 -l", ["-l", "adir"])
    show("stdin -l", ["-l"], b"a\n")
    show("stdin -c", ["-c"], b"a\n")
    show("stdin -lw", ["-lw"], b"a\n")
    print()

    print("== 5. 宽度与隐藏列 ==")
    show("b6.txt -lw（6位字节，单文件多列）", ["-lw", "b6.txt"])
    show("b6.txt -lwcL", ["-lwcL", "b6.txt"])
    show("b5.txt -lwcL", ["-lwcL", "b5.txt"])
    print()

    print("== 6. 没有操作数时的名字列 ==")
    show("stdin 无名 -lwc", ["-lwc"], b"a b\nc\n")
    show("stdin '-' -lwc", ["-lwc", "-"], b"a b\nc\n")


if __name__ == "__main__":
    main()
