"""探针十四：区分列宽 W 的两个候选模型。

候选一：W = max(各位数字位数, 下限 7 只在标准输入/目录参与时)
候选二：W = 只由「已知大小的文件」及其 total 决定，标准输入固定占 7

判据：标准输入灌 12345678 字节（8 位）+ 一个 5 位字节的文件。
- 若 W = 8 → total 的字节数（含标准输入）参与 W
- 若 W = 7 → 标准输入的字节数不参与，7 是它的固定下限

同时确认：
- 无操作数时标准输入那一行没有文件名
- 多个操作数时的 total 行文件名是 total
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc14"
TMP.mkdir(exist_ok=True)


def setup() -> None:
    (TMP / "b5.txt").write_bytes(b"h" * 99999)
    (TMP / "b6.txt").write_bytes(b"g" * 999999)


def wc(args, stdin_data=None, loc="C.UTF-8"):
    env = dict(os.environ)
    env["LC_ALL"] = loc
    proc = subprocess.run(
        [WC] + args,
        cwd=str(TMP),
        input=stdin_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr


def show(label, args, stdin_data=None, loc="C.UTF-8"):
    code, out, err = wc(args, stdin_data, loc)
    print(f"{label}")
    print(f"    args={args!r} rc={code}")
    for line in out.splitlines():
        edges = [m.end() for m in re.finditer(r"\d+", line)]
        print(f"    | {line!r}  右边界={edges}")
    if err:
        print(f"    err={err!r}")


def main() -> None:
    setup()

    print("== 1. 判据：标准输入 8 位字节 + 5 位文件 ==")
    show("stdin(12345678) + b5 -lwc", ["-lwc", "-", "b5.txt"], b"x" * 12345678)
    show("stdin(12345678) 单独 -lwc", ["-lwc"], b"x" * 12345678)
    show("stdin(12345678) 单独 -lw", ["-lw"], b"x" * 12345678)
    show("stdin(12345678) + b6 -lwc", ["-lwc", "-", "b6.txt"], b"x" * 12345678)
    print()

    print("== 2. 无操作数时没有文件名 ==")
    show("stdin 无操作数 -lwc", ["-lwc"], b"a b\nc\n")
    show("stdin 带 '-' -lwc", ["-lwc", "-"], b"a b\nc\n")
    print()

    print("== 3. 已知文件的 total 参与 W ==")
    show("b5 + b6 -lwc（total 1099998）", ["-lwc", "b5.txt", "b6.txt"])
    show("b6 + b6 -lwc（total 1999998）", ["-lwc", "b6.txt", "b6.txt"])
    print()

    print("== 4. 确切字节 ==")
    code, out, err = wc(["-lwc"], b"a b\nc\n")
    print(f"    无操作数 bytes={out!r}")
    code, out, err = wc(["-lwc", "-"], b"a b\nc\n")
    print(f"    带 '-' bytes={out!r}")
    code, out, err = wc(["-lwc", "b5.txt", "b6.txt"])
    print(f"    两文件 bytes={out!r}")


if __name__ == "__main__":
    main()
