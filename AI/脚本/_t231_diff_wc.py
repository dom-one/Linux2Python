"""差分对照：把本实现和 GNU wc 的输出逐字节比。

语料与选项组合跑一遍，只比较标准输出（错误信息与退出码按项目约定不同，
不参与比较）。
"""

import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(HERE, "_data_wc31")
OUT = os.path.join(HERE, "_t232_wc_diff.txt")
GNU = r"E:\software\Git\Git\usr\bin\wc.exe"

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from w2l.commands.wc import build_parser, wc  # noqa: E402
from w2l.context import RunContext  # noqa: E402

os.makedirs(DATA, exist_ok=True)


def write(name, data):
    with open(os.path.join(DATA, name), "wb") as handle:
        handle.write(data)


write("one.txt", b"x\n")
write("empty.txt", b"")
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
write("cjk1.txt", "中文测试\n".encode("utf-8"))
write("gbk.txt", "中文测试\n".encode("gb18030"))
write("words.txt", b"a b\tc\rd\x0be\x0cf\n")
write("noeol.txt", b"a\nb")
write("crlf.txt", b"a\r\nb\r\n")
write("cr.txt", b"a\rb\n")
write("ctrl.txt", b"a\x01b\n")
write("tab.txt", b"a\tb\tc\n")
write("bin.dat", b"\x00\x01\x02\xff\xfe\n")
write("mix.txt", "abc中文\n".encode("utf-8") + b"\xff\xfe tail\n")
os.makedirs(os.path.join(DATA, "adir"), exist_ok=True)

OPTIONS = [
    [],
    ["-l"],
    ["-w"],
    ["-m"],
    ["-c"],
    ["-L"],
    ["-lwc"],
    ["-lw"],
    ["-lm"],
    ["-lc"],
    ["-lL"],
    ["-wl"],
    ["-mL"],
    ["-cL"],
    ["-lwcL"],
    ["-lwcLm"],
    ["-clw"],
]

OPERANDS = [
    ["one.txt"],
    ["empty.txt"],
    ["f9.txt", "g9.txt"],
    ["-"],
    ["one.txt", "-"],
    ["f9.txt", "-"],
    ["-", "-"],
    ["b5.txt", "b6.txt"],
    ["f9.txt", "nope.txt"],
    ["adir"],
    ["f9.txt", "adir"],
    ["one.txt", "one.txt"],
    ["big1.txt", "big2.txt"],
    ["m7.txt", "-"],
    ["cjk99.txt"],
    ["cjk1.txt"],
    ["gbk.txt"],
    ["words.txt"],
    ["noeol.txt"],
    ["crlf.txt"],
    ["cr.txt"],
    ["ctrl.txt"],
    ["tab.txt"],
    ["bin.dat"],
    ["mix.txt"],
    ["empty.txt", "one.txt"],
    ["f100.txt", "f100000.txt"],
    ["one.txt", "f9.txt", "g9.txt"],
]

STDIN_DATA = b"abc def\nx\n"


def run_gnu(args, stdin_data):
    env = dict(os.environ)
    env["LC_ALL"] = "C.UTF-8"
    proc = subprocess.run(
        [GNU] + args,
        input=stdin_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=DATA,
    )
    return proc.stdout.decode("utf-8", "replace")


def run_ours(args, stdin_text):
    namespace = build_parser().parse_args(list(args))
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(
        cwd=os.path.join(DATA),
        stdout=out,
        stderr=err,
        stdin=io.StringIO(stdin_text),
    )
    wc(namespace, ctx)
    return out.getvalue()


lines = []
mismatches = 0
total = 0
for options in OPTIONS:
    for operands in OPERANDS:
        args = options + operands
        gnu_out = run_gnu(args, STDIN_DATA)
        our_out = run_ours(args, STDIN_DATA.decode("utf-8"))
        total += 1
        if gnu_out != our_out:
            mismatches += 1
            lines.append(f"--- 不一致: wc {' '.join(args)}")
            lines.append(f"    GNU   ={gnu_out!r}")
            lines.append(f"    本实现={our_out!r}")

lines.append(f"共 {total} 组，不一致 {mismatches} 组")
text = "\n".join(lines) + "\n"
with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
    handle.write(text)
print(f"written {OUT}: 共 {total} 组，不一致 {mismatches} 组")
