"""探针二：tail 特有的几件事，跟随模式、编码判定取样、边界。

用法:
    python AI/脚本/_t600_probe_tail.py

要查的：
1. 编码判定取的是「将要输出的那一段」，不是文件开头——GBK 中文在末尾、
   开头是 ASCII 时，tail 仍能出中文
2. 跟随模式：-f 认描述符、-F 认文件名（轮转）、半行要等换行符
3. --pid：目标进程退出就结束
4. 边界：-n 行数超过文件行数、-c 字节数超过文件大小
5. -c 在文件与标准输入上的「+N 从第 N 个字节开始」是否一致
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

MAIN = os.path.join(ROOT, "main.py")
GNU_TAIL = r"E:\software\Git\Git\usr\bin\tail.exe"


def write(base: str, name: str, data: bytes) -> str:
    path = os.path.join(base, name)
    with open(path, "wb") as fh:
        fh.write(data)
    return path


def run(args, cwd, stdin=b""):
    proc = subprocess.run(
        [sys.executable, MAIN, "tail"] + args,
        cwd=cwd, input=stdin, capture_output=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_gnu(args, cwd, stdin=b""):
    proc = subprocess.run(
        [GNU_TAIL] + args, cwd=cwd, input=stdin, capture_output=True)
    return proc.returncode, proc.stdout, proc.stderr


def show(title, value):
    print("%s = %r" % (title, value))


def probe_encoding_tail():
    print("=== 1. 编码判定取的是输出段，不是文件开头 ===")
    base = tempfile.mkdtemp(prefix="tailenc")
    try:
        # 开头是纯 ASCII，中文只在最后一行
        write(base, "mix.txt", b"ascii line\nascii line 2\n"
              + "中文最后一行\n".encode("gb18030"))
        for n in (1, 2, 3):
            rc, out, err = run(["-n", str(n), "mix.txt"], base)
            print("  -n %d  本项目 rc=%d out=%r" % (n, rc, out.decode("utf-8", "replace")))
            rc, out, err = run_gnu(["-n", str(n), "mix.txt"], base)
            print("          GNU   rc=%d out=%r" % (rc, out.decode("utf-8", "replace")))
        # 同样内容用 head 取开头，head 判的是开头那段的编码
        rc, out, err = run(["-n", "1", "mix.txt"], base)
        print("  tail -n 1 的字节是 GBK，转出来是中文：%r" % out.decode("utf-8", "replace"))
    finally:
        shutil.rmtree(base, ignore_errors=True)


def probe_follow():
    print("=== 2. 跟随模式 ===")
    base = tempfile.mkdtemp(prefix="tailfollow")
    try:
        log = write(base, "log.txt", b"first\n")
        # -f：新行要立刻出来
        proc = subprocess.Popen(
            [sys.executable, MAIN, "tail", "-f", "-s", "0.2", "log.txt"],
            cwd=base, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        collected = bytearray()

        def reader():
            while True:
                chunk = proc.stdout.read(1)
                if not chunk:
                    break
                collected.extend(chunk)

        import threading
        th = threading.Thread(target=reader, daemon=True)
        th.start()
        time.sleep(1.0)
        with open(log, "ab") as fh:
            fh.write(b"second\n")
        deadline = time.time() + 10
        while time.time() < deadline and b"second\n" not in collected:
            time.sleep(0.1)
        print("  -f 输出 %r（first+second 都到了）" % bytes(collected))
        proc.terminate()
        proc.wait(timeout=10)

        # 半行要等换行符
        log2 = write(base, "log2.txt", b"first\n")
        proc = subprocess.Popen(
            [sys.executable, MAIN, "tail", "-f", "-s", "0.2", "log2.txt"],
            cwd=base, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        collected = bytearray()

        def reader2():
            while True:
                chunk = proc.stdout.read(1)
                if not chunk:
                    break
                collected.extend(chunk)

        th = threading.Thread(target=reader2, daemon=True)
        th.start()
        time.sleep(0.8)
        with open(log2, "ab") as fh:
            fh.write(b"half")
        time.sleep(1.5)
        print("  -f 写了一半时的输出 %r（半行被压住）" % bytes(collected))
        with open(log2, "ab") as fh:
            fh.write(b" done\n")
        deadline = time.time() + 10
        while time.time() < deadline and b"done\n" not in collected:
            time.sleep(0.1)
        print("  -f 补上换行后输出 %r" % bytes(collected))
        proc.terminate()
        proc.wait(timeout=10)

        # -F：轮转后跟到新文件
        log3 = write(base, "rotate.log", b"old1\nold2\n")
        proc = subprocess.Popen(
            [sys.executable, MAIN, "tail", "-F", "-s", "0.2", "rotate.log"],
            cwd=base, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        collected = bytearray()

        def reader3():
            while True:
                chunk = proc.stdout.read(1)
                if not chunk:
                    break
                collected.extend(chunk)

        th = threading.Thread(target=reader3, daemon=True)
        th.start()
        time.sleep(1.0)
        os.rename(log3, os.path.join(base, "rotate.log.1"))
        write(base, "rotate.log", b"new1\n")
        deadline = time.time() + 12
        while time.time() < deadline and b"new1\n" not in collected:
            time.sleep(0.1)
        print("  -F 轮转后输出 %r（跟到新文件）" % bytes(collected))
        proc.terminate()
        proc.wait(timeout=10)
    finally:
        shutil.rmtree(base, ignore_errors=True)


def probe_pid():
    print("=== 3. --pid ===")
    base = tempfile.mkdtemp(prefix="tailpid")
    try:
        write(base, "p.txt", b"x\n")
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3)"])
        proc = subprocess.Popen(
            [sys.executable, MAIN, "tail", "-f", "-s", "0.2", "--pid", str(child.pid), "p.txt"],
            cwd=base, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        start = time.time()
        # 关键：子进程退出后必须把句柄回收掉（wait 会关句柄）。
        # Windows 上只要还有任何句柄指着这个进程，OpenProcess 就能打开它，
        # tail 会以为进程还活着。
        child.wait(timeout=20)
        print("  子进程已退出并回收句柄，耗时 %.1fs" % (time.time() - start))
        try:
            proc.wait(timeout=15)
            print("  tail 在子进程退出后 %.1fs 结束跟随（总耗时）" % (time.time() - start))
        except subprocess.TimeoutExpired:
            print("  tail 15s 内没有结束（--pid 没生效？）")
            proc.terminate()
            proc.wait(timeout=10)
    finally:
        shutil.rmtree(base, ignore_errors=True)


def probe_edges():
    print("=== 4. 边界 ===")
    base = tempfile.mkdtemp(prefix="taileg")
    try:
        write(base, "a.txt", b"l1\nl2\nl3\nl4\nl5\n")
        write(base, "one.txt", b"only\n")
        for args in (["-n", "99", "a.txt"], ["-n", "99", "one.txt"],
                     ["-c", "9999", "a.txt"], ["-n", "+99", "one.txt"],
                     ["-c", "+99", "a.txt"], ["-c", "+1", "a.txt"],
                     ["-c", "+1", "nonl.txt"]):
            write(base, "nonl.txt", b"p1\np2\np3")
            rc, out, err = run(args, base)
            rcg, outg, errg = run_gnu(args, base)
            mark = "同" if out == outg else "差"
            print("  [%s] %-22s 本项目 rc=%d out=%r" % (mark, " ".join(args), rc, out))
            if mark == "差":
                print("        GNU rc=%d out=%r" % (rcg, outg))
    finally:
        shutil.rmtree(base, ignore_errors=True)


def probe_stdin_bytes():
    print("=== 5. 标准输入上的 +N 字节起点 ===")
    base = tempfile.mkdtemp(prefix="tailstdin")
    try:
        write(base, "a.txt", b"l1\nl2\nl3\nl4\nl5\n")
        for args, data in ((["-c", "+5"], b"l1\nl2\nl3\nl4\nl5\n"),
                           (["-c", "+1"], b"l1\nl2\nl3\nl4\nl5\n"),
                           (["-c", "+2"], b"l1\nl2\nl3\nl4\nl5\n"),
                           (["-n", "+2"], b"l1\nl2\nl3\nl4\nl5\n")):
            rc, out, err = run(args, base, data)
            rcg, outg, errg = run_gnu(args, base, data)
            mark = "同" if out == outg else "差"
            print("  [%s] %-12s 本项目 rc=%d out=%r" % (mark, " ".join(args), rc, out))
            if mark == "差":
                print("        GNU rc=%d out=%r" % (rcg, outg))
    finally:
        shutil.rmtree(base, ignore_errors=True)


def main():
    probe_encoding_tail()
    print()
    probe_follow()
    print()
    probe_pid()
    print()
    probe_edges()
    print()
    probe_stdin_bytes()
    return 0


if __name__ == "__main__":
    sys.exit(main())
