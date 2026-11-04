"""探针 _t64：GNU tail 第二轮，钉死乘数后缀与边界行为。

第一轮发现：
- `-n N` 取末 N 行，`-n +N` 从第 N 行开始（与 head 相反）
- `-c N` 取末 N 字节，`-c +N` 从第 N 字节开始
- `-n` 与 `-c` 同时给，后写的生效
- `-n 1k` 不报错，但到底是「1024 行」还是「1 行」没分出来

这一轮用更长的语料把上面这些分清楚，另外把 -c 的后缀表逐个试一遍。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve()
AI = HERE.parents[1]
DATA = AI / "数据" / "tail_probe2"
DATA.mkdir(parents=True, exist_ok=True)
LOG = AI / "数据" / "tail_probe2_out.txt"

GNU_TAIL = shutil.which("tail")
if GNU_TAIL is None:
    raise SystemExit("找不到 GNU tail")

_lines: list[str] = []


def print(*args):  # noqa: A001
    _lines.append(" ".join(str(a) for a in args))


def run(args, stdin=b"", cwd=None, timeout=None):
    proc = subprocess.Popen(
        [GNU_TAIL, *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd or DATA),
    )
    try:
        out, err = proc.communicate(input=stdin, timeout=timeout)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        code = f"TIMEOUT(已杀，部分输出如下)"
    return code, out, err


def show(title, args, stdin=b"", cwd=None, timeout=None):
    code, out, err = run(args, stdin=stdin, cwd=cwd, timeout=timeout)
    print(f"--- {title}")
    print(f"    argv = {args!r}")
    print(f"    exit = {code}")
    print(f"    out  = {out!r}")
    print(f"    err  = {err.decode('utf-8', 'replace')!r}")


# 20 行语料，每行 4 字节 + 换行 = 100 字节
(DATA / "long.txt").write_bytes(b"".join(b"L%02d\n" % i for i in range(1, 21)))
# 正好 1000 字节：便于试 1000 进制后缀
(DATA / "k1000.txt").write_bytes(b"".join(b"K%03d\n" % i for i in range(100)))  # 100 * 5 = 500
(DATA / "kb1000.txt").write_bytes(b"".join(b"B%04d\n" % i for i in range(100)))  # 100 * 6 = 600
# 1024 字节
(DATA / "k1024.txt").write_bytes(b"".join(b"P%04d\n" % i for i in range(128)))  # 128 * 6 = 768
# 末行无换行
(DATA / "noeol.txt").write_bytes(b"x\ny\nno-newline-tail")

print("=" * 70)
print("I. -n 是否认乘数后缀（20 行语料）")
print("=" * 70)
show("-n 3（基准，3 行）", ["-n", "3", "long.txt"])
show("-n 1k", ["-n", "1k", "long.txt"])
show("-n 1K", ["-n", "1K", "long.txt"])
show("-n 1b", ["-n", "1b", "long.txt"])
show("-n 1kb", ["-n", "1kb", "long.txt"])
show("-n 1kB", ["-n", "1kB", "long.txt"])
show("-n 1KiB", ["-n", "1KiB", "long.txt"])
show("-n 2M", ["-n", "2M", "long.txt"])
show("-n 1Z", ["-n", "1Z", "long.txt"])
show("-n 99999999999999999999（溢出）", ["-n", "99999999999999999999", "long.txt"])
show("-n abc（非法）", ["-n", "abc", "long.txt"])
show("-n ''（非法）", ["-n", "", "long.txt"])
show("-n 1.5（非法）", ["-n", "1.5", "long.txt"])
show("-n -abc（非法）", ["-n", "-abc", "long.txt"])
show("-n -0", ["-n", "-0", "long.txt"])
show("-n -3", ["-n", "-3", "long.txt"])
show("-n +2 与 -n 2 对照", ["-n", "+2", "long.txt"])
show("-n -2 与 -n 2 对照", ["-n", "-2", "long.txt"])

print()
print("=" * 70)
print("J. -c 后缀表（用不同大小的文件反推字节数）")
print("=" * 70)
# kb1000.txt 600 字节；k1024.txt 768 字节
show("-c 1b on 600B（应给 512）", ["-c", "1b", "kb1000.txt"])
show("-c 1k on 600B（应给 600 全量）", ["-c", "1k", "kb1000.txt"])
show("-c 1K on 600B（应给 600 全量）", ["-c", "1K", "kb1000.txt"])
show("-c 1kB on 600B（应给 600 全量）", ["-c", "1kB", "kb1000.txt"])
show("-c 1KB on 600B（应给 600 全量）", ["-c", "1KB", "kb1000.txt"])
show("-c 1kiB on 600B", ["-c", "1kiB", "kb1000.txt"])
show("-c 1KiB on 600B", ["-c", "1KiB", "kb1000.txt"])
show("-c 1m on 600B", ["-c", "1m", "kb1000.txt"])
show("-c 1M on 600B", ["-c", "1M", "kb1000.txt"])
show("-c 1mB on 600B", ["-c", "1mB", "kb1000.txt"])
show("-c 1MB on 600B", ["-c", "1MB", "kb1000.txt"])
show("-c 1MiB on 600B", ["-c", "1MiB", "kb1000.txt"])
show("-c 1miB on 600B", ["-c", "1miB", "kb1000.txt"])
show("-c 1G on 600B", ["-c", "1G", "kb1000.txt"])
show("-c 1GB on 600B", ["-c", "1GB", "kb1000.txt"])
show("-c 1GiB on 600B", ["-c", "1GiB", "kb1000.txt"])
show("-c 1Z on 600B", ["-c", "1Z", "kb1000.txt"])
show("-c 1Y on 600B", ["-c", "1Y", "kb1000.txt"])
show("-c 1E on 600B", ["-c", "1E", "kb1000.txt"])
show("-c 1bB on 600B", ["-c", "1bB", "kb1000.txt"])
show("-c 1biB on 600B", ["-c", "1biB", "kb1000.txt"])
show("-c 1kb on 600B（非法？）", ["-c", "1kb", "kb1000.txt"])
show("-c 1Kb on 600B（非法？）", ["-c", "1Kb", "kb1000.txt"])

print()
print("=" * 70)
print("K. -c 与 -n 的 + 语义边界")
print("=" * 70)
show("-c +2 on noeol", ["-c", "+2", "noeol.txt"])
show("-c +3 on noeol", ["-c", "+3", "noeol.txt"])
show("-c +12 on noeol", ["-c", "+12", "noeol.txt"])
show("-c +14 on noeol", ["-c", "+14", "noeol.txt"])
show("-c +15 on noeol", ["-c", "+15", "noeol.txt"])
show("-c +16 on noeol（超过长度）", ["-c", "+16", "noeol.txt"])
show("-n +3 on noeol", ["-n", "+3", "noeol.txt"])
show("-c -0 on noeol", ["-c", "-0", "noeol.txt"])
show("-n -0 on noeol", ["-n", "-0", "noeol.txt"])
show("-c +0 on noeol", ["-c", "+0", "noeol.txt"])
show("-c 99999999999999999999（溢出）", ["-c", "99999999999999999999", "noeol.txt"])
show("-c +99999999999999999999（溢出）", ["-c", "+99999999999999999999", "noeol.txt"])

print()
print("=" * 70)
print("L. --follow 的初始行为（只截 1.2 秒的首屏输出）")
print("=" * 70)
T = 1.2
show("-f 存在文件", ["-f", "long.txt"], timeout=T)
show("-F 存在文件", ["-F", "long.txt"], timeout=T)
show("--follow=name", ["--follow=name", "long.txt"], timeout=T)
show("--follow=descriptor", ["--follow=descriptor", "long.txt"], timeout=T)
show("-f 不存在的文件", ["-f", "nosuch.txt"], timeout=T)
show("-f 目录", ["-f", "."], timeout=T)
show("-f 加 -n 3", ["-f", "-n", "3", "long.txt"], timeout=T)
show("-f 加 -q", ["-f", "-q", "long.txt"], timeout=T)
show("--follow 无参数值（当 descriptor）", ["--follow", "long.txt"], timeout=T)
show("-f 加 -v 多文件", ["-f", "-v", "long.txt", "noeol.txt"], timeout=T)

LOG.write_text("\n".join(_lines) + "\n", encoding="utf-8")
print(f"日志已写入 {LOG}")
