#!/usr/bin/env python
"""查 awk-lite 的崩溃面：哪些输入会让 Python 抛未捕获异常。

用法：
    python AI/脚本/_t1304_probe_awk_crash.py

起因：`_to_number` 用的是 Python 的 `float()`，它接受 `inf` / `infinity` / `nan`
/ `1e400` / `1_000` 这类写法；`_format_number` 第 445 行又直接 `int(number)`，
于是无穷大抛 OverflowError、NaN 抛 ValueError，异常一路冒到 main.py 顶层，
用户看到的是 Python traceback 而不是本项目统一的错误信息。

本脚本逐条跑，比对「本项目退出码 / 是否有 traceback」与「GNU awk 的行为」。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "产物" / "awk-diff"
AWK = r"E:\software\Git\Git\usr\bin\awk.exe"

# (说明, 项目侧 argv 增量, GNU 侧程序)
CASES = [
    ("-v 赋 inf", ["-v", "x=inf", "{print x}"], "{print x}"),
    ("-v 赋 INF", ["-v", "x=INF", "{print x}"], "{print x}"),
    ("-v 赋 Infinity", ["-v", "x=Infinity", "{print x}"], "{print x}"),
    ("-v 赋 -inf", ["-v", "x=-inf", "{print x}"], "{print x}"),
    ("-v 赋 nan", ["-v", "x=nan", "{print x}"], "{print x}"),
    ("-v 赋 NaN", ["-v", "x=NaN", "{print x}"], "{print x}"),
    ("-v 赋 1e400", ["-v", "x=1e400", "{print x}"], "{print x}"),
    ("-v 赋 1_000", ["-v", "x=1_000", "{print x}"], "{print x}"),
    ("-v 赋 1_0.5", ["-v", "x=1_0.5", "{print x}"], "{print x}"),
    ("变量当字段号 inf", ["-v", "n=inf", "{print $n}"], "{print $n}"),
    ("变量当字段号 nan", ["-v", "n=nan", "{print $n}"], "{print $n}"),
    ("数字字面量 1e400", ["{print 1e400}"], "{print 1e400}"),
    ("数字字面量 1_000", ["{print 1_000}"], "{print 1_000}"),
    ("数字字面量 inf", ["{print inf}"], "{print inf}"),
    ("数字字面量 nan", ["{print nan}"], "{print nan}"),
    ("数字字面量 -inf", ["{print -inf}"], "{print -inf}"),
]


def env() -> dict[str, str]:
    e = dict(os.environ)
    e["MSYS_NO_PATHCONV"] = "1"
    e["LC_ALL"] = "C"
    return e


def main() -> int:
    work = OUT / "work"
    work.mkdir(parents=True, exist_ok=True)
    (work / "one.log").write_bytes(b"a b\n")
    progfile = OUT / "prog_crash.awk"

    print(f"{'用例':<24} {'项目码':<8} {'项目输出/错误':<46} {'GNU码':<7} GNU输出")
    print("-" * 120)
    crashes = []
    for label, extra, gnu_prog in CASES:
        progfile.write_text(gnu_prog + "\n", encoding="utf-8")

        p = subprocess.run(
            [sys.executable, str(ROOT / "main.py"), "awk-lite", *extra, "one.log"],
            cwd=str(work),
            input=b"",
            capture_output=True,
            env=env(),
        )
        g = subprocess.run(
            [AWK, "-f", str(progfile), "one.log"],
            cwd=str(work),
            input=b"",
            capture_output=True,
            env=env(),
        )

        p_out = p.stdout.decode("utf-8", "replace").replace("\r\n", "\n").strip()
        p_err = p.stderr.decode("utf-8", "replace").strip()
        traceback = "Traceback (most recent call last)" in p_err
        if traceback:
            last = p_err.strip().splitlines()[-1] if p_err.strip() else ""
            shown = "!! " + last
            crashes.append((label, last))
        else:
            shown = (p_out or p_err).replace("\n", " | ")[:44]

        g_out = g.stdout.decode("utf-8", "replace").replace("\r\n", "\n").strip()
        g_err = g.stderr.decode("utf-8", "replace").strip().replace("\n", " | ")[:30]
        print(
            f"{label:<24} {p.returncode:<8} {shown:<46} {g.returncode:<7} "
            f"{g_out or g_err}"
        )

    print()
    print(f"能让本项目抛未捕获异常的用例数：{len(crashes)}")
    for label, last in crashes:
        print(f"  - {label}: {last}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
