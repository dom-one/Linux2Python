"""最后一轮: 定死 GNU 的列宽规则, 并核实 README 里那两句关于 GNU 的说法。

要解决的:
1. GNU 的列宽到底是「每列按自己的最大值」还是「所有计数列共用一个宽度」。
   9 个 99 字节的文件那组, 第一行看着与后 8 行不一致(第一行 '1' 没补,
   后 8 行 '  1' 补了), 这不合常理, 要用 od -c 复核原始字节,
   并用 3 个文件、-l 单列等变体交叉验证。

2. README 与 wc.py 文档字符串的两句话要核实:
   (a)「GNU 在 C 区域设置下只把可打印的 ASCII 当可打印字符, 中文文件在 GNU 那边词数是 0」
   (b)「换到匹配的区域设置(zh_CN.UTF-8)跑 GNU, 数字与本实现一致」
   实测发现两句都需要改: C 区域设置下中文词数是 1 不是 0;
   zh_CN.UTF-8 跑 GBK 文件解不出来, 真正对得上的是 zh_CN(GBK 区域设置)。

这一轮把这几点一次测完, 之后就开始写教程。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_rule_final.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"


def run_bash(script: str) -> str:
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    return (out + ("[err] " + err.strip() if err.strip() else "")).strip()


def ours(base: str, argv: list[str]) -> str:
    cmd = [sys.executable, os.path.join(ROOT, "main.py"), "wc"] + argv
    proc = subprocess.run(cmd, cwd=base, capture_output=True)
    return proc.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")


def main() -> None:
    base = tempfile.mkdtemp(prefix="wc_rule_")
    lines: list[str] = []
    try:
        for i in range(9):
            with open(os.path.join(base, "f%d.txt" % i), "wb") as fh:
                fh.write(b"z" * 98 + b"\n")
        for i in range(3):
            with open(os.path.join(base, "g%d.txt" % i), "wb") as fh:
                fh.write(b"z" * 98 + b"\n")
        with open(os.path.join(base, "one.txt"), "wb") as fh:
            fh.write(b"x\n")

        lines.append("### 一、9 个 99 字节文件: 原始字节复核")
        names9 = " ".join("f%d.txt" % i for i in range(9))
        lines.append("od -c:")
        lines.append(run_bash("cd '%s' && wc -lc %s | od -c | head -12" % (base, names9)))
        lines.append("")
        lines.append("repr:")
        lines.append("  GNU : %r" % run_bash("cd '%s' && wc -lc %s" % (base, names9)))
        lines.append("  项目: %r" % ours(base, ["-lc"] + ["f%d.txt" % i for i in range(9)]))
        lines.append("")

        lines.append("### 二、3 个 99 字节文件")
        names3 = " ".join("g%d.txt" % i for i in range(3))
        lines.append("  GNU : %r" % run_bash("cd '%s' && wc -lc %s" % (base, names3)))
        lines.append("  项目: %r" % ours(base, ["-lc"] + ["g%d.txt" % i for i in range(3)]))
        lines.append("")

        lines.append("### 三、单列变体")
        for argv in (["-l"] + ["f%d.txt" % i for i in range(9)], ["-c"] + ["f%d.txt" % i for i in range(9)]):
            lines.append("$ wc %s" % " ".join(argv[:3]) + " ...")
            lines.append("  GNU : %r" % run_bash("cd '%s' && wc %s" % (base, " ".join(argv))))
            lines.append("  项目: %r" % ours(base, argv))
            lines.append("")

        lines.append("### 四、README 两句话的核实")
        gb = "中文内容\n".encode("gb18030")
        u8 = "中文内容\n".encode("utf-8")
        for label, data, locales in [
            ("GBK 中文", gb, ["LC_ALL=C", "LC_ALL=zh_CN", "LC_ALL=zh_CN.utf8"]),
            ("UTF-8 中文", u8, ["LC_ALL=C", "LC_ALL=C.utf8", "LC_ALL=zh_CN.utf8"]),
        ]:
            hexed = "".join("\\x%02x" % b for b in data)
            lines.append("--- %s" % label)
            lines.append("  项目          : 词=%d 字符=%d 字节=%d" % (
                wcmod_words(data), len(wcmod_text(data)), len(data)))
            for loc in locales:
                vals = []
                for opt in ("-w", "-m", "-c"):
                    out = run_bash("printf '%s' | env %s wc %s" % (hexed, loc, opt))
                    vals.append(int(out.split()[0]) if out.split() else -1)
                lines.append("  GNU %-18s: 词=%d 字符=%d 字节=%d" % (loc, *vals))
            lines.append("")

        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        print("写入 %s" % OUT)
        print()
        print("\n".join(lines))
    finally:
        shutil.rmtree(base, ignore_errors=True)


sys.path.insert(0, ROOT)
from w2l.commands import wc as wcmod  # noqa: E402


def wcmod_text(data: bytes) -> str:
    encoding = wcmod._pick_encoding(data)
    try:
        return data.decode(encoding)
    except UnicodeDecodeError:
        return wcmod._decode_bytes(data)


def wcmod_words(data: bytes) -> int:
    return wcmod._count_words(wcmod_text(data))


if __name__ == "__main__":
    main()
