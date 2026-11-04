"""测试索引页第 2 步要用的结构命令。

要点：
1. 顶层 ls 的输出
2. 源码目录 ls 的输出（w2l / w2l/commands / tests / bin）
3. 合并成一条命令时的输出（核对器会把多行用 && 串起来）

跑法：
    python AI/脚本/_t78_probe_index_cmd.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BASH = r"E:\software\Git\Git\bin\bash.exe"


def decode(raw: bytes) -> str:
    for enc in ("utf-8", "gbk", "cp936"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def run(command: str, timeout: int = 120):
    handle, outpath = tempfile.mkstemp(suffix=".txt")
    os.close(handle)
    try:
        full = 'cd "%s" && { %s ; } > "%s" 2>&1' % (ROOT, command, outpath)
        proc = subprocess.run([BASH, "-c", full], capture_output=True,
                              stdin=subprocess.DEVNULL, timeout=timeout)
        with open(outpath, "rb") as fh:
            return proc.returncode, decode(fh.read()).strip()
    finally:
        try:
            os.remove(outpath)
        except OSError:
            pass


COMMANDS = [
    "python main.py ls .",
    "python main.py ls w2l/ && python main.py ls w2l/commands/ && python main.py ls tests/ && python main.py ls bin/",
    "python main.py ls -1 .",
]


def main() -> None:
    for idx, cmd in enumerate(COMMANDS, 1):
        rc, out = run(cmd)
        print("")
        print("#" * 70)
        print("# [%d] %s" % (idx, cmd))
        print("# rc=%d" % rc)
        print("#" * 70)
        print(out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
