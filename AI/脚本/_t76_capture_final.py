"""捕获教程最终要用的命令的确切输出。

按核对器 AI/脚本/_t12_verify_teach.py 的跑法（Git Bash、cwd=项目根、输出重定向到文件）
逐条跑，拿到的就是核对器会看到的文本。

跑法：
    python AI/脚本/_t76_capture_final.py
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
    'python main.py grep -n "def " w2l/entry.py',
    'python main.py grep -rn "command_prog" w2l/',
    'python main.py grep -rn "DMLINUX" bin/',
    'python main.py grep -n "DMLINUX" w2l/entry.py',
    'python -c "import os;from w2l.entry import entry_name;print(\'导入后:\',entry_name());os.environ[\'DMLINUX\']=\'1\';print(\'改环境后:\',entry_name())"',
    'python -m pytest tests/test_launcher.py 2>&1 | tail -1',
    'python -m pytest 2>&1 | tail -1',
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
