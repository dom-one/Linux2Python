"""探针 _t65：GNU tail 第三轮，钉死乘数后缀到底作用在什么量上。

第二轮留下的两个疑问：

1. `-n 1b` 在 20 行文件上输出全部 20 行。若后缀是「字节块」，
   `-n` 的语义（行数）就说不通；若后缀乘的是行数，1b = 512 行，
   20 行自然全给。拿 600 行文件一试便知。
2. `-c 1k` 与 `-c 1kB` 在 600 字节文件上都是全量，分不出 1024 与 1000。
   拿 1500 字节文件一试便知。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve()
AI = HERE.parents[1]
DATA = AI / "数据" / "tail_probe3"
DATA.mkdir(parents=True, exist_ok=True)
LOG = AI / "数据" / "tail_probe3_out.txt"

GNU_TAIL = shutil.which("tail")
if GNU_TAIL is None:
    raise SystemExit("找不到 GNU tail")

_lines: list[str] = []


def print(*args):  # noqa: A001
    _lines.append(" ".join(str(a) for a in args))


def run(args, stdin=b""):
    proc = subprocess.run(
        [GNU_TAIL, *args],
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(DATA),
    )
    return proc.returncode, proc.stdout, proc.stderr


def show(title, args):
    code, out, err = run(args)
    nl = out.count(b"\n")
    print(f"--- {title}")
    print(f"    argv = {args!r}")
    print(f"    exit = {code}  out_len = {len(out)}  out_lines = {nl}")
    print(f"    head = {out[:60]!r}  tail = {out[-40:]!r}")
    print(f"    err  = {err.decode('utf-8', 'replace')!r}")


# 600 行，每行 4 字节 + 换行 = 3000 字节
(DATA / "lines600.txt").write_bytes(b"".join(b"N%03d\n" % i for i in range(600)))
# 1500 字节：每行 5 字节 + 换行，300 行
(DATA / "bytes1500.txt").write_bytes(b"".join(b"B%03d\n" % i for i in range(300)))
# 精确 1000 字节：每行 10 字节 + 换行，100 行
(DATA / "exact1000.txt").write_bytes(b"".join(b"E%08d\n" % i for i in range(100)))
# 精确 1024 字节
(DATA / "exact1024.txt").write_bytes(b"".join(b"F%09d\n" % i for i in range(100)))

print("=" * 70)
print("M. -n 的后缀乘的是行数还是字节（600 行文件）")
print("=" * 70)
show("-n 3（基准 3 行）", ["-n", "3", "lines600.txt"])
show("-n 1b（若=512 行则给 512 行）", ["-n", "1b", "lines600.txt"])
show("-n 1k（若=1024 行则给全部 600 行）", ["-n", "1k", "lines600.txt"])
show("-n 1kB（若=1000 行则给全部 600 行）", ["-n", "1kB", "lines600.txt"])
show("-n 512（基准 512 行）", ["-n", "512", "lines600.txt"])
show("-n 600（全部）", ["-n", "600", "lines600.txt"])
show("-n 601（全部）", ["-n", "601", "lines600.txt"])

print()
print("=" * 70)
print("N. -c 的 k 与 kB（1500 字节文件）")
print("=" * 70)
show("-c 0（空）", ["-c", "0", "bytes1500.txt"])
show("-c 1k（若=1024 则给 1024 字节）", ["-c", "1k", "bytes1500.txt"])
show("-c 1kB（若=1000 则给 1000 字节）", ["-c", "1kB", "bytes1500.txt"])
show("-c 1K（=1024）", ["-c", "1K", "bytes1500.txt"])
show("-c 1KB（=1000）", ["-c", "1KB", "bytes1500.txt"])
show("-c 1KiB（=1024）", ["-c", "1KiB", "bytes1500.txt"])
show("-c 1kiB（=1024）", ["-c", "1kiB", "bytes1500.txt"])
show("-c 1b（=512）", ["-c", "1b", "bytes1500.txt"])
show("-c 1000（基准）", ["-c", "1000", "bytes1500.txt"])
show("-c 1024（基准）", ["-c", "1024", "bytes1500.txt"])

print()
print("=" * 70)
print("O. 精确边界：文件正好 1000 / 1024 字节")
print("=" * 70)
show("-c 1kB on exact1000（应给全部 1000）", ["-c", "1kB", "exact1000.txt"])
show("-c 1k on exact1000（应给全部 1000）", ["-c", "1k", "exact1000.txt"])
show("-c 1kB on exact1024（应给 1000）", ["-c", "1kB", "exact1024.txt"])
show("-c 1k on exact1024（应给 1024，全量）", ["-c", "1k", "exact1024.txt"])

print()
print("=" * 70)
print("P. +N 边界（文件 1500 字节）")
print("=" * 70)
show("-c +1500（正好最后 1 字节）", ["-c", "+1500", "bytes1500.txt"])
show("-c +1501（超过 1 字节）", ["-c", "+1501", "bytes1500.txt"])
show("-c +1499（最后 2 字节）", ["-c", "+1499", "bytes1500.txt"])
show("-n +600（正好最后 1 行）", ["-n", "+600", "lines600.txt"])
show("-n +601（超过 1 行）", ["-n", "+601", "lines600.txt"])
show("-n +599（最后 2 行）", ["-n", "+599", "lines600.txt"])

LOG.write_text("\n".join(_lines) + "\n", encoding="utf-8")
print(f"日志已写入 {LOG}")
