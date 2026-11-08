"""探针八：钉死最后几个判据。

已归纳的规则：
- 列序固定：行数 → 词数 → 字符数(-m) → 字节数(-c) → 最长行(-L)
- 不给选项时默认打印 行/词/字节；给了选项就只打印给的那些
- 只有「一个操作数 + 一列」时数字不补空格，否则补到统一宽度 W
- W = max(操作数个数>1 时所有文件与 total 的字节数位数)，标准输入出现时下限 7
- 目录：打印一行全 0 并报错，且不计入 total
- 缺文件：只报错，不打印那一行

这一轮确认：
1. `wc -l -`（单个操作数 '-' + 一列）到底补不补空格
2. 缺文件 + 正常文件时 total 的内容与 W
3. -L 的制表位（8 的倍数）与 \\r 的回车语义
4. -m 单列时按字符数（不按字节数）
5. 空文件与只含换行文件的 -L
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc8"
TMP.mkdir(exist_ok=True)
(TMP / "adir").mkdir(exist_ok=True)


def setup() -> None:
    (TMP / "one.txt").write_bytes(b"x\n")
    (TMP / "empty.txt").write_bytes(b"")
    (TMP / "nl.txt").write_bytes(b"\n")
    (TMP / "tabs.txt").write_bytes(b"a\tb\tc\n")
    (TMP / "tab1.txt").write_bytes(b"\tx\n")
    (TMP / "cr2.txt").write_bytes(b"ab\rcd\n")
    (TMP / "u8.txt").write_bytes("中文测试\n第二行\n".encode("utf-8"))
    (TMP / "big1.txt").write_bytes(b"y" * 99 + b"\n")


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

    print("== 1. 单操作数 + 单列 ==")
    show("'-' 单列 -l", ["-l", "-"], b"a b\nc\n")
    show("'-' 单列 -c", ["-c", "-"], b"a b\nc\n")
    show("'-' 两列 -lw", ["-lw", "-"], b"a b\nc\n")
    show("文件 单列 -l", ["-l", "one.txt"])
    show("文件 单列 -L", ["-L", "one.txt"])
    show("文件 单列 -m", ["-m", "u8.txt"])
    print()

    print("== 2. 缺文件与 total ==")
    show("缺文件 单列 -l", ["-l", "nope.txt"])
    show("缺文件 + 文件 -lwc", ["-lwc", "nope.txt", "one.txt"])
    show("文件 + 缺文件 -lwc", ["-lwc", "one.txt", "nope.txt"])
    show("缺 + 文件 + 缺 -lwc", ["-lwc", "nope.txt", "one.txt", "nope2.txt"])
    show("目录 + 文件 -lwc", ["-lwc", "adir", "one.txt"])
    show("目录 + 缺 -lwc", ["-lwc", "adir", "nope.txt"])
    print()

    print("== 3. -L 的制表位与回车 ==")
    show("tabs.txt (a\\tb\\tc) -L", ["-L", "tabs.txt"])
    show("tab1.txt (\\tx) -L", ["-L", "tab1.txt"])
    show("cr2.txt (ab\\rcd) -L", ["-L", "cr2.txt"])
    show("cr2.txt -lc", ["-lc", "cr2.txt"])
    print()

    print("== 4. 空与只含换行 ==")
    show("empty.txt -lwcL", ["-lwcL", "empty.txt"])
    show("nl.txt -lwcL", ["-lwcL", "nl.txt"])
    show("big1.txt -lwcL", ["-lwcL", "big1.txt"])
    print()

    print("== 5. -m 的口径 ==")
    show("u8.txt -m", ["-m", "u8.txt"])
    show("u8.txt -c", ["-c", "u8.txt"])
    show("u8.txt -mc", ["-mc", "u8.txt"])
    print()

    print("== 6. 选项顺序与重复 ==")
    show("-c -l", ["-c", "-l", "one.txt"])
    show("-l -c", ["-l", "-c", "one.txt"])
    show("--lines --words", ["--lines", "--words", "one.txt"])
    show("--max-line-length", ["--max-line-length", "big1.txt"])
    show("--bytes --chars --lines --words", ["--bytes", "--chars", "--lines", "--words", "u8.txt"])
    print()

    print("== 7. 选项粘写 ==")
    show("-lw", ["-lw", "one.txt"])
    show("-lwc", ["-lwc", "one.txt"])
    show("-cw", ["-cw", "one.txt"])
    print()

    print("== 8. 非法选项 ==")
    show("-x", ["-x", "one.txt"])
    show("--bogus", ["--bogus", "one.txt"])


if __name__ == "__main__":
    main()
