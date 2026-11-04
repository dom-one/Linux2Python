"""捕获教程里要写的命令的精确输出。

按 AI/脚本/_t12_verify_teach.py 的跑法（Git Bash、cwd=项目根、输出重定向到文件）
逐条跑一遍，把真实输出打出来，方便把「预期输出」抄准。

跑法：
    python AI/脚本/_t72_capture_tutorial.py
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


def run(command: str, timeout: int = 60):
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
    "python -c \"from w2l.entry import entry_name, command_prog;print(entry_name());print(command_prog('grep'))\"",
    "DMLINUX=1 python -c \"from w2l.entry import entry_name, command_prog;print(entry_name());print(command_prog('grep'))\"",
    "python main.py --help",
    "DMLINUX=1 python main.py --help",
    "python -c \"from w2l.commands.grep import build_parser;print(build_parser().format_usage())\"",
    "DMLINUX=1 python -c \"from w2l.commands.grep import build_parser;print(build_parser().format_usage())\"",
    "python main.py grep -Z",
    "DMLINUX=1 python main.py grep -Z",
    "DMLINUX=0 python main.py --help",
    "DMLINUX= python main.py --help",
    "python -c \"import sys;sys.argv[0]='main.py';import argparse;p=argparse.ArgumentParser();print('默认 prog =',p.prog)\"",
    "python -c \"import sys;sys.argv[0]='E:/1/NULL/Windows-to-Linux/main.py';import argparse;p=argparse.ArgumentParser();print('默认 prog =',p.prog)\"",
    "python main.py grep -n \"main.py\" bin/dmlinux.cmd",
    "PATH=\"$PATH:$PWD/bin\" dmlinux --help",
    "PATH=\"$PATH:$PWD/bin\" dmlinux grep --help",
    "python -c \"import os;print('DMLINUX in env =', repr(os.environ.get('DMLINUX')))\"",
    "DMLINUX=1 python -c \"import os;print('DMLINUX in env =', repr(os.environ.get('DMLINUX')))\"",
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
