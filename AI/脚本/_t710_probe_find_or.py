"""核对 -o 两边都是动作时的短路行为（左分支是裸动作的情况）。

用法:
    python AI/脚本/_t710_probe_find_or.py
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DEMO = Path(ROOT) / "AI" / "数据" / "find_demo"
MAIN = Path(ROOT) / "main.py"
BASH = r"E:\software\Git\Git\bin\bash.exe"

CASES = [
    ("左分支是裸 -print",
     [".", "-print", "-o", "-name", "*.md", "-print"]),
    ("左分支是 -name 加 -print",
     [".", "-name", "*.md", "-print", "-o", "-name", "*.txt", "-print"]),
    ("左分支是裸 -print0",
     [".", "-print0", "-o", "-name", "*.md", "-print0"]),
]


def _run_gnu(args, cwd):
    cmd = "find " + " ".join(shlex.quote(a) for a in args)
    p = subprocess.run([BASH, "-c", cmd], cwd=str(cwd), capture_output=True)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def _run_ours(args, cwd):
    p = subprocess.run([sys.executable, str(MAIN), "find"] + args, cwd=str(cwd), capture_output=True)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def main() -> None:
    for name, args in CASES:
        tmp = Path(tempfile.mkdtemp(prefix="find_or_"))
        work = tmp / "demo"
        shutil.copytree(DEMO, work)
        try:
            _, g_out, g_err = _run_gnu(args, work)
            shutil.rmtree(work)
            shutil.copytree(DEMO, work)
            _, o_out, o_err = _run_ours(args, work)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        g_lines = [ln for ln in g_out.splitlines() if ln]
        o_lines = [ln for ln in o_out.splitlines() if ln]
        print(f"[{'同' if g_lines == o_lines else '差'}] {name}   参数={args[1:]}")
        print(f"    GNU    {len(g_lines)} 行: {g_lines}")
        print(f"    本项目 {len(o_lines)} 行: {o_lines}")
        dup = len(o_lines) != len(set(o_lines))
        print(f"    本项目有重复行：{'是' if dup else '否'}")
        print()


if __name__ == "__main__":
    main()
