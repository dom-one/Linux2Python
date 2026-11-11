"""补测 wc 的列宽模型与几个边界。

上一轮探针只覆盖了常规用法。这一轮专门验证三件事:
1. 列宽是**逐列**算的, 不是全局一个宽度
2. 标准输入/目录事先数不出大小, GNU 为它们预留 7 列
3. total 行的计数比预留宽度长时直接写长, 不截断
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_width_probe.txt")


def run(base: str, argv: list[str], stdin_text: str | None = None) -> tuple[int, str, str]:
    cmd = [sys.executable, os.path.join(ROOT, "main.py"), "wc"] + argv
    proc = subprocess.run(
        cmd, cwd=base, capture_output=True,
        input=(stdin_text.encode("utf-8") if stdin_text is not None else b""),
    )
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", errors="replace"),
        proc.stderr.decode("utf-8", errors="replace"),
    )


def main() -> None:
    base = tempfile.mkdtemp(prefix="wc_w_")
    lines: list[str] = []
    try:
        # 100 行的小文件: 行数 3 位, 字节数 2 位
        with open(os.path.join(base, "many.txt"), "wb") as fh:
            fh.write(b"ab\n" * 100)
        # 一个 9999999 字节的文件
        with open(os.path.join(base, "huge.txt"), "wb") as fh:
            fh.write(b"z" * 9999999)
        # 一个 100000 字节的文件
        with open(os.path.join(base, "big.txt"), "wb") as fh:
            fh.write(b"y" * 100000)
        os.mkdir(os.path.join(base, "sub"))

        cases: list[tuple[str, list[str], str | None]] = [
            ("逐列宽度: 行数3位 字节数2位", ["-lwc", "many.txt"], None),
            ("总字节数撑开: 100000 字节", ["-lwc", "big.txt"], None),
            ("单列不撑开: 100000 字节", ["-l", "big.txt"], None),
            ("total 比预留宽: 9999999 字节 + stdin", ["-lwc", "huge.txt", "-"], "x\n"),
            ("只有 stdin 时预留 7 列", ["-lwc", "-"], "a b\nc\n"),
            ("目录预留 7 列", ["-lwc", "sub"], None),
            ("目录 + 文件", ["-lwc", "sub", "many.txt"], None),
            ("单列且有 total 不对齐", ["-l", "many.txt", "many.txt"], None),
        ]
        for title, argv, stdin_text in cases:
            code, out, err = run(base, argv, stdin_text)
            lines.append("=" * 60)
            lines.append("# %s" % title)
            lines.append("$ python main.py wc %s" % " ".join(argv))
            if stdin_text is not None:
                lines.append("[stdin=%r]" % stdin_text)
            lines.append("[退出码] %d" % code)
            lines.append("[stdout] %r" % out)
            lines.append("[stderr] %r" % err)

        # wc --help 的真实输出
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "main.py"), "wc", "--help"],
            cwd=base, capture_output=True,
        )
        lines.append("=" * 60)
        lines.append("# wc --help")
        lines.append("[退出码] %d" % proc.returncode)
        lines.append("[stdout]")
        lines.append(proc.stdout.decode("utf-8", errors="replace"))

        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        print("写入 %s" % OUT)
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
