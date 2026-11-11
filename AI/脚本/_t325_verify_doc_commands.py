"""核对教程里要写的每一条命令的真实输出。

核对器的规矩: bash 块去掉 cd 行后用 && 串起来跑, 跟在后面的无语言标记围栏块
是预期输出。所以文档里写的每条命令都要先在这里跑一遍, 把**逐字节**的结果存下来,
照着抄进文档, 不能凭印象写。

同时查一件事: cat.py 与 wc.py 的编码判定是不是各写一份。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_doc_commands.txt")

# 文档里要用的命令, 逐条实跑
COMMANDS = [
    "printf 'hello world\\n' | python main.py wc",
    "printf 'a b\\nc\\n' | python main.py wc",
    "printf 'a b\\nc\\n' | python main.py wc -l",
    "printf 'a b\\nc\\n' | python main.py wc -w",
    "printf 'a b\\nc\\n' | python main.py wc -c",
    "printf 'a b\\nc\\n' | python main.py wc -m",
    "printf 'a b\\nc\\n' | python main.py wc -lwc",
    "printf 'a b\\nc\\n' | python main.py wc -wlc",
    "printf 'a b\\nc\\n' | python main.py wc -lwc -m -L",
    "printf 'a\\tb\\tc\\n' | python main.py wc -L",
    "printf 'a\\tb\\tc\\n' | python main.py wc -lL",
    "printf 'x\\n' | python main.py wc -",
    "printf 'x\\n' | python main.py wc -lwc -",
    "printf 'x\\n' | python main.py wc -lw - -",
    "printf 'a\\nb' | python main.py wc -lwc",
    "printf 'c1\\r\\nc2\\r\\n' | python main.py wc -lwc",
    "printf '' | python main.py wc -lwc",
    "printf '\\001\\002\\003\\n' | python main.py wc -lw",
    "printf 'a\\001b\\n' | python main.py wc -lw",
    "python main.py wc -l nonexistent.txt",
    "python main.py wc -lwc w2l/commands/wc.py",
    "python main.py wc --help",
    "printf 'x\\n' | python main.py wc -L",
]


def run(command: str) -> tuple[int, bytes, bytes]:
    proc = subprocess.run(
        ["E:\\software\\Git\\Git\\bin\\bash.exe", "-c",
         'cd "%s" && { %s ; } 2>&1' % (ROOT, command)],
        capture_output=True, stdin=subprocess.DEVNULL,
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> None:
    lines: list[str] = []

    lines.append("### cat.py 与 wc.py 的编码判定是否重复实现")
    for name in ("cat.py", "wc.py"):
        path = os.path.join(ROOT, "w2l", "commands", name)
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        funcs = re.findall(r"^def (\w+)", text, re.M)
        picked = [f for f in funcs if "encod" in f or "text" in f or "score" in f
                  or "print" in f or "decode" in f]
        lines.append("  %s: %d 行, 编码相关函数 %s" % (name, text.count("\n") + 1, picked))
    lines.append("")

    lines.append("### 逐条命令的真实输出")
    for command in COMMANDS:
        code, out, err = run(command)
        lines.append("-" * 70)
        lines.append("$ %s" % command)
        lines.append("  [退出码] %d" % code)
        lines.append("  [stdout 原始字节] %r" % out)
        lines.append("  [stderr 原始字节] %r" % err)
        lines.append("  [按行显示]")
        for line in out.decode("utf-8", errors="replace").splitlines():
            lines.append("    |%s|" % line)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("写入 %s" % OUT)


if __name__ == "__main__":
    main()
