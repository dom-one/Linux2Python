"""探针二十三：最后一批判别项。

要定案的：
1. W 是否取「所有文件字节数之和」的位数：nine(9B) + tiny(1B) → 和=10（2 位）
   若 W=2 则「和」参与，若 W=1 则只看各文件最大值
2. 两个文件 + 一列时是否补空格（单数字不补空格的规则边界）
3. GBK / UTF-8 / 二进制 的 -m 与 -L 精确数值
4. CRLF 文件的 -L（\\r 算不算宽度）
5. 缺文件、目录的行输出形态
6. total 行的 -L 是最大值
7. 末行无换行时的行数与 -L
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc23"
TMP.mkdir(exist_ok=True)
(TMP / "adir").mkdir(exist_ok=True)


def setup() -> None:
    (TMP / "tiny.txt").write_bytes(b"a")
    (TMP / "nine.txt").write_bytes(b"a" * 9)
    (TMP / "ten.txt").write_bytes(b"a" * 10)
    (TMP / "gbk.txt").write_bytes("中文\n".encode("gb18030"))
    (TMP / "u8.txt").write_bytes("中文\n".encode("utf-8"))
    (TMP / "bin.dat").write_bytes(bytes(range(256)))
    (TMP / "crlf.txt").write_bytes(b"c1\r\nc2\r\n")
    (TMP / "nonl.txt").write_bytes(b"p1\np2\np3")
    (TMP / "ws.txt").write_bytes(b"a b\tc\rd\x0be\x0cf\n")
    (TMP / "long.txt").write_bytes(b"x" * 20 + b"\n" + b"y" * 5)


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
        print(f"    | {line!r}")
    if err:
        print(f"    err={err!r}")


def main() -> None:
    setup()

    print("== 1. W 是否看「和」 ==")
    show("nine(9) + tiny(1) -lw → 和=10（2 位）", ["-lw", "nine.txt", "tiny.txt"])
    show("ten + ten -l → 和=20（2 位），两文件一列", ["-l", "ten.txt", "ten.txt"])
    show("ten 单独 -l（单数字）", ["-l", "ten.txt"])
    print()

    print("== 2. 编码相关的 -m 与 -L ==")
    show("u8.txt -mwcL (C.UTF-8)", ["-mwcL", "u8.txt"])
    show("gbk.txt -mwcL (C.UTF-8)", ["-mwcL", "gbk.txt"])
    show("gbk.txt -mwcL (C)", ["-mwcL", "gbk.txt"], loc="C")
    show("bin.dat -mwcL (C.UTF-8)", ["-mwcL", "bin.dat"])
    show("bin.dat -mwcL (C)", ["-mwcL", "bin.dat"], loc="C")
    print()

    print("== 3. CRLF 与末行无换行 ==")
    show("crlf.txt -lwcL", ["-lwcL", "crlf.txt"])
    show("nonl.txt -lwcL", ["-lwcL", "nonl.txt"])
    show("ws.txt -lw", ["-lw", "ws.txt"])
    print()

    print("== 4. 缺文件 / 目录 ==")
    show("缺 + tiny", ["-lw", "nope.txt", "tiny.txt"])
    show("adir", ["-lw", "adir"])
    show("adir 单独一列", ["-l", "adir"])
    print()

    print("== 5. total 的 -L ==")
    show("long + tiny -L", ["-L", "long.txt", "tiny.txt"])
    show("long + tiny -lL", ["-lL", "long.txt", "tiny.txt"])


if __name__ == "__main__":
    main()
