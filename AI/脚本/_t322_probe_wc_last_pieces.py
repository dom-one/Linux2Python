"""最后两块拼图: locale 名字的识别行为, 以及列宽取「字节总和」还是「最大文件」。

拼图一: locale 名字
  t314/t317 出现一个怪现象:
    默认(LC_CTYPE="C.UTF-8")            -> 高位字节词数 1 (像 C 区域设置)
    env LC_ALL=C.UTF-8                   -> 高位字节词数 0 (像 UTF-8 区域设置)
  两者 LC_CTYPE 都是 "C.UTF-8", 结果却不同。
  要弄清是「LC_CTYPE=C.UTF-8 这个名字不被 C 库认」还是别的缘故,
  这一轮把四种写法都测一遍, 并让 wc 自己报出它认到的 locale。

拼图二: 列宽取哪个数
  已知 GNU 的所有计数列共用一个宽度 W。
  W = 位数(所有文件的字节总和) 还是 位数(最大那个文件的字节数)?
  造 9 个 99 字节的文件: 总和 891(3 位), 最大文件 99(2 位) —— 两者可分开。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_last_pieces.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"


def run_bash(script: str) -> str:
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    return (out + ("[err] " + err.strip() if err.strip() else "")).strip()


def main() -> None:
    base = tempfile.mkdtemp(prefix="wc_pieces_")
    lines: list[str] = []
    try:
        # 拼图二: 9 个 99 字节的文件
        for i in range(9):
            with open(os.path.join(base, "f%d.txt" % i), "wb") as fh:
                fh.write(b"z" * 98 + b"\n")

        lines.append("### 拼图二: W 取字节总和(891, 3 位)还是最大文件(99, 2 位)")
        lines.append("9 个文件, 每个 99 字节, 总和 891")
        lines.append("")
        for argv in (["-l"] + ["f%d.txt" % i for i in range(9)],
                     ["-lc"] + ["f%d.txt" % i for i in range(9)]):
            lines.append("$ wc %s" % " ".join(argv))
            lines.append("  GNU : %r" % run_bash("cd '%s' && wc %s" % (base, " ".join(argv))))
        lines.append("")

        # 拼图一: locale 名字的识别行为
        lines.append("### 拼图一: locale 名字的识别行为")
        lines.append("")
        lines.append("%-30s %-14s %-14s %-14s" % ("写法", "高位字节词数", "UTF8中文词数", "UTF8中文字符数"))
        variants = [
            ("默认(LC_CTYPE=C.UTF-8)", ""),
            ("env LC_ALL=C", "env LC_ALL=C "),
            ("env LC_ALL=C.UTF-8", "env LC_ALL=C.UTF-8 "),
            ("env LC_ALL=C.utf8", "env LC_ALL=C.utf8 "),
            ("env LC_CTYPE=C.UTF-8", "env LC_CTYPE=C.UTF-8 "),
            ("env LC_CTYPE=C.utf8", "env LC_CTYPE=C.utf8 "),
            ("env LANG=C.UTF-8", "env LANG=C.UTF-8 "),
            ("env LANG=C.utf8", "env LANG=C.utf8 "),
        ]
        for label, prefix in variants:
            w1 = run_bash("printf '\\xa1\\n' | %swc -w" % prefix)
            w2 = run_bash("printf '\\xe4\\xb8\\xad\\xe6\\x96\\x87\\n' | %swc -w" % prefix)
            m2 = run_bash("printf '\\xe4\\xb8\\xad\\xe6\\x96\\x87\\n' | %swc -m" % prefix)
            lines.append("%-30s %-14s %-14s %-14s" % (
                label,
                w1.split()[0] if w1.split() else "?",
                w2.split()[0] if w2.split() else "?",
                m2.split()[0] if m2.split() else "?"))

        lines.append("")
        lines.append("### wc 进程自己认到的 locale (locale 命令的输出)")
        for label, prefix in variants:
            loc = run_bash("%slocale 2>&1 | grep -E 'LC_CTYPE|LC_ALL|LANG' | tr '\\n' ' '"
                           % prefix)
            lines.append("  %-30s %s" % (label, loc))

        lines.append("")
        lines.append("### locale -a 里的真实名字")
        lines.append(run_bash("locale -a | grep -E '^(C|POSIX)' | head -6"))
        lines.append(run_bash("locale -a | grep -iE '^zh_CN' | head -6"))

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
