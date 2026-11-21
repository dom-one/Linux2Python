#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针：为什么 bash -c 跑出来的 sed 输出是空的。

上一轮探针里，bash -c 跑 `python main.py sed -n '\\|bravo|p' <文件>`
拿到 exit=0 但 stdout 是空串，而同样的命令在交互式 bash 里明明打出 bravo。
这一轮要查清差别在哪。

用法：python AI/脚本/_t1015_probe_sed_bash_out.py
产物：AI/数据/sed_bash_out_report.txt
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "sed_bash_out_report.txt"
BASH = r"E:\software\Git\Git\bin\bash.exe"

sys.path.insert(0, str(ROOT))
from w2l.commands.sed import run_sed  # noqa: E402


def show(label, cmd, use_bash=True, **kw):
    if use_bash:
        argv = [BASH, "-c", cmd]
    else:
        argv = cmd
    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          cwd=str(ROOT), **kw)
    print(f"--- {label}")
    print(f"  argv={argv}")
    print(f"  exit={proc.returncode}")
    print(f"  stdout_bytes={proc.stdout!r}")
    print(f"  stderr={proc.stderr.decode('utf-8', 'replace').strip()!r}")
    print()
    return proc


def main() -> int:
    L: list[str] = []
    keep = L.append

    keep("=" * 70)
    keep("一、bash -c 各种写法")
    keep("=" * 70)
    for label, cmd in (
        ("竖线地址", r"python main.py sed -n '\|bravo|p' AI/数据/sed_demo/a.txt"),
        ("斜杠地址", r"python main.py sed -n '/bravo/p' AI/数据/sed_demo/a.txt"),
        ("替换", r"python main.py sed 's/a/b/' AI/数据/sed_demo/a.txt"),
        ("替换后加 cat", r"python main.py sed 's/a/b/' AI/数据/sed_demo/a.txt | cat"),
        ("pwd 检查", r"pwd"),
        ("ls 检查", r"ls AI/数据/sed_demo/"),
        ("python 直接跑", r"python -c \"print('hi')\""),
    ):
        keep(f"### {label}")
        proc = subprocess.run([BASH, "-c", cmd], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, cwd=str(ROOT))
        keep(f"  cmd={cmd}")
        keep(f"  exit={proc.returncode}")
        keep(f"  stdout_bytes={proc.stdout!r}")
        keep(f"  stderr={proc.stderr.decode('utf-8', 'replace').strip()!r}")
        keep("")

    keep("=" * 70)
    keep("二、不经 bash，直接 spawn python.exe（Windows 原生）")
    keep("=" * 70)
    for label, argv in (
        ("竖线地址", [sys.executable, "main.py", "sed", "-n", r"\|bravo|p",
                      "AI/数据/sed_demo/a.txt"]),
        ("斜杠地址", [sys.executable, "main.py", "sed", "-n", "/bravo/p",
                      "AI/数据/sed_demo/a.txt"]),
    ):
        proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              cwd=str(ROOT))
        keep(f"### {label}")
        keep(f"  argv={argv}")
        keep(f"  exit={proc.returncode}")
        keep(f"  stdout_bytes={proc.stdout!r}")
        keep(f"  stderr={proc.stderr.decode('utf-8', 'replace').strip()!r}")
        keep("")

    keep("=" * 70)
    keep("三、run_sed 层（不经 stdout 重定向）")
    keep("=" * 70)
    code, so, se = run_sed(["-n", r"\|bravo|p", "AI/数据/sed_demo/a.txt"], cwd=ROOT)
    keep(f"  exit={code} stdout={so!r} stderr={se!r}")
    keep("")

    keep("=" * 70)
    keep("四、stdout 是不是被 _configure_streams 改过")
    keep("=" * 70)
    cli_src = (ROOT / "w2l" / "cli.py").read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(cli_src, 1):
        if "reconfigure" in line or "SetConsoleOutputCP" in line or "encoding" in line:
            keep(f"  第 {i} 行: {line.strip()}")
    keep("")

    OUT.write_text("\n".join(L), encoding="utf-8", newline="\n")
    print("\n".join(L))
    print(f"[result] 报告已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
