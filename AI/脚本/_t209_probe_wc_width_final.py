"""探针十：钉死列宽规则的最后判据。

已归纳的模型：
- 列序固定：行数 → 词数 → 字符数(-m) → 字节数(-c) → 最长行(-L)
- 不给选项时默认 行/词/字节；给了就只打印给的
- 一个操作数 + 一列时数字不补空格；其余情况补到统一宽度 W
- W = max(各文件与 total 的 字节数位数)，操作数里出现标准输入或目录时 W 至少 7

待验证：
1. 单文件单列时隐藏的字节数会不会撑宽度（big.txt 的 -l/-w）
2. 宽度是按字节数还是按行数/词数（Z 文件：5000 行短行，字节 10000 五位、行 5000 四位）
3. 目录撑出的 7 会不会被更大位数的文件盖掉
4. total 行的位数是否参与（两文件各 60000 字节，total 120000 六位）
5. 目录行是否算进 total（已验证：不算）
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc10"
TMP.mkdir(exist_ok=True)
(TMP / "adir").mkdir(exist_ok=True)


def setup() -> None:
    # big.txt: 1 行 1 词 12346 字节
    (TMP / "big.txt").write_bytes(b"x" * 12345 + b"\n")
    # Z: 5000 行短行 → 行 5000(4位) 词 5000(4位) 字节 10000(5位)
    (TMP / "z.txt").write_bytes(b"ab\n" * 5000)
    # 两个各 60000 字节 → total 120000（6 位）
    (TMP / "t1.txt").write_bytes(b"c" * 59999 + b"\n")
    (TMP / "t2.txt").write_bytes(b"d" * 59999 + b"\n")
    # 9 位字节
    (TMP / "h9.txt").write_bytes(b"e" * 999999999)
    # 8 位字节
    (TMP / "h8.txt").write_bytes(b"f" * 99999999)


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

    print("== 1. 单文件单列：隐藏字节撑不撑宽度 ==")
    show("big.txt -l", ["-l", "big.txt"])
    show("big.txt -w", ["-w", "big.txt"])
    show("big.txt -c", ["-c", "big.txt"])
    show("big.txt -m", ["-m", "big.txt"])
    show("big.txt -L", ["-L", "big.txt"])
    show("big.txt -lw", ["-lw", "big.txt"])
    print()

    print("== 2. 宽度按字节还是按行/词 ==")
    show("z.txt -lw（行 5000 / 词 5000 / 字节 10000）", ["-lw", "z.txt"])
    show("z.txt -lwc", ["-lwc", "z.txt"])
    show("z.txt -lw + big.txt", ["-lw", "z.txt", "big.txt"])
    print()

    print("== 3. 目录的 7 会不会被盖掉 ==")
    show("目录 + big.txt -lw", ["-lw", "adir", "big.txt"])
    show("目录 + h8.txt -lw", ["-lw", "adir", "h8.txt"])
    show("目录 + h9.txt -lw", ["-lw", "adir", "h9.txt"])
    show("目录单独 -lw", ["-lw", "adir"])
    show("目录 + h9.txt -l", ["-l", "adir", "h9.txt"])
    print()

    print("== 4. total 的位数参与吗 ==")
    show("t1+t2 -lw（各 60000，total 120000）", ["-lw", "t1.txt", "t2.txt"])
    show("t1+t2 -l", ["-l", "t1.txt", "t2.txt"])
    show("t1+t2+big.txt -lw", ["-lw", "t1.txt", "t2.txt", "big.txt"])
    print()

    print("== 5. 标准输入的 7 会不会被盖掉 ==")
    show("stdin + h9.txt -lw", ["-lw", "-", "h9.txt"], b"a\n")
    show("stdin + h8.txt -lw", ["-lw", "-", "h8.txt"], b"a\n")
    show("stdin + big.txt -lw", ["-lw", "-", "big.txt"], b"a\n")
    show("stdin + t1.txt -lw", ["-lw", "-", "t1.txt"], b"a\n")
    print()

    print("== 6. 单文件单列 + 目录 ==")
    show("big.txt -l（无目录）", ["-l", "big.txt"])
    show("目录 -l", ["-l", "adir"])
    show("目录 -lw", ["-lw", "adir"])
    print()

    print("== 7. 多文件单列时的宽度 ==")
    show("big.txt + z.txt -l", ["-l", "big.txt", "z.txt"])
    show("big.txt + z.txt -lw", ["-lw", "big.txt", "z.txt"])


if __name__ == "__main__":
    main()
