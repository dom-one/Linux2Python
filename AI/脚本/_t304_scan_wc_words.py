"""逐字节扫描, 弄清词数判定在项目与 GNU 之间的分歧点。

上一轮发现: 文件含高位字节(0x80-0xFF)而没有可打印 ASCII 时,
本项目数 0 个词, GNU wc 数 1 个词。

这一轮对 0x00-0xFF 每个字节值单独造一个文件, 两边各数一次词,
找出分歧到底落在哪些字节上。同时把项目内部的编码判定过程打出来,
看项目为什么会数成 0。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_words_scan.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"

sys.path.insert(0, ROOT)
from w2l.commands import wc as wcmod  # noqa: E402


def run_ours(base: str, name: str) -> int:
    cmd = [sys.executable, os.path.join(ROOT, "main.py"), "wc", "-w", name]
    proc = subprocess.run(cmd, cwd=base, capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    return int(out.split()[0])


def run_gnu(base: str, name: str) -> int:
    script = "cd '%s' && wc -w %s" % (base, name)
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    return int(out.split()[0])


def main() -> None:
    base = tempfile.mkdtemp(prefix="wc_scan_")
    lines: list[str] = []
    try:
        lines.append("每个字节值单独成文件, 文件内容 = <该字节> + \\n")
        lines.append("%-8s %-10s %-10s %-10s %s" % ("字节", "本项目", "GNU", "分歧", "项目判定编码"))
        lines.append("-" * 70)

        diff_bytes = []
        for value in range(256):
            name = "b%03d.dat" % value
            with open(os.path.join(base, name), "wb") as fh:
                fh.write(bytes([value]) + b"\n")
            ours = run_ours(base, name)
            gnu = run_gnu(base, name)
            sample = bytes([value]) + b"\n"
            encoding = wcmod._pick_encoding(sample)
            try:
                decoded = sample.decode(encoding)
                shown = repr(decoded)
            except UnicodeDecodeError:
                shown = "(解码失败)"
            mark = "" if ours == gnu else "★"
            if ours != gnu:
                diff_bytes.append(value)
            lines.append("%-8s %-10d %-10d %-10s %s  %s" % (
                "0x%02x" % value, ours, gnu, mark, encoding, shown))

        lines.append("-" * 70)
        lines.append("分歧字节个数: %d" % len(diff_bytes))
        lines.append("分歧字节: %s" % ", ".join("0x%02x" % v for v in diff_bytes))

        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        print("写入 %s" % OUT)
        print("分歧字节: %s" % ", ".join("0x%02x" % v for v in diff_bytes))
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
