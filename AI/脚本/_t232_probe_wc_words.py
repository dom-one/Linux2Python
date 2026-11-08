"""探针七：GNU wc 的词到底怎么算。

候选规则：
  A. 一段非空白片段，只有以可打印字符开头才算一个词
  B. 一段非空白片段，只要含可打印字符就算一个词

判别用例：
  x1 = b"\\x01abc\\n"   A -> 0 词，B -> 1 词
  x2 = b"abc\\x01\\n"   A -> 1 词，B -> 1 词
  x3 = b"abc\\x01def\\n" A -> 1 词，B -> 1 词
  x4 = b"\\xffabc\\n"    A -> 0 词，B -> 1 词
  x5 = b" \\x01abc\\n"   A -> 0 词，B -> 1 词
  x6 = b"\\x01\\x02abc\\n" A -> 0 词，B -> 1 词
"""

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "_data_wc32")
OUT = os.path.join(HERE, "_t233_wc_words.txt")
GNU = r"E:\software\Git\Git\usr\bin\wc.exe"

os.makedirs(DATA, exist_ok=True)

samples = {
    "x1.bin": b"\x01abc\n",
    "x2.bin": b"abc\x01\n",
    "x3.bin": b"abc\x01def\n",
    "x4.bin": b"\xffabc\n",
    "x5.bin": b" \x01abc\n",
    "x6.bin": b"\x01\x02abc\n",
    "x7.bin": b"abc\x01\x02\n",
    "x8.bin": b"a\x01b c\x02d\n",
}

lines = []
for name, data in samples.items():
    with open(os.path.join(DATA, name), "wb") as handle:
        handle.write(data)
    env = dict(os.environ)
    env["LC_ALL"] = "C.UTF-8"
    proc = subprocess.run(
        [GNU, "-w", name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=DATA,
    )
    lines.append(f"{name} {data!r} -> GNU 词数 {proc.stdout.decode('utf-8', 'replace').strip()!r}")

text = "\n".join(lines) + "\n"
with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
    handle.write(text)
print(f"written {OUT}")
