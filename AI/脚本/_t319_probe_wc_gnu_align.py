"""查清 GNU 的两列对齐规则, 以及目录到底打不打计数行。

t318 发现两处不一致:
1. `wc -lL tab.txt one.txt` 项目输出 '1  1 one.txt'(第二列补了空格),
   GNU 输出 '1 1 one.txt'(没补)。但同一批里 `wc -lL sub tab.txt` 两边又一致,
   两列都被撑到 7 列宽。
   ⇒ GNU 的补齐规则比「每列各按最大值补」更细, 要自己测出来。

2. 目录那组两边一致, 但要确认 GNU 真的也打了一行全 0(而不是两边都没打、
   恰好被当成一致)。

这一轮用受控的输入把 GNU 的对齐规则测出来:
- 改变第一列的位数, 看第二列动不动
- 改变第二列的位数, 看第一列动不动
- 单独一列 vs 两列 vs 三列
- 有没有 total 行
每组都 dump 原始字节(repr), 不靠终端显示。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_gnu_align.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"


def gnu(base: str, argv: list[str]) -> str:
    script = "cd '%s' && wc %s" % (base, " ".join(argv))
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    return proc.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")


def main() -> None:
    base = tempfile.mkdtemp(prefix="wc_align_")
    lines: list[str] = []
    try:
        # a1.txt: 1 行, 显示宽度 17   (b"a\tb\tc\n")
        # a2.txt: 1 行, 显示宽度 1    (b"x\n")
        # a3.txt: 100 行, 显示宽度 2   (b"ab\n"*100)
        # b1.txt: 1 行, 显示宽度 1000 (b"z"*999 + b"\n")
        files = {
            "a1.txt": b"a\tb\tc\n",
            "a2.txt": b"x\n",
            "a3.txt": b"ab\n" * 100,
            "b1.txt": b"z" * 999 + b"\n",
        }
        for name, data in files.items():
            with open(os.path.join(base, name), "wb") as fh:
                fh.write(data)
        os.mkdir(os.path.join(base, "sub"))

        lines.append("### 一、目录: GNU 到底打不打计数行")
        lines.append("stdout: %r" % gnu(base, ["-lL", "sub"]))
        proc = subprocess.run([BASH, "-c", "cd '%s' && wc -lL sub" % base],
                              capture_output=True)
        lines.append("stderr: %r" % proc.stderr.decode("utf-8", errors="replace"))
        lines.append("退出码: %d" % proc.returncode)
        lines.append("")

        lines.append("### 二、对齐规则: 受控组合")
        combos = [
            ["-lL", "a1.txt", "a2.txt"],        # 第一列 1 位, 第二列 2 位
            ["-lL", "a2.txt", "a1.txt"],        # 顺序反过来
            ["-lL", "a3.txt", "a1.txt"],        # 第一列 3 位, 第二列 2 位
            ["-lL", "a1.txt", "a3.txt"],        # 第一列 1 位, 第二列 2 位 + total
            ["-lL", "b1.txt", "a2.txt"],        # 第二列 4 位
            ["-lL", "a2.txt", "b1.txt"],
            ["-lc", "a1.txt", "a2.txt"],        # 两列都是小数字
            ["-lwc", "a3.txt", "a2.txt"],
            ["-L", "a1.txt", "a2.txt"],         # 单列 + total
            ["-l", "a3.txt", "a2.txt"],         # 单列 + total
        ]
        for argv in combos:
            lines.append("$ wc %s" % " ".join(argv))
            lines.append("   %r" % gnu(base, argv))

        lines.append("")
        lines.append("### 三、带 total 时第三行的对齐")
        for argv in (["-lL", "a3.txt", "a2.txt"], ["-lwc", "a3.txt", "a2.txt"]):
            lines.append("$ wc %s" % " ".join(argv))
            lines.append("   %r" % gnu(base, argv))

        lines.append("")
        lines.append("### 四、目录参与时(预留 7 列)的组合")
        for argv in (["-lL", "sub", "a1.txt"], ["-lL", "a1.txt", "sub"],
                     ["-lc", "sub", "a3.txt"]):
            lines.append("$ wc %s" % " ".join(argv))
            lines.append("   %r" % gnu(base, argv))

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
