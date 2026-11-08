"""探针：GNU wc 的列宽到底由什么决定。

候选模型：
  A. W = 位数(所有普通文件字节数之和)
  B. W = 位数(打印出来的最大计数)
  C. W = 位数(单个文件大小的最大值)
  D. 含 stdin 时下限 7

要判别的是：只打印 -l 一列时，宽度是按字节数算还是按这一列的计数算。
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "_data_wc25")
GNU = r"E:\software\Git\Git\usr\bin\wc.exe"

os.makedirs(DATA, exist_ok=True)


def write(name, data):
    path = os.path.join(DATA, name)
    with open(path, "wb") as handle:
        handle.write(data)
    return path


def run(args, stdin=None):
    env = dict(os.environ)
    env["LC_ALL"] = "C.UTF-8"
    proc = subprocess.run(
        [GNU] + args,
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=DATA,
    )
    return proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace"), proc.returncode


# 100 字节、1 行
write("f100.txt", b"x" * 99 + b"\n")
# 9 字节、1 行
write("f9.txt", b"x" * 8 + b"\n")
# 100000 字节、1 行
write("f100000.txt", b"x" * 99999 + b"\n")
# 两个 60000 字节的文件
write("a60000.txt", b"x" * 59999 + b"\n")
write("b60000.txt", b"x" * 59999 + b"\n")
# 一个 99999 字节 + 一个 999999 字节（前面测过的组合）
write("b5.txt", b"x" * 99998 + b"\n")
write("b6.txt", b"x" * 999998 + b"\n")

cases = [
    (["-l", "f100.txt"], None, "单文件 100 字节，只看行数"),
    (["-lc", "f100.txt"], None, "单文件 100 字节，行+字节"),
    (["-c", "f100.txt"], None, "单文件 100 字节，只看字节"),
    (["-l", "f9.txt"], None, "单文件 9 字节，只看行数"),
    (["-l", "f100000.txt"], None, "单文件 100000 字节，只看行数"),
    (["-l", "a60000.txt", "b60000.txt"], None, "两个 60000 字节文件（和 120000）"),
    (["-lwc", "b5.txt", "b6.txt"], None, "99999 + 999999"),
    (["-lwc"], b"abc\n", "纯 stdin"),
    (["-lwc", "-"], b"abc\n", "stdin 显式操作数"),
    (["-lwc", "f9.txt", "-"], b"abc\n", "小文件 + stdin"),
    (["-lwc", "f100000.txt", "-"], b"abc\n", "100000 字节文件 + stdin"),
    (["-lwc", "a60000.txt", "b60000.txt", "-"], b"abc\n", "两个 60000 + stdin"),
    (["-L"], b"abc\n", "stdin 的 -L"),
    (["-l", "nope.txt"], None, "缺文件"),
    (["-lwc", "f9.txt", "nope.txt"], None, "小文件 + 缺文件"),
]

for args, stdin, label in cases:
    out, err, code = run(args, stdin)
    print(f"--- {label}: wc {' '.join(args)}")
    print(f"    stdout={out!r}")
    if err:
        print(f"    stderr={err!r}")
    print(f"    rc={code}")
