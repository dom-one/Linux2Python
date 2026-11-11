"""收尾核对: 写教程前把最后几件事验实。

一、-L 显示宽度的几条规则各造一个最小样本, 逐字节对照项目与 GNU:
   制表符展开到 8 的倍数、\\r 把列号清零、取行内出现过的最大列数、
   全角字符 2 列、组合字符 0 列。
二、把教程里要用到的多文件命令按**核对器的执行方式**跑一遍
   (bash + cd 到仓库根 + 2>&1 合并 + mktemp 临时目录),
   看预期输出能不能被核对器逐行对上。
三、列宽模型的分歧样本, 把 GNU 与项目的原始字节都留下(供正文表格用)。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_final_semantics.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"


def bash(script: str) -> tuple[int, bytes]:
    proc = subprocess.run([BASH, "-c", script], capture_output=True,
                          stdin=subprocess.DEVNULL)
    return proc.returncode, proc.stdout.replace(b"\r\n", b"\n")


def ours(script: str) -> tuple[int, bytes]:
    """按核对器的方式跑仓库里的 python main.py。"""
    proc = subprocess.run(
        [BASH, "-c", 'cd "%s" && { %s ; } 2>&1' % (ROOT, script)],
        capture_output=True, stdin=subprocess.DEVNULL,
    )
    return proc.returncode, proc.stdout.replace(b"\r\n", b"\n")


def main() -> None:
    lines: list[str] = []

    lines.append("### 一、-L 显示宽度规则的最小样本")
    samples = {
        "制表符 a\\tb\\tc": "a\\tb\\tc\\n",
        "回车清零 abc\\rdef": "abc\\rdef\\n",
        "行内最大列(后面更长但被\\r清掉)": "abcdef\\rxy\\n",
        "全角字(UTF-8)": "\\xe5\\x85\\xa8\\xe8\\xa7\\xaf\\xe5\\xad\\x97\\n",
        "组合字符 e\\u0301": "e\\xcc\\x81\\n",
        "制表符在行首": "\\t\\t\\n",
    }
    for label, body in samples.items():
        code, out = ours("printf '%s' | python main.py wc -L" % body)
        gcode, gout = bash("printf '%s' | wc -L" % body)
        lines.append("--- %s" % label)
        lines.append("  字节     : %r" % body.encode("latin-1"))
        lines.append("  项目 -L  : %r" % out.decode("latin-1"))
        lines.append("  GNU  -L  : %r" % gout.decode("latin-1"))

    lines.append("")
    lines.append("### 二、多文件命令按核对器方式跑(临时目录)")
    script = (
        "d=$(mktemp -d) && "
        "printf 'a\\tb\\tc\\n' > \"$d/wide.dat\" && "
        "printf 'x\\n' > \"$d/small.dat\" && "
        "python main.py wc -lL \"$d/wide.dat\" \"$d/small.dat\""
    )
    code, out = ours(script)
    lines.append("$ %s" % script)
    lines.append("  [退出码] %d" % code)
    lines.append("  [原始字节] %r" % out)
    lines.append("  [按行]")
    for line in out.decode("utf-8", errors="replace").splitlines():
        lines.append("    |%s|" % line)

    lines.append("")
    lines.append("### 三、列宽模型: GNU 与项目的分歧样本(原始字节)")
    base = tempfile.mkdtemp(prefix="wc_sem_")
    try:
        with open(os.path.join(base, "wide.dat"), "wb") as fh:
            fh.write(b"a\tb\tc\n")
        with open(os.path.join(base, "small.dat"), "wb") as fh:
            fh.write(b"x\n")
        with open(os.path.join(base, "tabs.dat"), "wb") as fh:
            fh.write(b"\t" * 125 + b"\n")
        for label, argv in [
            ("-lL wide.dat small.dat", "-lL wide.dat small.dat"),
            ("-L wide.dat small.dat", "-L wide.dat small.dat"),
            ("-lL tabs.dat small.dat", "-lL tabs.dat small.dat"),
            ("-lwc wide.dat small.dat", "-lwc wide.dat small.dat"),
        ]:
            gcode, gout = bash("cd '%s' && wc %s" % (base, argv))
            ocode, out = ours("cd '%s' && python main.py wc %s" % (base, argv))
            lines.append("--- %s" % label)
            lines.append("  GNU : %r" % gout.decode("latin-1"))
            lines.append("  项目: %r" % out.decode("latin-1"))
            lines.append("  %s" % ("一致" if gout == out else "★不一致"))
    finally:
        shutil.rmtree(base, ignore_errors=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("写入 %s" % OUT)


if __name__ == "__main__":
    main()
