"""探针十五：判定 total 行是否参与列宽 W。

判据：两个各 99999 字节的文件（5 位），total = 199998（6 位）。
- 若 W = 6 → total 行的字节数参与 W
- 若 W = 5 → 只有各文件自己的字节数参与 W

同时验证：
- 两个 999999 字节的文件（6 位），total = 1999998（7 位）
- 标准输入的字节数不参与 W（前面已见，这里再确认一次）
- total 行与文件行的列宽是否始终一致
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc15"
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

    print("== 1. total 是否参与 W ==")
    show("b5 + b5 -lw（各 5 位，total 199998=6位）", ["-lw", "b5.txt", "b5.txt"])
    show("b5 + b5 -l（各 5 位，total 6 位）", ["-l", "b5.txt", "b5.txt"])
    show("b6 + b6 -lw（各 6 位，total 1999998=7位）", ["-lw", "b6.txt", "b6.txt"])
    show("b6 + b6 -l", ["-l", "b6.txt", "b6.txt"])
    print()

    print("== 2. 标准输入 ==")
    show("stdin(9999999) + b5 -lw", ["-lw", "-", "b5.txt"], b"x" * 9999999)
    show("stdin(9999999) + b5 -l", ["-l", "-", "b5.txt"], b"x" * 9999999)
    print()

    print("== 3. 空文件与 total ==")
    (TMP / "empty.txt").write_bytes(b"")
    show("empty + b5 -lwc", ["-lwc", "empty.txt", "b5.txt"])
    show("b5 + empty -lwc", ["-lwc", "b5.txt", "empty.txt"])


if __name__ == "__main__":
    main()
