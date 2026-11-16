"""探针五：倒读时的块边界，以及与 head 的编码判定取样差异。

用法:
    python AI/脚本/_t605_probe_tail_block.py

查两件事：
1. _read_last_lines 从文件末尾按 64KB 块倒读，若块边界正好落在行首，
   会不会把那一整行丢掉（源码里 `if position > 0: lines = lines[1:]`）
2. head 与 tail 的编码判定取样是不是同一个位置
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from w2l.commands.tail import _READ_SIZE  # noqa: E402

MAIN = os.path.join(ROOT, "main.py")
GNU_TAIL = r"E:\software\Git\Git\usr\bin\tail.exe"
GNU_HEAD = r"E:\software\Git\Git\usr\bin\head.exe"


def run(args, cwd):
    proc = subprocess.run([sys.executable, MAIN] + args, cwd=cwd, capture_output=True)
    return proc.returncode, proc.stdout


def run_gnu(exe, args, cwd):
    proc = subprocess.run([exe] + args, cwd=cwd, capture_output=True)
    return proc.returncode, proc.stdout


def case(label, data, n):
    base = tempfile.mkdtemp(prefix="tailblk")
    path = os.path.join(base, "big.txt")
    with open(path, "wb") as fh:
        fh.write(data)
    rc, out = run(["tail", "-n", str(n), "big.txt"], base)
    rcg, outg = run_gnu(GNU_TAIL, ["-n", str(n), "big.txt"], base)
    mark = "同" if out == outg else "差"
    print("[%s] %s" % (mark, label))
    print("    本项目 %d 字节，GNU %d 字节" % (len(out), len(outg)))
    if out != outg:
        print("    本项目头 %r" % out[:60])
        print("    GNU   头 %r" % outg[:60])
        print("    本项目尾 %r" % out[-60:])
        print("    GNU   尾 %r" % outg[-60:])
    return out == outg


def main() -> int:
    print("_READ_SIZE = %d" % _READ_SIZE)
    print()
    print("=== 1. 块边界落在行首 ===")

    # 情形 A：块边界正好是行首。
    # 构造：前导行长 = _READ_SIZE - 4，使第二个块起点落在行首。
    lead = b"L" * (_READ_SIZE - 4) + b"\n"      # 长度 = _READ_SIZE - 3
    body = b"".join(b"line%05d\n" % i for i in range(2000))
    data = lead + body
    # 让 _READ_SIZE 边界落在 lead 之后第一行的行首
    ok_a = case("块边界落在行首（-n 5）", data, 5)

    # 情形 B：块边界落在行中间（对照）
    lead2 = b"L" * (_READ_SIZE - 2) + b"\n"     # 长度 = _READ_SIZE - 1
    ok_b = case("块边界落在行中间（-n 5）", lead2 + body, 5)

    # 情形 C：块边界正好在某个行首，取的行数跨过边界
    lead3 = b"M" * (_READ_SIZE - 6) + b"\n"     # 长度 = _READ_SIZE - 5
    ok_c = case("块边界与行首错开 5 字节（-n 5）", lead3 + body, 5)

    print()
    print("=== 2. head 与 tail 的编码判定取样位置 ===")
    base = tempfile.mkdtemp(prefix="tailenc2")
    with open(os.path.join(base, "mix.txt"), "wb") as fh:
        fh.write(b"ascii head\n" + "中文在后面\n".encode("gb18030"))
    rc, out = run(["tail", "-n", "1", "mix.txt"], base)
    rc2, out2 = run(["head", "-n", "1", "mix.txt"], base)
    print("  tail -n 1 -> %r" % out.decode("utf-8", "replace"))
    print("  head -n 1 -> %r" % out2.decode("utf-8", "replace"))
    rc3, out3 = run_gnu(GNU_HEAD, ["-n", "1", "mix.txt"], base)
    print("  GNU head -n 1 -> %r" % out3.decode("utf-8", "replace"))

    print()
    print("情形 A/B/C 与 GNU 一致：%r %r %r" % (ok_a, ok_b, ok_c))
    return 0


if __name__ == "__main__":
    sys.exit(main())
