"""确认 GNU 的列宽规则到底是什么。

t319 的数据显示 GNU 的列宽不像「每列按自己最大计数补」, 倒像是
「所有计数列共用一个宽度 = 字节数之和的位数」。

要证成这个假设, 需要构造「列宽来源」与「字节数位数」互相独立的样本:
- 列值位数 < 字节数位数 -> 若宽度取字节数位数, 列会被补宽
- 列值位数 > 字节数位数 -> 若宽度取字节数位数, 列值会原样写出(不截断)

另外还要复核两处上一轮发现的分歧:
1. 项目比 GNU 多补的那一列(项目给每列加了「自身最大计数位数」的下限)
2. 单列 + total 行时, 项目补齐而 GNU 不补

测完这一轮, 列宽模型就可以写进教程了。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_width_rule.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"


def gnu(base: str, argv: list[str]) -> str:
    script = "cd '%s' && wc %s" % (base, " ".join(argv))
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    return proc.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")


def ours(base: str, argv: list[str]) -> str:
    cmd = [sys.executable, os.path.join(ROOT, "main.py"), "wc"] + argv
    proc = subprocess.run(cmd, cwd=base, capture_output=True)
    return proc.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")


def main() -> None:
    base = tempfile.mkdtemp(prefix="wc_rule_")
    lines: list[str] = []
    try:
        files = {
            # 名字 -> (内容, 说明)
            "tab.txt": (b"a\tb\tc\n", "6 字节, 显示宽度 17, 1 行"),
            "one.txt": (b"x\n", "2 字节, 1 行"),
            "z300.txt": (b"z" * 299 + b"\n", "300 字节, 1 行"),
            "m100.txt": (b"ab\n" * 100, "300 字节, 100 行"),
            "big1000.txt": (b"z" * 999 + b"\n", "1000 字节, 1 行"),
            "tabs.txt": (b"\t" * 5 + b"\n", "6 字节, 显示宽度 40"),
        }
        for name, (data, desc) in files.items():
            with open(os.path.join(base, name), "wb") as fh:
                fh.write(data)
            lines.append("  %-14s %s" % (name, desc))
        lines.append("")

        cases = [
            # (说明, argv)
            ("列值位数 < 字节数位数(1 行 300 字节)", ["-l", "z300.txt"]),
            ("列值位数 < 字节数位数(单文件无 total 不补)", ["-l", "z300.txt"]),
            ("两文件 total, 字节和 302(3 位)", ["-l", "m100.txt", "one.txt"]),
            ("两文件 total, 字节和 1002(4 位)", ["-l", "big1000.txt", "one.txt"]),
            ("-L 17 列值 2 位, 字节和 8(1 位)", ["-lL", "tab.txt", "one.txt"]),
            ("-L 单列 + total, 字节和 8", ["-L", "tab.txt", "one.txt"]),
            ("-L 40 列值 2 位, 字节和 8", ["-lL", "tabs.txt", "one.txt"]),
            ("-lL 两文件, 字节和 302", ["-lL", "m100.txt", "one.txt"]),
            ("-lwc 两文件, 字节和 302", ["-lwc", "m100.txt", "one.txt"]),
        ]

        for title, argv in cases:
            g = gnu(base, argv)
            o = ours(base, argv)
            ok = g == o
            lines.append("=" * 66)
            lines.append("# %s" % title)
            lines.append("$ wc %s" % " ".join(argv))
            lines.append("  项目: %r" % o)
            lines.append("  GNU : %r" % g)
            lines.append("  %s" % ("一致" if ok else "★不一致"))

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
