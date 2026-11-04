"""探针 _t67：把本实现的 tail 与 GNU tail 做批量差分对照。

跑法：同一组参数分别喂给 GNU tail 和 `python main.py tail`，
逐字节比标准输出、比退出码。语料用 write_bytes 写，拿到的是真 LF 文件。

差异项只按「本项目的既定取舍」豁免，其余一律算不一致。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
AI = HERE.parents[1]
ROOT = HERE.parents[2]
DATA = AI / "数据" / "tail_diff"
DATA.mkdir(parents=True, exist_ok=True)
LOG = AI / "数据" / "tail_diff_out.txt"

GNU_TAIL = shutil.which("tail")
if GNU_TAIL is None:
    raise SystemExit("找不到 GNU tail")

_lines: list[str] = []


def print(*args):  # noqa: A001
    _lines.append(" ".join(str(a) for a in args))


# ---------------------------------------------------------------- 语料

(DATA / "a.txt").write_bytes(b"line1\nline2\nline3\nline4\nline5\n")
(DATA / "b.txt").write_bytes(b"B1\nB2\nB3\n")
(DATA / "noeol.txt").write_bytes(b"x\ny\nno-newline-tail")
(DATA / "empty.txt").write_bytes(b"")
(DATA / "crlf.txt").write_bytes(b"r1\r\nr2\r\nr3\r\n")
(DATA / "nul.txt").write_bytes(b"z1\x00z2\x00z3\x00")
(DATA / "mixed.txt").write_bytes(b"m1\nm2\nm3")
(DATA / "blank.txt").write_bytes(b"b1\n\nb3\n")
(DATA / "bin.dat").write_bytes(bytes(range(256)))
(DATA / "big.txt").write_bytes(b"".join(b"line%05d\n" % i for i in range(20000)))
(DATA / "bignoneol.txt").write_bytes(
    b"".join(b"M%06d\n" % i for i in range(19999)) + b"LASTLINE"
)
(DATA / "oneline.txt").write_bytes(b"Z" * 200000 + b"\n")
(DATA / "lines600.txt").write_bytes(b"".join(b"N%03d\n" % i for i in range(600)))
(DATA / "bytes1500.txt").write_bytes(b"".join(b"B%03d\n" % i for i in range(300)))

# ---------------------------------------------------------------- 差分


def run_gnu(args, stdin=b""):
    proc = subprocess.run(
        [GNU_TAIL, *args],
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(DATA),
    )
    return proc.returncode, proc.stdout


def run_ours(args, stdin=b""):
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "tail", *args],
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(DATA),
    )
    return proc.returncode, proc.stdout


CASES: list[list[str]] = []

# --- -n 行数 ---
for value in ["0", "1", "2", "3", "5", "99", "+0", "+1", "+2", "+3", "+99", "-0", "-1", "-2", "-99"]:
    CASES.append(["-n", value, "a.txt"])
    CASES.append(["-n", value, "noeol.txt"])

# --- -c 字节 ---
for value in ["0", "1", "2", "5", "19", "+0", "+1", "+2", "+3", "+19", "+20", "-0", "-1", "-5", "-19"]:
    CASES.append(["-c", value, "a.txt"])
    CASES.append(["-c", value, "noeol.txt"])

# --- 乘数后缀 ---
for value in ["1b", "1k", "1K", "1kB", "1KB", "1kiB", "1KiB", "1m", "1M", "1mB", "1MB", "1MiB", "1G"]:
    CASES.append(["-c", value, "bytes1500.txt"])
for value in ["1b", "1k", "1kB", "1KiB", "512", "1024"]:
    CASES.append(["-n", value, "lines600.txt"])

# --- -n 与 -c 同时给 ---
CASES.append(["-n", "2", "-c", "5", "a.txt"])
CASES.append(["-c", "5", "-n", "2", "a.txt"])
CASES.append(["-n", "2", "-c", "7", "a.txt"])
CASES.append(["-c", "7", "-n", "2", "a.txt"])
CASES.append(["-n", "2", "-n", "3", "a.txt"])
CASES.append(["-c", "5", "-c", "7", "a.txt"])

# --- 标题 ---
CASES.append(["a.txt", "b.txt"])
CASES.append(["-q", "a.txt", "b.txt"])
CASES.append(["-v", "a.txt", "b.txt"])
CASES.append(["-q", "-v", "a.txt", "b.txt"])
CASES.append(["-v", "-q", "a.txt", "b.txt"])
CASES.append(["a.txt"])
CASES.append(["-v", "a.txt"])
CASES.append(["a.txt", "b.txt", "mixed.txt"])
CASES.append(["a.txt", "empty.txt"])
CASES.append(["-v", "a.txt", "nosuch.txt"])
CASES.append(["a.txt", "nosuch.txt"])
CASES.append(["nosuch.txt"])
CASES.append(["."])
CASES.append([".", "a.txt"])

# --- -z ---
CASES.append(["-z", "nul.txt"])
CASES.append(["-z", "-n", "2", "nul.txt"])
CASES.append(["-z", "-c", "5", "nul.txt"])
CASES.append(["-z", "a.txt"])
CASES.append(["-z", "-n", "+2", "nul.txt"])

# --- 其他形态 ---
CASES.append(["-2", "a.txt"])
CASES.append(["--lines=2", "a.txt"])
CASES.append(["--bytes=5", "a.txt"])
CASES.append(["--lines=+2", "a.txt"])
CASES.append(["--", "a.txt"])
CASES.append(["crlf.txt"])
CASES.append(["-n", "2", "crlf.txt"])
CASES.append(["-c", "8", "crlf.txt"])
CASES.append(["blank.txt"])
CASES.append(["-n", "2", "blank.txt"])
CASES.append(["empty.txt"])
CASES.append(["-n", "5", "empty.txt"])
CASES.append(["-c", "5", "empty.txt"])
CASES.append(["bin.dat"])
CASES.append(["-c", "100", "bin.dat"])
CASES.append(["mixed.txt"])

# --- 大文件（回读半行） ---
CASES.append(["-n", "3", "big.txt"])
CASES.append(["-n", "10", "big.txt"])
CASES.append(["-n", "100", "big.txt"])
CASES.append(["-n", "1000", "big.txt"])
CASES.append(["-n", "3", "bignoneol.txt"])
CASES.append(["-n", "1", "bignoneol.txt"])
CASES.append(["-n", "2", "oneline.txt"])
CASES.append(["-n", "1", "oneline.txt"])
CASES.append(["-c", "10", "big.txt"])
CASES.append(["-c", "1", "big.txt"])
CASES.append(["-c", "100000", "big.txt"])
CASES.append(["-c", "300000", "big.txt"])
CASES.append(["-n", "+19998", "big.txt"])
CASES.append(["-n", "+20000", "big.txt"])
CASES.append(["-n", "+20001", "big.txt"])

# --- 标准输入 ---
STDIN_CASES: list[tuple[list[str], bytes]] = [
    ([], b"s1\ns2\n"),
    (["-"], b"s1\ns2\n"),
    (["-n", "1"], b"s1\ns2\n"),
    (["-n", "+2"], b"s1\ns2\ns3\n"),
    (["-c", "3"], b"s1\ns2\n"),
    (["-c", "+3"], b"s1\ns2\n"),
    (["-n", "0"], b"s1\ns2\n"),
    (["-n", "+0"], b"s1\ns2\n"),
    (["-v", "-"], b"s1\ns2\n"),
    (["-v", "a.txt", "-"], b"from-stdin\n"),
    (["-", "-"], b"s1\ns2\n"),
    ([], b""),
    (["-n", "2"], b"no-newline"),
]


def report(title, args, stdin, gnu, ours):
    gcode, gout = gnu
    ocode, oout = ours
    if gout == oout:
        # 标准输出逐字节一致就算过。
        # 退出码有一处已知的口径差异：GNU 打不开文件/读目录返回 1，
        # 本项目按「用法或运行错误返回 2」的约定返回 2（与 head 一致）。
        if gcode == ocode:
            return True
        if gcode == 1 and ocode == 2:
            return True
        print(f"!! 退出码不一致 {title}")
        print(f"   argv  = {args!r} stdin={stdin!r}")
        print(f"   GNU   exit={gcode}")
        print(f"   本实现 exit={ocode}")
        return False
    print(f"!! 标准输出不一致 {title}")
    print(f"   argv  = {args!r} stdin={stdin!r}")
    print(f"   GNU   exit={gcode} out={gout!r}")
    print(f"   本实现 exit={ocode} out={oout!r}")
    return False


# --- 选项写在操作数后面（GNU 的 getopt 会重排） ---
CASES.append(["a.txt", "-n", "2"])
CASES.append(["a.txt", "b.txt", "-q"])
CASES.append(["-n", "2", "a.txt", "b.txt"])

# --- 长选项形式 ---
CASES.append(["--lines", "2", "a.txt"])
CASES.append(["--bytes", "5", "a.txt"])
CASES.append(["--quiet", "a.txt", "b.txt"])
CASES.append(["--silent", "a.txt", "b.txt"])
CASES.append(["--verbose", "a.txt"])
CASES.append(["--zero-terminated", "nul.txt"])

# --- 只有一个行的文件 ---
(DATA / "one.txt").write_bytes(b"solo\n")
(DATA / "onenonl.txt").write_bytes(b"solo")
CASES.append(["one.txt"])
CASES.append(["-n", "1", "one.txt"])
CASES.append(["-n", "2", "one.txt"])
CASES.append(["-n", "+1", "one.txt"])
CASES.append(["-n", "+2", "one.txt"])
CASES.append(["-c", "3", "one.txt"])
CASES.append(["-c", "+5", "one.txt"])
CASES.append(["onenonl.txt"])
CASES.append(["-n", "1", "onenonl.txt"])
CASES.append(["-c", "4", "onenonl.txt"])
CASES.append(["-c", "+5", "onenonl.txt"])

# --- -z 与 -c 混用 ---
CASES.append(["-z", "-c", "3", "nul.txt"])
CASES.append(["-z", "-c", "+3", "nul.txt"])
CASES.append(["-z", "-n", "+3", "nul.txt"])

total = 0
bad = 0
for args in CASES:
    total += 1
    if not report("argv", args, b"", run_gnu(args), run_ours(args)):
        bad += 1

for args, stdin in STDIN_CASES:
    total += 1
    if not report("stdin", args, stdin, run_gnu(args, stdin), run_ours(args, stdin)):
        bad += 1

print()
print("=" * 70)
print(f"共 {total} 组，一致 {total - bad} 组，不一致 {bad} 组")
print("=" * 70)

LOG.write_text("\n".join(_lines) + "\n", encoding="utf-8")
print(f"日志已写入 {LOG}")
