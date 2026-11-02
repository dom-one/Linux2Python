"""探针：摸清 GNU head 8.32 在本机的确切行为。

只做只读探测与临时目录写入，不碰项目源码。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
DATA = AI_DIR / "数据"

GNU_HEAD = r"C:\Program Files\Git\usr\bin\head.exe"


def locate_head() -> str:
    """找到 GNU head 的绝对路径（避开 C:\\Windows\\System32 里的 WSL 启动器）。"""
    candidate = shutil.which("head")
    if candidate and "System32" not in candidate:
        return candidate
    return GNU_HEAD


def run(args: list[str], cwd: Path, stdin: bytes = b"") -> tuple[int, bytes, bytes]:
    proc = subprocess.run(
        [locate_head(), *args],
        cwd=str(cwd),
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.returncode, proc.stdout, proc.stderr


def show(title: str, args: list[str], cwd: Path, stdin: bytes = b"") -> None:
    code, out, err = run(args, cwd, stdin)
    print(f"--- {title}")
    print(f"    argv   : head {' '.join(args)}")
    print(f"    exit   : {code}")
    print(f"    stdout : {out!r}")
    print(f"    stderr : {err!r}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    DATA.mkdir(parents=True, exist_ok=True)

    root = Path(tempfile.mkdtemp(prefix="probe_head_"))
    try:
        (root / "a.txt").write_text("l1\nl2\nl3\nl4\nl5\n", encoding="utf-8")
        (root / "b.txt").write_text("x\n", encoding="utf-8")
        (root / "nonl.txt").write_text("p1\np2\np3", encoding="utf-8")  # 末行无换行
        (root / "empty.txt").write_text("", encoding="utf-8")
        (root / "zeros.bin").write_bytes(b"z1\x00z2\nz3\x00z4\n")
        (root / "crlf.txt").write_bytes(b"c1\r\nc2\r\nc3\r\n")
        (root / "sub").mkdir()
        (root / "sub" / "inner.txt").write_text("inner\n", encoding="utf-8")

        print("=" * 70)
        print("A. 基本行数")
        show("默认 10 行", ["a.txt"], root)
        show("-n 2", ["-n", "2", "a.txt"], root)
        show("-n 0", ["-n", "0", "a.txt"], root)
        show("-n 99（超过行数）", ["-n", "99", "a.txt"], root)
        show("-n2 紧凑写法", ["-n2", "a.txt"], root)
        show("-2 紧凑写法", ["-2", "a.txt"], root)
        show("--lines=3", ["--lines=3", "a.txt"], root)

        print("=" * 70)
        print("B. +N / -N 形式")
        show("-n +3", ["-n", "+3", "a.txt"], root)
        show("-n +1", ["-n", "+1", "a.txt"], root)
        show("-n +99", ["-n", "+99", "a.txt"], root)
        show("-n -2（除末两行）", ["-n", "-2", "a.txt"], root)
        show("-n -99", ["-n", "-99", "a.txt"], root)
        show("-n -0", ["-n", "-0", "a.txt"], root)
        show("-n +0", ["-n", "+0", "a.txt"], root)

        print("=" * 70)
        print("C. 字节模式")
        show("-c 5", ["-c", "5", "a.txt"], root)
        show("-c 0", ["-c", "0", "a.txt"], root)
        show("-c +5", ["-c", "+5", "a.txt"], root)
        show("-c -2", ["-c", "-2", "a.txt"], root)
        show("-c 5 与 -n 2 同开", ["-c", "5", "-n", "2", "a.txt"], root)
        show("-n 2 与 -c 5 同开（顺序相反）", ["-n", "2", "-c", "5", "a.txt"], root)

        print("=" * 70)
        print("D. 多文件与头部")
        show("两文件", ["a.txt", "b.txt"], root)
        show("两文件 -q", ["-q", "a.txt", "b.txt"], root)
        show("两文件 -v", ["-v", "a.txt", "b.txt"], root)
        show("单文件 -v", ["-v", "a.txt"], root)
        show("单文件 -q", ["-q", "a.txt"], root)
        show("三文件 -q", ["-q", "a.txt", "b.txt", "nonl.txt"], root)

        print("=" * 70)
        print("E. 错误路径")
        show("不存在的文件", ["missing.txt"], root)
        show("目录当文件", ["sub"], root)
        show("一个存在一个不存在", ["a.txt", "missing.txt"], root)
        show("不存在 + -v", ["-v", "missing.txt"], root)

        print("=" * 70)
        print("F. 标准输入")
        show("无操作数读 stdin", [], root, stdin=b"s1\ns2\ns3\n")
        show("'-' 读 stdin", ["-"], root, stdin=b"s1\ns2\ns3\n")
        show("- 与文件混排", ["-", "b.txt"], root, stdin=b"s1\ns2\n")

        print("=" * 70)
        print("G. -z 零分隔")
        show("-z 读 zeros.bin", ["-z", "zeros.bin"], root)
        show("-z -n 1", ["-z", "-n", "1", "zeros.bin"], root)
        show("不加 -z 读 zeros.bin", ["zeros.bin"], root)

        print("=" * 70)
        print("H. 边界文件")
        show("末行无换行", ["nonl.txt"], root)
        show("空文件", ["empty.txt"], root)
        show("CRLF 文件", ["crlf.txt"], root)
        show("空文件 -n 2", ["-n", "2", "empty.txt"], root)

        print("=" * 70)
        print("I. 用法错误")
        show("-n 非数字", ["-n", "abc", "a.txt"], root)
        show("-n 无值", ["-n"], root)
        show("未知选项", ["--bogus", "a.txt"], root)
        show("-c 多余值", ["-c", "1", "2", "a.txt"], root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
