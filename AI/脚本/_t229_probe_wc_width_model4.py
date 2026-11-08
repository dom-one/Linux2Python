"""探针五：列宽模型的最后三个判别用例。

模型 H7：
  W = max(所有打印出来的计数的位数)
  若「打印的列数 >= 2」或「有 total 行」，再并入 width_basis：
      width_basis = 位数(普通文件字节数之和)，若存在事先不可知大小的来源
                    （stdin / 目录）则再取 max(该值, 7)

判别用例：
  D1  -lm cjk99.txt   99 字符 / 297 字节，单操作数两列
      预测：列数>=2 -> width_basis=3 -> ' 99 cjk99.txt'（W=3）
      若列数不触发 -> W=2 -> '99 cjk99.txt'
  D2  -l m7.txt f9.txt  9999999 + 9 = 10000008
      预测：sum -> 8 位 -> W=8；若取单文件最大 -> 7
  D3  -lm m7.txt       9999999 字节的 ASCII（字符数=字节数）
      预测：列数>=2 -> width_basis = 7 -> W=7
"""

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "_data_wc29")
OUT = os.path.join(HERE, "_t229_wc_width_out2.txt")
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


write("cjk99.txt", ("中" * 99).encode("utf-8"))
write("m7.txt", b"x" * 9999998 + b"\n")
write("f9.txt", b"y" * 8 + b"\n")
write("long.txt", b"x" * 19 + b"\n")
write("tiny.txt", b"z\n")
# GBK 文件：2 个汉字 = 4 字节
write("gbk.txt", "中文".encode("gb18030"))

cases = [
    (["-lm", "cjk99.txt"], None),
    (["-l", "m7.txt", "f9.txt"], None),
    (["-lm", "m7.txt"], None),
    (["-m", "m7.txt"], None),
    (["-L", "long.txt", "tiny.txt"], None),
    (["-m", "gbk.txt"], None),
    (["-c", "gbk.txt"], None),
    (["-lwc", "gbk.txt"], None),
]

lines = []
for args, stdin in cases:
    out, err, code = run(args, stdin)
    lines.append(f"--- wc {' '.join(args)}")
    lines.append(f"    stdout={out!r}")
    if err:
        lines.append(f"    stderr={err!r}")
    lines.append(f"    rc={code}")

text = "\n".join(lines) + "\n"
with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
    handle.write(text)
print(f"written {OUT}")
