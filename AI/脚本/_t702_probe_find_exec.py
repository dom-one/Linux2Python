"""核对 -exec 不带 {} 时 GNU 与本项目的差别。

用法:
    python AI/脚本/_t702_probe_find_exec.py
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

# (场景名, find 参数)
CASES = [
    ("; 无 {} 单个匹配", [".", "-name", "*.md", "-exec", "echo", ";"]),
    ("; 无 {} 两个匹配", [".", "-name", "*.txt", "-exec", "echo", ";"]),
    ("+ 无 {} 两个匹配", [".", "-name", "*.txt", "-exec", "echo", "+"]),
    ("; 带 {} 两个匹配", [".", "-name", "*.txt", "-exec", "echo", "{}", ";"]),
    ("+ 带 {} 两个匹配", [".", "-name", "*.txt", "-exec", "echo", "{}", "+"]),
    ("; 无 {} 命令带参数", [".", "-name", "*.txt", "-exec", "echo", "hello", ";"]),
    ("; 无 {} 命令带参数+批量", [".", "-name", "*.txt", "-exec", "echo", "hello", "+"]),
    ("; 换行命令", [".", "-name", "*.txt", "-exec", "echo", "{}", "\\;"]),
    ("; 无 {} 用 /bin/echo", [".", "-name", "*.md", "-exec", "/bin/echo", ";"]),
    ("; 无 {} 用 ls -d", [".", "-name", "*.md", "-exec", "ls", "-d", ";"]),
    ("; 无 {} 用 printf", [".", "-name", "*.md", "-exec", "printf", "[%s]", ";"]),
    ("; {} 在参数中间", [".", "-name", "*.md", "-exec", "echo", "A{}B", ";"]),
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
        tmp = Path(tempfile.mkdtemp(prefix="find_exec_"))
        work = tmp / "demo"
        shutil.copytree(DEMO, work)
        try:
            g_code, g_out, g_err = _run_gnu(args, work)
            shutil.rmtree(work)
            shutil.copytree(DEMO, work)
            o_code, o_out, o_err = _run_ours(args, work)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        same = g_out == o_out
        print(f"[{'同' if same else '差'}] {name}")
        print(f"    GNU   rc={g_code} stdout={g_out!r}")
        print(f"    本项目 rc={o_code} stdout={o_out!r}")
        if g_err:
            print(f"    GNU   stderr={g_err!r}")
        if o_err:
            print(f"    本项目 stderr={o_err!r}")


if __name__ == "__main__":
    main()
