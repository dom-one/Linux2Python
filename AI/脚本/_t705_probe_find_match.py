"""核对 find 的匹配细节：-regex 是否整串锚定、-name 是否区分大小写、-path 的 * 是否跨 /。

用法:
    python AI/脚本/_t705_probe_find_match.py
"""

from __future__ import annotations

import fnmatch
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
    ("regex 前缀锚定", [".", "-regex", r"\.md$"]),
    ("regex 整串锚定", [".", "-regex", r".*\.md$"]),
    ("regex 中间不锚定", [".", "-regex", r"notes"]),
    ("regex 带路径", [".", "-regex", r".*/sub/.*"]),
    ("path 跨斜杠", [".", "-path", "*/sub/*"]),
    ("path 不跨斜杠", [".", "-path", "*/sub*"]),
    ("name 不跨斜杠", [".", "-name", "*deep*"]),
    ("name 问号通配", [".", "-name", "?.txt"]),
    ("name 字符类", [".", "-name", "[ab].txt"]),
    ("iname 字符类", [".", "-iname", "[AB].txt"]),
]


def _run_gnu(args, cwd):
    cmd = "find " + " ".join(shlex.quote(a) for a in args)
    p = subprocess.run([BASH, "-c", cmd], cwd=str(cwd), capture_output=True)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def _run_ours(args, cwd):
    p = subprocess.run([sys.executable, str(MAIN), "find"] + args, cwd=str(cwd), capture_output=True)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def main() -> None:
    print("== fnmatch 在本机的行为 ==")
    print(f"  os.name = {os.name}")
    print(f"  fnmatch.fnmatch('B.TXT', '*.txt')      = {fnmatch.fnmatch('B.TXT', '*.txt')}")
    print(f"  fnmatch.fnmatchcase('B.TXT', '*.txt')  = {fnmatch.fnmatchcase('B.TXT', '*.txt')}")
    print(f"  fnmatch.fnmatch('a/b', '*')            = {fnmatch.fnmatch('a/b', '*')}")
    print(f"  fnmatch.fnmatchcase('a/b', '*')        = {fnmatch.fnmatchcase('a/b', '*')}")
    print()

    for name, args in CASES:
        tmp = Path(tempfile.mkdtemp(prefix="find_match_"))
        work = tmp / "demo"
        shutil.copytree(DEMO, work)
        try:
            g_code, g_out, _ = _run_gnu(args, work)
            shutil.rmtree(work)
            shutil.copytree(DEMO, work)
            o_code, o_out, _ = _run_ours(args, work)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        g_lines = g_out.splitlines()
        o_lines = o_out.splitlines()
        same = g_lines == o_lines
        print(f"[{'同' if same else '差'}] {name:16} 参数={args[1:]}")
        print(f"    GNU    {g_lines}")
        print(f"    本项目 {o_lines}")


if __name__ == "__main__":
    main()
