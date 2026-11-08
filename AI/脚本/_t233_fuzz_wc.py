"""模糊对照：随机造一批纯 ASCII 文本文件，逐个与 GNU wc 比。

只造 ASCII 文本，这样编码判定没有歧义，比出来的差异就只能是列宽或计数
规则本身的问题。
"""

import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(HERE, "_data_wc33")
OUT = os.path.join(HERE, "_t234_wc_fuzz.txt")
GNU = r"E:\software\Git\Git\usr\bin\wc.exe"

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from w2l.commands.wc import build_parser, wc  # noqa: E402
from w2l.context import RunContext  # noqa: E402

import io  # noqa: E402

os.makedirs(DATA, exist_ok=True)

random.seed(20261108)

WORDS = ["alpha", "beta", "gamma", "x", "yy", "zzz", "a1", "b2"]


def make_text(rng):
    parts = []
    for _ in range(rng.randint(0, 12)):
        kind = rng.random()
        if kind < 0.35:
            parts.append(" ".join(rng.choice(WORDS) for _ in range(rng.randint(1, 5))))
        elif kind < 0.5:
            parts.append("\t".join(rng.choice(WORDS) for _ in range(rng.randint(1, 4))))
        elif kind < 0.6:
            parts.append("".join(rng.choice(WORDS) for _ in range(rng.randint(1, 6))))
        elif kind < 0.7:
            parts.append("")
        else:
            parts.append(" ".join(rng.choice(WORDS) for _ in range(rng.randint(1, 3))))
        if rng.random() < 0.85:
            parts.append("\n")
    return "".join(parts).encode("ascii")


def run_gnu(args, cwd):
    env = dict(os.environ)
    env["LC_ALL"] = "C.UTF-8"
    proc = subprocess.run(
        [GNU] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=cwd,
    )
    return proc.stdout.decode("utf-8", "replace")


def run_ours(args, cwd):
    namespace = build_parser().parse_args(list(args))
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(cwd=cwd, stdout=out, stderr=err, stdin=io.StringIO(""))
    wc(namespace, ctx)
    return out.getvalue()


names = []
for index in range(120):
    name = f"f{index:03d}.txt"
    with open(os.path.join(DATA, name), "wb") as handle:
        handle.write(make_text(random))
    names.append(name)

OPTIONS = [["-l"], ["-w"], ["-c"], ["-m"], ["-L"], ["-lwc"], ["-lwcL"], ["-lw"], ["-lm"], ["-cL"]]

lines = []
mismatches = 0
total = 0
for options in OPTIONS:
    for name in names:
        args = options + [name]
        gnu_out = run_gnu(args, DATA)
        our_out = run_ours(args, DATA)
        total += 1
        if gnu_out != our_out:
            mismatches += 1
            lines.append(f"--- 单文件不一致: wc {' '.join(args)}")
            lines.append(f"    GNU   ={gnu_out!r}")
            lines.append(f"    本实现={our_out!r}")
    for _ in range(40):
        first, second = random.sample(names, 2)
        args = options + [first, second]
        gnu_out = run_gnu(args, DATA)
        our_out = run_ours(args, DATA)
        total += 1
        if gnu_out != our_out:
            mismatches += 1
            lines.append(f"--- 双文件不一致: wc {' '.join(args)}")
            lines.append(f"    GNU   ={gnu_out!r}")
            lines.append(f"    本实现={our_out!r}")

lines.append(f"共 {total} 组，不一致 {mismatches} 组")
text = "\n".join(lines) + "\n"
with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
    handle.write(text)
print(f"written {OUT}: 共 {total} 组，不一致 {mismatches} 组")
