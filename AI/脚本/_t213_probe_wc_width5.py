"""探针十三：钉死列宽模型的三处判据。

待确认：
1. 隐藏的 -L（最长行显示宽度）算不算进列宽 W
   造一个字节数 1 位、但 -L 显示宽度 2 位的文件（5 个制表符）
2. 标准输入的字节数算不算进 total 的列宽
   造 999999 字节的文件 + 2 字节标准输入：
   - total 含标准输入 → total 字节 1000001（7 位）→ W=7
   - total 不含标准输入 → 999999（6 位）→ W=6
   同时看 total 行实际打印的字节数
3. 「整个输出只有一个数字时不补空格」这条规则的确切范围
   - 两个操作数都缺时只剩 total 一行 → 1 个数字
   - 目录 + 单列 → 1 个数字，且下限 7 也没生效
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc13"
TMP.mkdir(exist_ok=True)
(TMP / "adir").mkdir(exist_ok=True)


def setup() -> None:
    # 6 位字节、1 行
    (TMP / "a6.txt").write_bytes(b"g" * 999999)
    # 5 个制表符：6 字节（1 位），但 -L 显示宽度 40（2 位）
    (TMP / "tabs5.rst").write_bytes(b"\t" * 5 + b"\n")
    # 8 个制表符：9 字节（1 位），-L 宽度 64（2 位）
    (TMP / "tabs8.rst").write_bytes(b"\t" * 8 + b"\n")
    # 行数 2 位、字节 2 位
    (TMP / "l2.txt").write_bytes(b"a\n" * 10)


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

    print("== 1. 隐藏的 -L 算不算进 W ==")
    show("tabs5.rst -lw（字节 6=1位，-L 40=2位）", ["-lw", "tabs5.rst"])
    show("tabs5.rst -lwcL", ["-lwcL", "tabs5.rst"])
    show("tabs5.rst -L", ["-L", "tabs5.rst"])
    show("tabs8.rst -lw", ["-lw", "tabs8.rst"])
    show("tabs8.rst -lwcL", ["-lwcL", "tabs8.rst"])
    print()

    print("== 2. 标准输入与 total 的位数 ==")
    show("a6 + stdin -lwc", ["-lwc", "a6.txt", "-"], b"a\n")
    show("stdin + a6 -lwc", ["-lwc", "-", "a6.txt"], b"a\n")
    show("a6 单独 -lwc", ["-lwc", "a6.txt"])
    show("a6 + stdin -lw", ["-lw", "a6.txt", "-"], b"a\n")
    print()

    print("== 3. 只有一个数字的场景 ==")
    show("两个缺文件 -l", ["-l", "nope.txt", "nope2.txt"])
    show("目录 -l", ["-l", "adir"])
    show("目录 -lw", ["-lw", "adir"])
    show("目录 + 缺 -l", ["-l", "adir", "nope.txt"])
    show("缺 + 目录 -l", ["-l", "nope.txt", "adir"])
    show("l2.txt -l", ["-l", "l2.txt"])
    show("l2.txt -lw", ["-lw", "l2.txt"])
    print()

    print("== 4. total 行的文件名 ==")
    show("a6 + l2 -lwc", ["-lwc", "a6.txt", "l2.txt"])
    show("a6 + l2 + a6 -lwc", ["-lwc", "a6.txt", "l2.txt", "a6.txt"])


if __name__ == "__main__":
    main()
