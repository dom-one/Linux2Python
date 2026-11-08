"""生成测试用例里要断言的期望输出（直接取 GNU wc 的实测值）。

测试要断言的字符串必须是 GNU 跑出来的，不能是我手算的。
"""

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "_data_wc34")
OUT = os.path.join(HERE, "_t235_wc_expect.txt")
GNU = r"E:\software\Git\Git\usr\bin\wc.exe"

os.makedirs(DATA, exist_ok=True)

FILES = {
    "one.txt": b"x\n",
    "two.txt": b"a b\nc\n",
    "empty.txt": b"",
    "noeol.txt": b"a\nb",
    "crlf.txt": b"c1\r\nc2\r\n",
    "cjk.txt": "中文\n".encode("utf-8"),
    "tab.txt": b"a\tb\tc\n",
    "big.txt": b"y" * 99 + b"\n",
    "bin.dat": b"\x00\x01\x02\xff\xfe\n",
}
for name, data in FILES.items():
    with open(os.path.join(DATA, name), "wb") as handle:
        handle.write(data)
os.makedirs(os.path.join(DATA, "sub"), exist_ok=True)

CASES = [
    ([], None),
    (["-l", "one.txt"], None),
    (["-w", "two.txt"], None),
    (["-c", "two.txt"], None),
    (["-m", "cjk.txt"], None),
    (["-L", "tab.txt"], None),
    (["-lwc", "one.txt", "two.txt"], None),
    (["-lwc", "one.txt", "big.txt"], None),
    (["-clw", "one.txt"], None),
    (["-lwc"], b"a b\nc\n"),
    (["-lwc", "-"], b"a b\nc\n"),
    (["-lw", "-", "-"], b"a b\nc\n"),
    (["-lwc", "one.txt", "nope.txt"], None),
    (["-lwc", "sub"], None),
    (["-l", "nope.txt"], None),
    (["-lwc", "empty.txt"], None),
    (["-lwc", "noeol.txt"], None),
    (["-lwc", "crlf.txt"], None),
    (["-L", "crlf.txt"], None),
    (["-lw", "bin.dat"], None),
]

lines = []
for args, stdin in CASES:
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
    label = "stdin" if stdin is not None else "files"
    lines.append(f"--- wc {' '.join(args)}  [{label}]")
    lines.append(f"    stdout={proc.stdout.decode('utf-8', 'replace')!r}")
    if proc.stderr:
        lines.append(f"    stderr={proc.stderr.decode('utf-8', 'replace')!r}")
    lines.append(f"    rc={proc.returncode}")

text = "\n".join(lines) + "\n"
with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
    handle.write(text)
print(f"written {OUT}")
