"""探针二：head 的 argv 改写到底解决了什么。

用法:
    python AI/脚本/_t91_probe_head_argv.py

做两件事:
1. 用裸 argparse 跑 `-3` 和 `-n -3`，看它怎么失败
2. 用 head.py 自己的 _rewrite_argv 跑同一批参数，看改写成了什么

产出:
    AI/数据/_t91_head_argv.txt
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "数据", "_t91_head_argv.txt")

sys.path.insert(0, ROOT)

from w2l.commands.head import _rewrite_argv  # noqa: E402

BASH_CANDIDATES = [
    r"E:\software\Git\Git\bin\bash.exe",
    r"C:\Program Files\Git\bin\bash.exe",
    r"C:\Program Files (x86)\Git\bin\bash.exe",
]
BASH_BIN = next((p for p in BASH_CANDIDATES if os.path.isfile(p)), None)

ARGV_CASES = [
    ["-3", "w2l/registry.py"],
    ["-n", "-3", "w2l/registry.py"],
    ["-n", "3", "w2l/registry.py"],
    ["-c", "-5", "w2l/registry.py"],
    ["-n", "+3", "w2l/registry.py"],
    ["-2k", "w2l/registry.py"],
    ["--", "-3"],
]

# 单个减号操作数的补充命令（前一轮探针误写了两个 -）
BASH_CASES = [
    ("末行无换行 单减号", "printf 'p1\\np2\\np3' | python main.py head - | od -c"),
    ("二进制透传 单减号", "printf 'a\\x00b\\xff' | python main.py head - | od -c"),
    ("GBK 取2字节 源字节", "printf '\\xd6\\xd0\\xce\\xc4\\n' | python main.py head -c 2 - | od -c"),
    ("GBK 取2字节 输出字节数", "printf '\\xd6\\xd0\\xce\\xc4\\n' | python main.py head -c 2 - | wc -c"),
    ("GNU GBK 取2字节 输出字节数", "printf '\\xd6\\xd0\\xce\\xc4\\n' | head -c 2 | wc -c"),
    ("GNU GBK 原文", "printf '\\xd6\\xd0\\xce\\xc4\\n' | head - | od -c"),
    ("本项目 GBK 原文", "printf '\\xd6\\xd0\\xce\\xc4\\n' | python main.py head - | od -c"),
    ("两文件都缺", "python main.py head -v -n 1 w2l/nope.txt w2l/also-nope.txt; echo \"退出码=$?\""),
    ("目录后继续处理", "python main.py head -n 1 w2l w2l/context.py; echo \"退出码=$?\""),
]


def main() -> int:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("### 1. 裸 argparse 的行为\n")
        parser = argparse.ArgumentParser(prog="python main.py head")
        parser.add_argument("-n", "--lines", dest="count_specs", action="append")
        parser.add_argument("files", nargs="*")
        for argv in ARGV_CASES:
            handle.write(f"\nargv={argv}\n")
            try:
                namespace = parser.parse_args(list(argv))
                handle.write(f"  解析成功: count_specs={namespace.count_specs} files={namespace.files}\n")
            except SystemExit as exc:
                handle.write(f"  解析失败: SystemExit({exc.code})\n")
            handle.write(f"  _rewrite_argv 改写后: {_rewrite_argv(list(argv))}\n")

        handle.write("\n\n### 2. 补充命令\n")
        if BASH_BIN is None:
            handle.write("找不到 Git Bash\n")
            return 2
        for label, command in BASH_CASES:
            proc = subprocess.run(
                [BASH_BIN, "-c", command],
                cwd=ROOT,
                capture_output=True,
                timeout=120,
            )
            handle.write("=" * 72 + "\n")
            handle.write(f"[{label}]\n$ {command}\n")
            handle.write(f"退出码={proc.returncode}\n")
            handle.write("--- stdout ---\n")
            handle.write(proc.stdout.decode("utf-8", errors="replace"))
            handle.write("--- stderr ---\n")
            handle.write(proc.stderr.decode("utf-8", errors="replace"))

    print(f"探针输出写到 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
