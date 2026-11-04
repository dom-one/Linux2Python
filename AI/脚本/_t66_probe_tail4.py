"""探针 _t66：GNU tail 回读时的半行处理。

tail 要取末尾几行，实现上通常从文件尾往前读一个块。块的起点多半落在
一行中间，这时开头那截「半行」是保留还是丢掉？GNU 的行为决定了实现
的取行逻辑，必须实测。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve()
AI = HERE.parents[1]
DATA = AI / "数据" / "tail_probe4"
DATA.mkdir(parents=True, exist_ok=True)
LOG = AI / "数据" / "tail_probe4_out.txt"

GNU_TAIL = shutil.which("tail")
if GNU_TAIL is None:
    raise SystemExit("找不到 GNU tail")

_lines: list[str] = []


def print(*args):  # noqa: A001
    _lines.append(" ".join(str(a) for a in args))


def run(args):
    proc = subprocess.run(
        [GNU_TAIL, *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(DATA),
    )
    return proc.returncode, proc.stdout, proc.stderr


def show(title, args):
    code, out, err = run(args)
    print(f"--- {title}")
    print(f"    argv = {args!r}")
    print(f"    exit = {code}  out_len = {len(out)}")
    print(f"    out  = {out!r}")
    print(f"    err  = {err.decode('utf-8', 'replace')!r}")


# 大文件：每行 10 字节，共 20000 行 = 200000 字节。
# 回读块边界落在行中间，才能看出半行是留还是丢。
(DATA / "big.txt").write_bytes(b"".join(b"line%05d\n" % i for i in range(20000)))
# 每行 7 字节，行边界更容易和 8192 之类的块长错开
(DATA / "big7.txt").write_bytes(b"".join(b"L%06d\n" % i for i in range(20000)))
# 末行无换行的大文件
(DATA / "bignoneol.txt").write_bytes(
    b"".join(b"M%06d\n" % i for i in range(19999)) + b"LASTLINE"
)
# 只有一个超长行的大文件
(DATA / "oneline.txt").write_bytes(b"Z" * 200000 + b"\n")

print("=" * 70)
print("Q. 回读时的半行（200000 字节，行长 10）")
print("=" * 70)
show("tail -n 3 big.txt", ["-n", "3", "big.txt"])
show("tail -n 10 big.txt", ["-n", "10", "big.txt"])
show("tail -n 100 big.txt", ["-n", "100", "big.txt"])
show("tail -n 1000 big.txt", ["-n", "1000", "big.txt"])
show("tail -n 3 big7.txt（行长 7）", ["-n", "3", "big7.txt"])
show("tail -n 500 big7.txt", ["-n", "500", "big7.txt"])
show("tail -n 3 bignoneol.txt（末行无换行）", ["-n", "3", "bignoneol.txt"])
show("tail -n 1 bignoneol.txt", ["-n", "1", "bignoneol.txt"])
show("tail -n 2 oneline.txt（单行超长）", ["-n", "2", "oneline.txt"])
show("tail -n 1 oneline.txt", ["-n", "1", "oneline.txt"])

print()
print("=" * 70)
print("R. -c 在大文件上取末尾字节")
print("=" * 70)
show("-c 10 big.txt", ["-c", "10", "big.txt"])
show("-c 1 big.txt", ["-c", "1", "big.txt"])
show("-c 100000 big.txt（正好一半）", ["-c", "100000", "big.txt"])
show("-c 200000 big.txt（全量）", ["-c", "200000", "big.txt"])
show("-c 300000 big.txt（超过）", ["-c", "300000", "big.txt"])

print()
print("=" * 70)
print("S. -n +N 在大文件上")
print("=" * 70)
show("-n +19998 big.txt", ["-n", "+19998", "big.txt"])
show("-n +20000 big.txt", ["-n", "+20000", "big.txt"])
show("-n +20001 big.txt", ["-n", "+20001", "big.txt"])

LOG.write_text("\n".join(_lines) + "\n", encoding="utf-8")
print(f"日志已写入 {LOG}")
