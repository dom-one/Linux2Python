"""决定性验证: GNU 的列宽到底是「各列独立」还是「所有计数列共用一个宽度」。

t320 的数据指向一个反直觉的规则: GNU 的所有计数列**共用一个宽度**,
这个宽度 = 字节数之和的位数(事先数不出大小的来源占 7 列),
而列值比这个宽度长时直接写长, 不补齐也不截断。

关键反例 (t320):
  wc -lL tab.txt one.txt
    tab.txt 的 -L 值是 17(2 位), 字节和是 8(1 位)
    GNU 输出 '1 17 tab.txt\\n1 1 one.txt\\n2 17 total\\n'
    第二列的 '1' **没有**被补成 ' 1' ⇒ 第二列的宽度是 1, 不是它自己的 2
    ⇒ 宽度是「所有计数列共用」, 不是逐列算

这一轮用「L 值位数 > 字节和位数」的样本做决定性区分:
  b"\\t"*125 + b"\\n"  -> 126 字节(3 位), 显示宽度 1000(4 位)
若宽度 = 字节和位数(3), 则 '1000' 溢出成 4 字符且行/词列都是 3 宽;
若宽度 = 逐列最大, 则 L 列 4 宽、行/词列 3 宽 —— 两者对 '1000' 之外的列就能分开。

再复核「事先数不出大小的来源占 7 列」这条。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_width_decisive.txt")
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
    base = tempfile.mkdtemp(prefix="wc_dec_")
    lines: list[str] = []
    try:
        files = {
            # 126 字节(3 位), 显示宽度 1000(4 位)
            "t125.txt": b"\t" * 125 + b"\n",
            # 11 字节(2 位), 显示宽度 80(2 位)
            "t10.txt": b"\t" * 10 + b"\n",
            # 1000 字节(4 位), 1 行
            "big.txt": b"z" * 999 + b"\n",
            # 2 字节
            "one.txt": b"x\n",
        }
        for name, data in files.items():
            with open(os.path.join(base, name), "wb") as fh:
                fh.write(data)
        os.mkdir(os.path.join(base, "sub"))

        lines.append("### 决定性样本")
        lines.append("  t125.txt: 126 字节(3 位), 显示宽度 1000(4 位)")
        lines.append("  t10.txt : 11 字节(2 位), 显示宽度 80(2 位)")
        lines.append("  big.txt : 1000 字节(4 位)")
        lines.append("")

        cases = [
            ("L 值 4 位 > 字节和 3 位, 带 total", ["-lL", "t125.txt", "one.txt"]),
            ("L 值 4 位, 单独一列带 total", ["-L", "t125.txt", "one.txt"]),
            ("L 值 4 位, 单独一列无 total", ["-L", "t125.txt"]),
            ("三列, L 值 4 位", ["-lwcL", "t125.txt", "one.txt"]),
            ("L 值 2 位, 字节和 2 位", ["-lL", "t10.txt", "one.txt"]),
            ("字节和 4 位", ["-lL", "big.txt", "one.txt"]),
            ("字节和 4 位, 三列", ["-lwc", "big.txt", "one.txt"]),
        ]
        for title, argv in cases:
            g = gnu(base, argv)
            o = ours(base, argv)
            lines.append("=" * 70)
            lines.append("# %s" % title)
            lines.append("$ wc %s" % " ".join(argv))
            lines.append("  GNU : %r" % g)
            lines.append("  项目: %r" % o)
            lines.append("  %s" % ("一致" if g == o else "★不一致"))

        lines.append("=" * 70)
        lines.append("### 事先数不出大小的来源: 是不是占 7 列")
        for argv in (["-l", "sub"], ["-l", "sub", "one.txt"], ["-l", "-", "one.txt"]):
            lines.append("$ wc %s" % " ".join(argv))
            lines.append("  GNU : %r" % gnu(base, argv))

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
