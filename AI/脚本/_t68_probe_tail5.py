"""探针 _t68：GBK 中文与跟随模式的实机行为。

三件事：

1. GBK 文本文件经本实现输出成 UTF-8（GNU 是字节透传，会把 GBK 字节
   原样写出去）。这是本项目刻意的取舍，得确认输出确实是可读中文。
2. `-f` 跟随时新追加的内容确实会输出出来，且半行要等换行符。
3. `-F` 跟随时文件被改名（轮转）也能跟到新文件——这一步在 Windows 上
   要求打开着的文件能被改名，所以跟随时不能长期占着句柄。

上一版探针崩在改名那一步，留下了孤儿 tail 进程占着文件，
后面几次都被它绊住。这版用 try/finally 兜住所有子进程，
并且无论成败都把日志落盘。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
AI = HERE.parents[1]
ROOT = HERE.parents[2]
DATA = AI / "数据" / "tail_probe5"
DATA.mkdir(parents=True, exist_ok=True)
LOG = AI / "数据" / "tail_probe5_out.txt"

GNU_TAIL = shutil.which("tail")
_lines: list[str] = []


def print(*args):  # noqa: A001
    _lines.append(" ".join(str(a) for a in args))


def flush():
    LOG.write_text("\n".join(_lines) + "\n", encoding="utf-8")


def run_ours(args, stdin=b""):
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "tail", *args],
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(DATA),
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_gnu(args, stdin=b""):
    proc = subprocess.run(
        [GNU_TAIL, *args],
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(DATA),
    )
    return proc.returncode, proc.stdout, proc.stderr


def start_follow(args):
    """起一个跟随进程，返回 (proc, 收尾函数)。"""
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "main.py"), "tail", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(DATA),
    )

    def stop():
        proc.terminate()
        try:
            return proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            return proc.communicate()

    return proc, stop


# ---- GBK 中文 ----
(DATA / "gbk.txt").write_bytes("第一行中文\n第二行中文\n第三行中文\n".encode("gb18030"))
(DATA / "utf8.txt").write_bytes("第一行中文\n第二行中文\n第三行中文\n".encode("utf-8"))

print("=" * 70)
print("T. GBK 文本（GNU 字节透传，本实现解成 UTF-8）")
print("=" * 70)
code, out, err = run_ours(["-n", "2", "gbk.txt"])
print(f"本实现 exit={code} out={out!r}")
print(f"       解码后 = {out.decode('utf-8')!r}")
code, out, err = run_gnu(["-n", "2", "gbk.txt"])
print(f"GNU    exit={code} out={out!r}（GBK 原字节）")

code, out, err = run_ours(["-n", "2", "utf8.txt"])
print(f"UTF-8 语料 本实现 exit={code} out={out!r}")

code, out, err = run_ours(["gbk.txt"])
print(f"GBK 全文 本实现 exit={code} out={out!r}")
print(f"          解码后 = {out.decode('utf-8')!r}")

print()
print("=" * 70)
print("U. -f 跟随（命令行路径，2.5 秒后掐掉）")
print("=" * 70)
target = DATA / "follow.log"
target.write_bytes(b"line1\nline2\n")

proc, stop = start_follow(["-f", "-n", "2", "follow.log"])
try:
    time.sleep(1.2)
    with target.open("ab") as writer:
        writer.write(b"line3\n")
    time.sleep(1.2)
    with target.open("ab") as writer:
        writer.write(b"line4\n")
    time.sleep(1.2)
finally:
    out, err = stop()
print(f"exit={proc.returncode}")
print(f"out={out!r}")
print(f"err={err.decode('utf-8', 'replace')!r}")

print()
print("=" * 70)
print("V. -f 跟随时半行的处理")
print("=" * 70)
target2 = DATA / "follow2.log"
target2.write_bytes(b"start\n")

proc, stop = start_follow(["-f", "follow2.log"])
try:
    time.sleep(1.2)
    with target2.open("ab") as writer:
        writer.write(b"half-written")
    time.sleep(1.2)
    with target2.open("ab") as writer:
        writer.write(b" completed\n")
    time.sleep(1.2)
finally:
    out, err = stop()
print(f"exit={proc.returncode}")
print(f"out={out!r}")
print("（半行不该单独出现，要等换行符到了才整体输出）")

print()
print("=" * 70)
print("W. -F 跟随文件名（轮转后跟新文件）")
print("=" * 70)
target3 = DATA / "rotate.log"
stale = DATA / "rotate.log.1"
if stale.exists():
    stale.unlink()
target3.write_bytes(b"old1\nold2\n")

proc, stop = start_follow(["-F", "rotate.log"])
try:
    time.sleep(1.2)
    # 轮转：改名 + 建新文件
    try:
        target3.rename(DATA / "rotate.log.1")
        print("改名成功")
    except OSError as exc:
        print(f"改名失败: {exc}")
    (DATA / "rotate.log").write_bytes(b"new1\n")
    time.sleep(1.5)
    with (DATA / "rotate.log").open("ab") as writer:
        writer.write(b"new2\n")
    time.sleep(1.5)
finally:
    out, err = stop()
print(f"exit={proc.returncode}")
print(f"out={out!r}")
print("（轮转后应跟到新文件的新内容）")

flush()
print(f"日志已写入 {LOG}")
