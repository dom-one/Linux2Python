"""探针三：验证 wc 列宽的最终模型。

模型 H5：
  W = max(
        所有打印出来的计数的位数（每行 + total 行）,
        有 total 行时 total 字节数的位数,
        当 -c 打印且某个操作数的字节数事先不可知（stdin / 目录）时取 7
      )

要验证的点：
  T1  -c 读 stdin            -> 期望 W=7（stdin 字节数不可知）
  T2  -lw 文件 + stdin       -> 期望 W=2（total 字节数 13，无 -c 不触发 7）
  T3  -lw 两个 9 字节文件    -> 期望 W=2（total 字节数 18）
  T4  -L 单文件              -> 期望 W=1（无 total 行，只看打印出来的计数）
  T5  -L 两个文件            -> 期望 W=2（total 行预留字节宽度）
  T6  -c 目录                -> 期望 W=7
  T7  -lwc 9999999 字节 + stdin -> 期望 W=7 或 8
  T8  -lw 9999999 + stdin    -> 期望 W=7（total 字节数 8 位）
"""

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "_data_wc27")
OUT = os.path.join(HERE, "_t227_wc_width_out.txt")
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
write("m7.txt", b"x" * 9999998 + b"\n")
os.makedirs(os.path.join(DATA, "adir"), exist_ok=True)

cases = [
    (["-c"], b"abc\n", "T1 只看字节数，读 stdin"),
    (["-lw", "f9.txt", "-"], b"abc\n", "T2 行+词，文件 + stdin（有 total）"),
    (["-lw", "f9.txt", "g9.txt"], None, "T3 行+词，两个 9 字节文件"),
    (["-L", "f9.txt"], None, "T4 最长行，单文件"),
    (["-L", "f9.txt", "g9.txt"], None, "T5 最长行，两个文件"),
    (["-c", "adir"], None, "T6 只看字节数，目录"),
    (["-lwc", "m7.txt", "-"], b"abc\n", "T7 9999999 字节文件 + stdin"),
    (["-lw", "m7.txt", "-"], b"abc\n", "T8 9999999 字节文件 + stdin，不看字节"),
    (["-lw", "-"], b"abc\n", "T9 只有 stdin，行+词"),
    (["-c", "-"], b"abc\n", "T10 只有 stdin，只看字节"),
    (["-lm", "-"], b"abc\n", "T11 只有 stdin，行+字符"),
    (["-lc", "-"], b"abc\n", "T12 只有 stdin，行+字节"),
]

lines = []
for args, stdin, label in cases:
    out, err, code = run(args, stdin)
    lines.append(f"--- {label}: wc {' '.join(args)}")
    lines.append(f"    stdout={out!r}")
    if err:
        lines.append(f"    stderr={err!r}")
    lines.append(f"    rc={code}")

text = "\n".join(lines) + "\n"
with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
    handle.write(text)
print(f"written {OUT}")
