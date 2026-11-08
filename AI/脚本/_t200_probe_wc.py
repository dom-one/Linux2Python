"""探针：实测 GNU wc 的输出格式与边界行为。

对照工具：E:\\software\\Git\\Git\\usr\\bin\\wc.exe
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc"
TMP.mkdir(exist_ok=True)

ASCII = b"alpha beta\ngamma\ndelta epsilon zeta\n"
EMPTY = b""
NONL = b"no newline at end"
BLANKS = b"   \n\t\n"
LONGLINE = b"x" * 40 + b"\nshort\n"
GBK = "中文测试\n第二行\n".encode("gb18030")
UTF8_CJK = "中文测试\n第二行\n".encode("utf-8")

FILES = {
    "a.txt": ASCII,
    "b.txt": NONL,
    "empty.txt": EMPTY,
    "blanks.txt": BLANKS,
    "long.txt": LONGLINE,
    "gbk.txt": GBK,
    "utf8.txt": UTF8_CJK,
}


def setup() -> None:
    for name, data in FILES.items():
        (TMP / name).write_bytes(data)


def run(args, stdin_data=None):
    proc = subprocess.run(
        [WC] + args,
        cwd=str(TMP),
        input=stdin_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.returncode, proc.stdout, proc.stderr


def show(label, args, stdin_data=None):
    code, out, err = run(args, stdin_data)
    print(f"--- {label}: wc {' '.join(args)}")
    print(f"    rc={code}")
    print(f"    out={out!r}")
    if err:
        print(f"    err={err!r}")


def main() -> None:
    setup()
    print("== 版本 ==")
    out = subprocess.run([WC, "--version"], stdout=subprocess.PIPE).stdout
    print(out.decode(errors="replace").splitlines()[0])
    print()

    print("== 默认输出 ==")
    show("默认 单文件", ["a.txt"])
    show("默认 多文件", ["a.txt", "b.txt", "empty.txt"])
    show("默认 多文件带 total", ["a.txt", "b.txt", "empty.txt", "total"])
    print()

    print("== 单个选项 ==")
    show("-l", ["-l", "a.txt"])
    show("-w", ["-w", "a.txt"])
    show("-c", ["-c", "a.txt"])
    show("-m", ["-m", "a.txt"])
    show("-L", ["-L", "long.txt"])
    print()

    print("== 组合选项 ==")
    show("-lw", ["-lw", "a.txt"])
    show("-lwcm", ["-lwcm", "a.txt"])
    show("-c -m", ["-c", "-m", "a.txt"])
    show("-lwc -L", ["-lwc", "-L", "long.txt"])
    print()

    print("== 多文件列宽 ==")
    show("多文件 -l", ["-l", "a.txt", "b.txt"])
    show("多文件 -lwc", ["-lwc", "a.txt", "b.txt", "empty.txt"])
    show("多文件 -lwc total", ["-lwc", "a.txt", "b.txt", "empty.txt", "total"])
    print()

    print("== 标准输入 ==")
    show("stdin 无参", [], b"one two\nthree\n")
    show("stdin -l", ["-l"], b"one two\nthree\n")
    show("stdin -", ["-"], b"one two\nthree\n")
    show("stdin - 与文件混合", ["-l", "-", "a.txt"], b"x\n")
    show("stdin - 与文件混合 带 total", ["-l", "-", "a.txt", "total"], b"x\n")
    print()

    print("== 边界 ==")
    show("空文件", ["a.txt"], None)
    show("空文件 -lwc", ["-lwc", "empty.txt"])
    show("无换行结尾 -lwc", ["-lwc", "b.txt"])
    show("空白行 -lwc", ["-lwc", "blanks.txt"])
    show("最长行 -L", ["-L", "long.txt"])
    show("最长行 -Lc", ["-Lc", "long.txt"])
    print()

    print("== 编码 ==")
    show("gbk -c", ["-c", "gbk.txt"])
    show("gbk -m", ["-m", "gbk.txt"])
    show("utf8 -c", ["-c", "utf8.txt"])
    show("utf8 -m", ["-m", "utf8.txt"])
    show("gbk -w", ["-w", "gbk.txt"])
    print()

    print("== 错误路径 ==")
    show("不存在的文件", ["-l", "nope.txt"])
    show("目录", ["-l", "."])
    show("多文件其中一个不存在", ["-l", "a.txt", "nope.txt", "b.txt"])
    print()

    print("== 长选项 ==")
    show("--lines", ["--lines", "a.txt"])
    show("--bytes --chars", ["--bytes", "--chars", "a.txt"])
    show("--max-line-length", ["--max-line-length", "long.txt"])
    show("--total", ["--total=always", "a.txt", "b.txt"])
    show("--files0-from", ["--files0-from=-"], b"a.txt\x00b.txt\x00")
    show("--strip-trailing-cr", ["--strip-trailing-cr", "-l", "a.txt"])


if __name__ == "__main__":
    main()
