"""探针二：GNU wc 列宽模型的判别实验。

已知观测（探针一）：
  -l f100.txt          -> W=1   （单操作数，只打印行数）
  -lc f100.txt         -> W=3   （单操作数，字节数 100）
  -l a60000 b60000     -> W=6   （两个操作数，合计 120000）
  -lwc (stdin)         -> W=7
  -L (stdin)           -> W=1

要判别的是：宽度到底来自「打印出来的计数」，还是来自「字节数」，以及
「有无 total 行」「有无 stdin」分别起什么作用。
"""

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "_data_wc26")
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


write("f9.txt", b"x" * 8 + b"\n")
write("g9.txt", b"y" * 8 + b"\n")
write("big1.txt", b"x" * 999999 + b"\n")
write("big2.txt", b"y" * 999999 + b"\n")
# 99 个汉字 = 297 字节，但只有 99 个字符
write("cjk99.txt", ("中" * 99).encode("utf-8"))
os.makedirs(os.path.join(DATA, "adir"), exist_ok=True)

cases = [
    (["-l", "f9.txt", "g9.txt"], None, "两个 9 字节文件，只看行数（合计 18）"),
    (["-lwc", "f9.txt", "g9.txt"], None, "两个 9 字节文件，行+词+字节"),
    (["-m", "cjk99.txt"], None, "99 个汉字（297 字节），只看字符数"),
    (["-mc", "cjk99.txt"], None, "99 个汉字，字符+字节"),
    (["-l", "big1.txt"], None, "单文件 1000000 字节，只看行数"),
    (["-l", "big1.txt", "big2.txt"], None, "两个 1000000 字节文件，只看行数"),
    (["-l"], b"abc\n", "纯 stdin，只看行数"),
    (["-m"], b"abc\n", "纯 stdin，只看字符数"),
    (["-w"], b"abc\n", "纯 stdin，只看词数"),
    (["-l", "adir"], None, "目录当操作数"),
    (["-lwc", "adir"], None, "目录当操作数，三列"),
    (["-lwc", "f9.txt", "adir"], None, "文件 + 目录"),
    (["-lw", "f9.txt", "g9.txt"], None, "两个文件，行+词"),
    (["-L", "f9.txt", "g9.txt"], None, "两个文件，最长行"),
    (["-lwc", "cjk99.txt"], None, "汉字文件，三列"),
]

for args, stdin, label in cases:
    out, err, code = run(args, stdin)
    print(f"--- {label}: wc {' '.join(args)}")
    print(f"    stdout={out!r}")
    if err:
        print(f"    stderr={err!r}")
    print(f"    rc={code}")
