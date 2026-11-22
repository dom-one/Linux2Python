#!/usr/bin/env python
"""查清「原生 Windows 父进程 → MSYS 子程序」这条路上 argv 的花括号改写。

用法：
    python AI/脚本/_t1302_probe_msys_braces.py

起因：差分对拍时 GNU awk 报 `{print}` 是语法错误，而同一个程序从 Git Bash 里跑
完全正常。说明 argv 在「原生父进程 → MSYS 子程序」这条路上被改写了。

本脚本让 awk 自己把收到的 argv 打出来（`BEGIN { for (i = 0; i < ARGC; i++) print i, ARGV[i] }`），
逐条比「传进去的字符串」与「awk 实际收到的字符串」。

注意：这条路径上 `/` 开头的参数也会被改写成 Windows 路径（已知问题），
本脚本把两种改写放在一起对照。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

AWK = r"E:\software\Git\Git\usr\bin\awk.exe"

DUMP = "BEGIN { for (i = 0; i < ARGC; i++) print i, ARGV[i] }"

# 探针要看的参数
PROBES = [
    "{print}",          # 无空格 + 花括号
    "{print $1}",       # 有空格 + 花括号
    "{print$1}",        # 无空格 + 花括号
    "{print($1, $2)}",  # 有括号有空格
    "a{b}c",
    "{a,b}",
    "/etc/passwd",      # 斜杠开头（已知会被改成 Windows 路径）
    "plain",
]


def env(no_conv: bool) -> dict[str, str]:
    e = dict(os.environ)
    e["LC_ALL"] = "C"
    if no_conv:
        e["MSYS_NO_PATHCONV"] = "1"
    else:
        e.pop("MSYS_NO_PATHCONV", None)
    return e


def run(argv: list[str], no_conv: bool) -> str:
    proc = subprocess.run(
        argv,
        input=b"",
        capture_output=True,
        env=env(no_conv),
        cwd=str(ROOT),
    )
    return proc.stdout.decode("utf-8", "replace").strip()


def main() -> int:
    print("=" * 78)
    print("A. 原生 Python 直接 spawn MSYS 的 awk.exe（不经 bash）")
    print("=" * 78)
    for no_conv in (False, True):
        label = "MSYS_NO_PATHCONV=1" if no_conv else "默认（不设）"
        print(f"\n--- {label} ---")
        for probe in PROBES:
            out = run([AWK, DUMP, probe], no_conv)
            got = ""
            for line in out.splitlines():
                if line.startswith("1 "):
                    got = line[2:]
            flag = "改写了" if got != probe else "原样"
            print(f"  传入 {probe!r}")
            print(f"    实收 {got!r}   <- {flag}")

    print()
    print("=" * 78)
    print("B. 经 bash -c 传给 awk（bash 自身不做花括号展开）")
    print("=" * 78)
    for probe in PROBES:
        cmd = f"awk '{DUMP}' '{probe}'"
        out = run(["bash", "-c", cmd], False)
        got = ""
        for line in out.splitlines():
            if line.startswith("1 "):
                got = line[2:]
        flag = "改写了" if got != probe else "原样"
        print(f"  传入 {probe!r}")
        print(f"    实收 {got!r}   <- {flag}")

    print()
    print("=" * 78)
    print("C. 绕法：程序写进文件，用 awk -f 读")
    print("=" * 78)
    prog = ROOT / "AI" / "产物" / "awk-diff" / "argv_dump.awk"
    prog.parent.mkdir(parents=True, exist_ok=True)
    prog.write_text(DUMP + "\n", encoding="utf-8")
    for probe in PROBES:
        out = run([AWK, "-f", str(prog), probe], False)
        got = ""
        for line in out.splitlines():
            if line.startswith("1 "):
                got = line[2:]
        flag = "改写了" if got != probe else "原样"
        print(f"  传入 {probe!r}")
        print(f"    实收 {got!r}   <- {flag}")

    print()
    print("=" * 78)
    print("D. 本项目入口（原生 python.exe）会不会被改写")
    print("=" * 78)
    work = ROOT / "AI" / "产物" / "awk-diff" / "work"
    for probe in ["{print}", "{print $1}", "{print$1}"]:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "main.py"), "awk-lite", probe, "app.log"],
            capture_output=True,
            cwd=str(work),
        )
        out = proc.stdout.decode("utf-8", "replace").strip().replace("\r\n", "\n")
        err = proc.stderr.decode("utf-8", "replace").strip()
        print(f"  程序 {probe!r} 退出码 {proc.returncode}")
        print(f"    输出 {out.splitlines()[:2]!r}")
        if err:
            print(f"    错误 {err}")

    print()
    print("=" * 78)
    print("E. 从 cmd.exe 经 bash 调用 awk.exe（模拟用户从 cmd 里用 awk）")
    print("=" * 78)
    for probe in ["{print}", "{print $1}"]:
        cmd = f'cmd //c "awk \\"{probe}\\" app.log"'
        out = run(["bash", "-c", f"MSYS_NO_PATHCONV=1 {cmd}"], False)
        print(f"  程序 {probe!r} 输出首行 {out.splitlines()[:1]!r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
