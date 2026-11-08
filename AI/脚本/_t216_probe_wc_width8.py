"""探针十六：判定 total 行是否参与列宽 W（决定性判据）。

已归纳的模型：
- 列序固定：行数 → 词数 → 字符数(-m) → 字节数(-c) → 最长行(-L)
- 不给任何选项时默认打印 行/词/字节；给了就只打印给的
- 整个输出只有一个数字时（一个操作数 + 一列）不补空格
- 其余情况所有列右对齐到统一宽度 W，列间一个空格，末列后一个空格接文件名
- W = max(各普通文件的字节数位数, total 的字节数位数)；
  标准输入与目录的大小事先未知，各贡献一个固定下限 7

本轮判据：
- 两个各 9999999 字节（7 位）的文件 → total 19999998（8 位）
  若 W = 8 → total 参与 W；若 W = 7 → 只有各文件参与
- 两个各 99999999 字节（8 位）的文件 → total 199999998（9 位）
- 单文件单列不补空格的规则在 9 位字节的文件上再确认一次
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc16"
TMP.mkdir(exist_ok=True)
(TMP / "adir").mkdir(exist_ok=True)


def setup() -> None:
    (TMP / "c7.txt").write_bytes(b"a" * 9999999)
    (TMP / "c8.txt").write_bytes(b"b" * 99999999)
    (TMP / "c9.txt").write_bytes(b"c" * 999999999)


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

    print("== 1. total 是否参与 W ==")
    show("c7 + c7 -lw（各 7 位，total 8 位）", ["-lw", "c7.txt", "c7.txt"])
    show("c7 + c7 -l", ["-l", "c7.txt", "c7.txt"])
    show("c8 + c8 -lw（各 8 位，total 9 位）", ["-lw", "c8.txt", "c8.txt"])
    show("c9 + c9 -lw", ["-lw", "c9.txt", "c9.txt"])
    print()

    print("== 2. 单文件单列不补空格 ==")
    show("c9 -l（9 位字节）", ["-l", "c9.txt"])
    show("c9 -lw", ["-lw", "c9.txt"])
    show("c9 -lwc", ["-lwc", "c9.txt"])
    print()

    print("== 3. 标准输入与目录的 7 ==")
    show("stdin + c9 -lw", ["-lw", "-", "c9.txt"], b"a\n")
    show("目录 + c9 -lw", ["-lw", "adir", "c9.txt"])
    show("stdin + 目录 -lw", ["-lw", "-", "adir"], b"a\n")


if __name__ == "__main__":
    main()
