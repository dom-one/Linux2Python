"""把 GNU 的列宽规则测死。

前面的 repr 里出现一个说不通的现象(9 个 99 字节的文件):
    GNU : '1  99 f0.txt\\n  1  99 f1.txt\\n...'
第一行的行数列宽 1, 后面几行的行数列宽 3 —— 同一个列宽度不该这样跳。
od -c 手工分栏又数出另一种结果, 说明我肉眼读 od 的输出不可靠。

这一轮不用肉眼读: 让 Python 直接拿字节, 逐行打印每行的 repr 和「每段的前导空格数」,
再把 GNU 与项目并排。样本覆盖:
- 2/3/9 个等长文件
- 不同长度文件混合
- 带 -L(列值位数与字节数位数不同)的组合
从结果里反推规则: 每列宽度到底是「自己的最大计数」还是「所有列共用」。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_width_rule_measured.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"


def gnu_bytes(base: str, argv: list[str]) -> bytes:
    script = "cd '%s' && wc %s" % (base, " ".join(argv))
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    return proc.stdout.replace(b"\r\n", b"\n")


def ours_bytes(base: str, argv: list[str]) -> bytes:
    cmd = [sys.executable, os.path.join(ROOT, "main.py"), "wc"] + argv
    proc = subprocess.run(cmd, cwd=base, capture_output=True)
    return proc.stdout.replace(b"\r\n", b"\n")


def describe(raw: bytes) -> list[str]:
    """把输出拆成每行, 标出各段的前导空格数。"""
    out = []
    for line in raw.split(b"\n"):
        if not line:
            continue
        # 按「空格分隔的段」拆, 记录每段原样
        parts = []
        i = 0
        while i < len(line):
            start = i
            while i < len(line) and line[i : i + 1] == b" ":
                i += 1
            gap = i - start
            j = i
            while j < len(line) and line[j : j + 1] != b" ":
                j += 1
            if j > i:
                parts.append("%r(前导空格%d)" % (line[i:j].decode("latin-1"), gap))
            i = j
        out.append("    " + " | ".join(parts))
    return out


def main() -> None:
    base = tempfile.mkdtemp(prefix="wc_meas_")
    lines: list[str] = []
    try:
        # 9 个 99 字节文件; 3 个 99 字节文件; 长度不一的两个文件
        for i in range(9):
            with open(os.path.join(base, "f%d.txt" % i), "wb") as fh:
                fh.write(b"z" * 98 + b"\n")
        for i in range(3):
            with open(os.path.join(base, "g%d.txt" % i), "wb") as fh:
                fh.write(b"z" * 98 + b"\n")
        with open(os.path.join(base, "small.txt"), "wb") as fh:
            fh.write(b"x\n")
        with open(os.path.join(base, "wide.txt"), "wb") as fh:
            fh.write(b"a\tb\tc\n")   # 6 字节, 显示宽度 17
        with open(os.path.join(base, "tabs.txt"), "wb") as fh:
            fh.write(b"\t" * 125 + b"\n")  # 126 字节, 显示宽度 1000

        cases = [
            ("9 个 99 字节, -lc", ["-lc"] + ["f%d.txt" % i for i in range(9)]),
            ("9 个 99 字节, -l", ["-l"] + ["f%d.txt" % i for i in range(9)]),
            ("9 个 99 字节, -c", ["-c"] + ["f%d.txt" % i for i in range(9)]),
            ("3 个 99 字节, -lc", ["-lc"] + ["g%d.txt" % i for i in range(3)]),
            ("2 个 99 字节, -lc", ["-lc", "g0.txt", "g1.txt"]),
            ("99 字节 + 2 字节, -lc", ["-lc", "g0.txt", "small.txt"]),
            ("6 字节(L=17) + 2 字节, -lL", ["-lL", "wide.txt", "small.txt"]),
            ("126 字节(L=1000) + 2 字节, -lL", ["-lL", "tabs.txt", "small.txt"]),
            ("126 字节(L=1000) 单列, -L", ["-L", "tabs.txt"]),
        ]

        for title, argv in cases:
            g = gnu_bytes(base, argv)
            o = ours_bytes(base, argv)
            lines.append("=" * 72)
            lines.append("# %s" % title)
            lines.append("$ wc %s" % " ".join(argv[:4]) + (" ..." if len(argv) > 4 else ""))
            lines.append("  GNU 原始: %r" % g.decode("latin-1"))
            lines.append("  GNU 分段:")
            lines.extend(describe(g))
            lines.append("  项目原始: %r" % o.decode("latin-1"))
            lines.append("  项目分段:")
            lines.extend(describe(o))
            lines.append("  %s" % ("一致" if g == o else "★不一致"))

        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        print("写入 %s" % OUT)
        print()
        print("\n".join(lines))
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
