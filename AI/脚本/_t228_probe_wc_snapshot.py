"""探针四：GNU wc 全量行为快照（结果写文件，避免终端输出丢字符）。

一次性覆盖：
  - 列宽模型（各种操作数组合 × 各种列组合）
  - 行/词/字节/字符/最长行的计数语义
  - 缺文件、目录、重复 - 的行为与退出码
"""

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "_data_wc28")
OUT = os.path.join(HERE, "_t228_wc_snapshot.txt")
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


write("one.txt", b"x\n")
write("f9.txt", b"x" * 8 + b"\n")
write("g9.txt", b"y" * 8 + b"\n")
write("f100.txt", b"x" * 99 + b"\n")
write("f100000.txt", b"x" * 99999 + b"\n")
write("big1.txt", b"x" * 999999 + b"\n")
write("big2.txt", b"y" * 999999 + b"\n")
write("b5.txt", b"x" * 99998 + b"\n")
write("b6.txt", b"x" * 999998 + b"\n")
write("m7.txt", b"x" * 9999998 + b"\n")
write("cjk99.txt", ("中" * 99).encode("utf-8"))
write("words.txt", b"a b\tc\rd\x0be\x0cf\n")
write("noeol.txt", b"a\nb")
os.makedirs(os.path.join(DATA, "adir"), exist_ok=True)

cases = [
    # 列宽：单操作数
    (["-l", "f100.txt"], None),
    (["-lc", "f100.txt"], None),
    (["-c", "f100.txt"], None),
    (["-l", "f100000.txt"], None),
    (["-L", "f100.txt"], None),
    (["-m", "cjk99.txt"], None),
    (["-mc", "cjk99.txt"], None),
    (["-lwc", "cjk99.txt"], None),
    # 列宽：多操作数（带 total）
    (["-l", "f9.txt", "g9.txt"], None),
    (["-lw", "f9.txt", "g9.txt"], None),
    (["-lwc", "f9.txt", "g9.txt"], None),
    (["-L", "f9.txt", "g9.txt"], None),
    (["-L", "f9.txt"], None),
    (["-l", "big1.txt", "big2.txt"], None),
    (["-lwc", "b5.txt", "b6.txt"], None),
    (["-lwc", "one.txt"], None),
    (["-lwc", "one.txt", "one.txt"], None),
    # 列宽：stdin
    (["-lwc"], b"abc\n"),
    (["-l"], b"abc\n"),
    (["-c"], b"abc\n"),
    (["-m"], b"abc\n"),
    (["-w"], b"abc\n"),
    (["-L"], b"abc\n"),
    (["-lw", "-"], b"abc\n"),
    (["-lc", "-"], b"abc\n"),
    (["-lwc", "-"], b"abc\n"),
    (["-c", "-"], b"abc\n"),
    (["-m", "-"], b"abc\n"),
    (["-L", "-"], b"abc\n"),
    (["-l", "f9.txt", "-"], b"abc\n"),
    (["-lw", "f9.txt", "-"], b"abc\n"),
    (["-lwc", "f9.txt", "-"], b"abc\n"),
    (["-lwc", "m7.txt", "-"], b"abc\n"),
    (["-lw", "m7.txt", "-"], b"abc\n"),
    (["-lw", "-", "-"], b"abc\n"),
    # 错误路径
    (["-l", "nope.txt"], None),
    (["-lwc", "f9.txt", "nope.txt"], None),
    (["-l", "adir"], None),
    (["-c", "adir"], None),
    (["-lwc", "adir"], None),
    (["-lwc", "f9.txt", "adir"], None),
    # 计数语义
    (["-lw", "words.txt"], None),
    (["-l", "noeol.txt"], None),
    (["-lw", "noeol.txt"], None),
]

lines = []
for args, stdin in cases:
    out, err, code = run(args, stdin)
    label = "stdin" if stdin is not None else "files"
    lines.append(f"--- wc {' '.join(args)}   [{label}]")
    lines.append(f"    stdout={out!r}")
    if err:
        lines.append(f"    stderr={err!r}")
    lines.append(f"    rc={code}")

text = "\n".join(lines) + "\n"
with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
    handle.write(text)
print(f"written {OUT} ({len(text)} bytes)")
