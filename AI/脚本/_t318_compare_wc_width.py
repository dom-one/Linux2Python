"""核对列宽模型: 项目 vs GNU, 逐个变体比。

前面的差分 (t302) 用 25 组用例比过, 25 组一致, 只在「纯二进制词数」一处不一致。
但那批用例里没有「-l 与 -L 同时开」这种组合, 而 GNU 在这种组合下的列宽
看起来与项目不一样(项目的两列宽度不同, GNU 像是把 -L 列撑得更宽)。

这一轮专门构造宽度模型的用例:
- 让各列的「自身最大计数位数」与「字节数之和的位数」互不相同
- 分别用单列、两列、多列、带 total、带 stdin 的组合
每组都比项目与 GNU 的原始输出(带空格, 所以用 repr 存盘, 不靠终端看)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_width_compare.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"


def run_project(base: str, argv: list[str], stdin_text: str | None = None) -> str:
    cmd = [sys.executable, os.path.join(ROOT, "main.py"), "wc"] + argv
    proc = subprocess.run(
        cmd, cwd=base, capture_output=True,
        input=(stdin_text.encode("utf-8") if stdin_text is not None else b""),
    )
    return proc.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")


def run_gnu(base: str, argv: list[str], stdin_text: str | None = None) -> str:
    quoted = " ".join(argv)
    if stdin_text is None:
        script = "cd '%s' && wc %s" % (base, quoted)
    else:
        script = "cd '%s' && printf '%%s' '%s' | wc %s" % (
            base, stdin_text.replace("'", "'\\''"), quoted)
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    return proc.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")


def main() -> None:
    base = tempfile.mkdtemp(prefix="wc_width_")
    lines: list[str] = []
    try:
        files = {
            "tab.txt": b"a\tb\tc\n",          # 6 字节, 显示宽度 17, 1 行
            "one.txt": b"x\n",               # 2 字节
            "big.txt": b"y" * 99 + b"\n",    # 100 字节
            "many.txt": b"ab\n" * 100,       # 300 字节, 100 行
            "tabs.txt": b"\t" * 5 + b"\n",   # 6 字节, 显示宽度 40
        }
        for name, data in files.items():
            with open(os.path.join(base, name), "wb") as fh:
                fh.write(data)
        os.mkdir(os.path.join(base, "sub"))

        cases: list[tuple[str, list[str], str | None]] = [
            ("单列 -L", ["-L", "tab.txt"], None),
            ("单列 -l", ["-l", "tab.txt"], None),
            ("两列 -lL", ["-lL", "tab.txt"], None),
            ("两列 -lc", ["-lc", "tab.txt"], None),
            ("两列 -lL 多文件", ["-lL", "tab.txt", "one.txt"], None),
            ("两列 -lL 目录", ["-lL", "sub"], None),
            ("两列 -lL 目录+文件", ["-lL", "sub", "tab.txt"], None),
            ("两列 -lL 带 stdin", ["-lL", "-"], "a b\nc\n"),
            ("两列 -lL stdin+文件", ["-lL", "-", "tab.txt"], "a b\nc\n"),
            ("三列 -lwc", ["-lwc", "one.txt", "big.txt"], None),
            ("三列 -lwc many", ["-lwc", "many.txt"], None),
            ("两列 -lL tabs", ["-lL", "tabs.txt"], None),
            ("两列 -lL many", ["-lL", "many.txt"], None),
        ]

        same = 0
        diff = 0
        for title, argv, stdin_text in cases:
            ours = run_project(base, argv, stdin_text)
            gnu = run_gnu(base, argv, stdin_text)
            ok = ours == gnu
            same += 1 if ok else 0
            diff += 0 if ok else 1
            lines.append("=" * 66)
            lines.append("# %s   [%s]" % (title, "一致" if ok else "★不一致"))
            lines.append("$ wc %s" % " ".join(argv))
            if stdin_text is not None:
                lines.append("[stdin=%r]" % stdin_text)
            lines.append("  项目: %r" % ours)
            lines.append("  GNU : %r" % gnu)

        lines.append("=" * 66)
        lines.append("汇总: 一致 %d, 不一致 %d" % (same, diff))

        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        print("写入 %s" % OUT)
        print("一致 %d, 不一致 %d" % (same, diff))
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
