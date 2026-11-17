"""核对 find 的三处语义分歧与若干关键机制。

用法:
    python AI/脚本/_t703_probe_find_gaps.py
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
    ("占位符在参数中间 ;", [".", "-name", "*.md", "-exec", "echo", "A{}B", ";"]),
    ("占位符在参数中间 +", [".", "-name", "*.txt", "-exec", "echo", "A{}B", "+"]),
    ("多个占位符", [".", "-name", "*.md", "-exec", "echo", "{}={}", ";"]),
    ("动作截断与链", [".", "-name", "*.txt", "-print", "-o", "-name", "*.md", "-print"]),
    ("动作在 or 左半边", [".", "-type", "d", "-print", "-o", "-name", "*.md", "-print"]),
    ("prune 不算动作", [".", "-type", "d", "-name", "sub", "-prune"]),
    ("delete 算动作", [".", "-name", "*.md", "-delete"]),
    ("printf 不认识的指令", [".", "-name", "*.md", "-printf", "%X\n"]),
    ("printf 未知后缀", [".", "-name", "*.md", "-printf", "%z\n"]),
    ("空表达式括号", [".", "(", ")"]),
    ("路径写在表达式后", [".", "-name", "*.md", "sub"]),
    ("未知谓词", [".", "-没有这个谓词"]),
    ("maxdepth 缺参数", [".", "-maxdepth"]),
    ("不存在的操作数", ["没有这个目录"]),
    ("newer 参照不存在", [".", "-newer", "没有这个文件"]),
]


def _run_gnu(args, cwd):
    cmd = "find " + " ".join(shlex.quote(a) for a in args)
    p = subprocess.run([BASH, "-c", cmd], cwd=str(cwd), capture_output=True)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def _run_ours(args, cwd):
    p = subprocess.run([sys.executable, str(MAIN), "find"] + args, cwd=str(cwd), capture_output=True)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def main():
    for name, args in CASES:
        tmp = Path(tempfile.mkdtemp(prefix="find_gap_"))
        work = tmp / "demo"
        shutil.copytree(DEMO, work)
        try:
            g_code, g_out, g_err = _run_gnu(args, work)
            shutil.rmtree(work)
            shutil.copytree(DEMO, work)
            o_code, o_out, o_err = _run_ours(args, work)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        same = g_out == o_out and g_err == o_err
        print(f"[{'同' if same else '差'}] {name}   参数={args}")
        print(f"    GNU    rc={g_code} out={g_out!r} err={g_err!r}")
        print(f"    本项目 rc={o_code} out={o_out!r} err={o_err!r}")
        print()


if __name__ == "__main__":
    main()
