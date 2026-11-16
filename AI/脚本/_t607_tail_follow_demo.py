"""跟随模式演示，供 teach/23 的第 18 步使用。

用法:
    python AI/脚本/_t607_tail_follow_demo.py

演示三件事:
1. `tail -f` 追加一行后立刻输出（_flush 刷缓冲的效果）
2. 追加半行时不输出，等换行符到了才整行出现
3. `tail -F` 能跟到轮转后的新文件

输出格式固定，方便写进教程里当预期输出。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN = os.path.join(ROOT, "main.py")


def _collect(proc):
    """后台线程把子进程 stdout 读进 bytearray。"""
    buf = bytearray()

    def reader():
        while True:
            chunk = proc.stdout.read(1)
            if not chunk:
                break
            buf.extend(chunk)

    th = threading.Thread(target=reader, daemon=True)
    th.start()
    return buf


def _wait_for(buf, needle, timeout=15.0):
    deadline = time.time() + timeout
    while time.time() < deadline and needle not in buf:
        time.sleep(0.05)
    return needle in buf


def demo_follow(base):
    log = os.path.join(base, "log.txt")
    with open(log, "wb") as fh:
        fh.write(b"first\n")
    proc = subprocess.Popen(
        [sys.executable, MAIN, "tail", "-f", "-s", "0.2", "log.txt"],
        cwd=base, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    buf = _collect(proc)
    try:
        time.sleep(1.0)
        print("[跟随] 追加 second 之前输出：%r" % bytes(buf))
        with open(log, "ab") as fh:
            fh.write(b"second\n")
        _wait_for(buf, b"second\n")
        print("[跟随] 追加 second 之后输出：%r" % bytes(buf))

        # 半行：写了一半不输出
        with open(log, "ab") as fh:
            fh.write(b"half")
        time.sleep(1.5)
        print("[跟随] 追加半行 half 之后输出：%r" % bytes(buf))

        # 补上换行，整行才出来
        with open(log, "ab") as fh:
            fh.write(b" done\n")
        _wait_for(buf, b"half done\n")
        print("[跟随] 补上换行之后输出：%r" % bytes(buf))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def demo_rotate(base):
    log = os.path.join(base, "rotate.log")
    with open(log, "wb") as fh:
        fh.write(b"old1\nold2\n")
    proc = subprocess.Popen(
        [sys.executable, MAIN, "tail", "-F", "-s", "0.2", "rotate.log"],
        cwd=base, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    buf = _collect(proc)
    try:
        time.sleep(1.0)
        print("[轮转] 旧文件内容：%r" % bytes(buf))
        os.rename(log, os.path.join(base, "rotate.log.1"))
        with open(log, "wb") as fh:
            fh.write(b"new1\n")
        _wait_for(buf, b"new1\n", timeout=20.0)
        print("[轮转] 轮转后跟到新文件：%r" % bytes(buf))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> int:
    base = tempfile.mkdtemp(prefix="tailfollow")
    try:
        demo_follow(base)
        demo_rotate(base)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
