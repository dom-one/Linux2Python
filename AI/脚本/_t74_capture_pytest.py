"""捕获教程结尾要用的 pytest 输出原文。

跑法：
    python AI/脚本/_t74_capture_pytest.py
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
    "python -m pytest tests/test_launcher.py",
    "python -m pytest tests/test_launcher.py -q",
    "python -m pytest",
    "python -m pytest --collect-only -q | tail -1",
    "python -m pytest -k entry_name",
]


def main() -> None:
    for idx, cmd in enumerate(COMMANDS, 1):
        rc, out = run(cmd)
        print("")
        print("#" * 70)
        print("# [%d] %s   (rc=%d)" % (idx, cmd, rc))
        print("#" * 70)
        print(repr(out))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
