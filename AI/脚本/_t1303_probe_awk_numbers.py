#!/usr/bin/env python
"""查 GNU awk 5.3.2 与本项目在「数字转字符串」上的分界。

用法：
    python AI/脚本/_t1303_probe_awk_numbers.py

要查两件事：
1. 整数常量打印到多大仍是完整数字、多大开始变成科学计数（CONVFMT %.6g 的边界）。
   本项目 `_format_number` 用 `abs(number) < 1e16` 判断，GNU 的门槛与之不同。
2. `-v name=value` 赋的值是「字符串」还是「数字」：
   GNU 把命令行赋值当字符串原样打印（`-v x=007` 打 007），
   本项目的 `_as_text` 会把能转成数字的字符串转成数字（打 7）。
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

VALUES = [
    "1",
    "42",
    "10000000",
    "100000000",
    "1000000000",
    "1000000000000",
    "1000000000000000",
    "10000000000000000",
    "100000000000000000",
    "1000000000000000000",
    "10000000000000000000",
    "100000000000000000000",
    "1000000000000000000000",
    "100000000000000000000000",
    "9007199254740993",
    "123456789012345678901",
    "0.1",
    "3.14159265358979",
    "1e3",
    "1e15",
    "1e16",
    "1e17",
    "1e18",
    "1e19",
    "1e20",
    "1e21",
    "1e22",
    "1e23",
]

ASSIGN_VALUES = ["007", "1e3", "1.5", "0x10", " 12 ", "1_000", "INF", "nan"]


def env() -> dict[str, str]:
    e = dict(os.environ)
    e["MSYS_NO_PATHCONV"] = "1"
    e["LC_ALL"] = "C"
    return e


def run(argv: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(
        argv, cwd=str(cwd), input=b"", capture_output=True, env=env()
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace").strip()


def main() -> int:
    work = OUT / "work"
    work.mkdir(parents=True, exist_ok=True)
    (work / "one.log").write_bytes(b"x\n")
    progfile = OUT / "prog_num.awk"

    print("=" * 72)
    print("一、整数常量的打印边界（{print <数值>}）")
    print("=" * 72)
    print(f"{'字面量':<26} {'本项目':<26} {'GNU awk':<26} 同")
    for value in VALUES:
        progfile.write_text(f"{{print {value}}}\n", encoding="utf-8")
        pcode, pout = run(
            [sys.executable, str(ROOT / "main.py"), "awk-lite", f"{{print {value}}}", "one.log"],
            work,
        )
        gcode, gout = run([AWK, "-f", str(progfile), "one.log"], work)
        p = pout.replace("\r\n", "\n").strip()
        g = gout.replace("\r\n", "\n").strip()
        print(f"{value:<26} {p:<26} {g:<26} {'一致' if p == g else '★差异'}")

    print()
    print("=" * 72)
    print("二、-v 赋的值打印成什么")
    print("=" * 72)
    print(f"{'-v 的值':<12} {'本项目':<20} {'GNU awk':<20} 同")
    for value in ASSIGN_VALUES:
        progfile.write_text("{print x}\n", encoding="utf-8")
        pcode, pout = run(
            [sys.executable, str(ROOT / "main.py"), "awk-lite", "-v", f"x={value}", "{print x}", "one.log"],
            work,
        )
        gcode, gout = run([AWK, "-v", f"x={value}", "-f", str(progfile), "one.log"], work)
        p = pout.replace("\r\n", "\n").strip()
        g = gout.replace("\r\n", "\n").strip()
        print(f"{value!r:<12} {p:<20} {g:<20} {'一致' if p == g else '★差异'}")

    print()
    print("=" * 72)
    print("三、动作里赋值 vs 命令行赋值（GNU 的 strnum 规则）")
    print("=" * 72)
    for prog in ["BEGIN { x = 007; print x }", "{ x = 007; print x }"]:
        progfile.write_text(prog + "\n", encoding="utf-8")
        gcode, gout = run([AWK, "-f", str(progfile), "one.log"], work)
        print(f"  GNU {prog!r} -> {gout!r}")

    print()
    print("=" * 72)
    print("四、-F 空串与能匹配空串的分隔符")
    print("=" * 72)
    (work / "abc.txt").write_bytes(b"abc\n")
    for fs in ["", "x*", "[a-z]*", "a*"]:
        progfile.write_text("{print NF}\n", encoding="utf-8")
        gcode, gout = run([AWK, "-F", fs, "-f", str(progfile), "abc.txt"], work)
        pcode, pout = run(
            [sys.executable, str(ROOT / "main.py"), "awk-lite", "-F", fs, "{print NF}", "abc.txt"],
            work,
        )
        print(f"  -F {fs!r:<10} GNU -> {gout!r:<14} 项目 -> {pout.replace(chr(13), '').strip()!r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
