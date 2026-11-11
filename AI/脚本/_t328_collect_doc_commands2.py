"""收集教程第 3 步要用到的最后一批命令的真实输出。

按核对器的执行方式跑: bash + cd 到仓库根 + 2>&1 合并, 逐字节取回。
文档里写什么, 这里就照着什么写, 不凭印象。
"""

from __future__ import annotations

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_doc_commands2.txt")

COMMANDS = [
    "python main.py",
    "python main.py wc w2l/errors.py w2l/context.py",
    "python main.py wc -lwc w2l/errors.py w2l/context.py",
    "python main.py wc -L README.md",
    "python main.py wc -m README.md",
    "python main.py wc README.md",
    "python main.py wc -lwc README.md AGENTS.md",
    "python main.py wc -l nonexistent.txt",
    "python main.py wc -lwc w2l nonexistent.txt",
    "printf 'a b\\nc\\n' | python main.py wc -lwc",
    "printf 'a b\\nc\\n' | python main.py wc -wlc",
    "printf 'x\\n' | python main.py wc -lw - -",
    "printf 'a\\tb\\tc\\n' | python main.py wc -L",
    "printf 'a\\tb\\tc\\n' | python main.py wc -lL",
    "printf 'abc\\rdef\\n' | python main.py wc -L",
    "printf 'abcdef\\rxy\\n' | python main.py wc -L",
    "printf '\\001\\002\\003\\n' | python main.py wc -lw",
    "printf 'a\\001b\\n' | python main.py wc -lw",
    "printf 'a\\nb' | python main.py wc -lwc",
    "printf 'c1\\r\\nc2\\r\\n' | python main.py wc -lwc",
    "printf '' | python main.py wc -lwc",
]


def main() -> None:
    lines: list[str] = []
    for command in COMMANDS:
        proc = subprocess.run(
            [r"E:\software\Git\Git\bin\bash.exe", "-c",
             'cd "%s" && { %s ; } 2>&1' % (ROOT, command)],
            capture_output=True, stdin=subprocess.DEVNULL,
        )
        raw = proc.stdout.replace(b"\r\n", b"\n")
        lines.append("=" * 70)
        lines.append("$ %s" % command)
        lines.append("[退出码] %d" % proc.returncode)
        lines.append("[原始字节] %r" % raw)
        lines.append("[按行]")
        for line in raw.decode("utf-8", errors="replace").split("\n"):
            if line == "" and raw.endswith(b"\n"):
                continue
            lines.append("  |%s|" % line)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("写入 %s" % OUT)


if __name__ == "__main__":
    main()
