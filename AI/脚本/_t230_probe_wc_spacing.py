"""探针六：把空格标成 ·，看清每一列到底占多宽。

关注：
  -lwc m7.txt -   字节列在文件行与 total 行是否同宽
  -lwc b5.txt b6.txt
  -lc f100.txt
  -l f9.txt g9.txt
"""

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "_data_wc30")
OUT = os.path.join(HERE, "_t230_wc_spacing.txt")
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
    return proc.stdout.decode("utf-8", "replace")


write("f100.txt", b"x" * 99 + b"\n")
write("f9.txt", b"x" * 8 + b"\n")
write("g9.txt", b"y" * 8 + b"\n")
write("b5.txt", b"x" * 99998 + b"\n")
write("b6.txt", b"x" * 999998 + b"\n")
write("m7.txt", b"x" * 9999998 + b"\n")

cases = [
    (["-lwc", "m7.txt", "-"], b"abc\n"),
    (["-lwc", "b5.txt", "b6.txt"], None),
    (["-lc", "f100.txt"], None),
    (["-l", "f9.txt", "g9.txt"], None),
    (["-lw", "f9.txt", "g9.txt"], None),
    (["-L", "f9.txt", "g9.txt"], None),
    (["-lwc", "f9.txt"], None),
    (["-lwc", "f9.txt", "g9.txt"], None),
    (["-c", "f9.txt", "g9.txt"], None),
]

lines = []
for args, stdin in cases:
    out = run(args, stdin)
    lines.append(f"--- wc {' '.join(args)}")
    for row in out.split("\n"):
        if row == "":
            continue
        lines.append("    " + row.replace(" ", "·"))
        # 逐列拆解：按单个空格切，统计每段长度
        parts = row.split(" ")
        lines.append(f"      段={parts}")
    lines.append("")

text = "\n".join(lines) + "\n"
with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
    handle.write(text)
print(f"written {OUT}")
