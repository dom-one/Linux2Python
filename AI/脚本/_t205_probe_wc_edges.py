"""探针六：钉死 -L 的宽度语义与几个边角行为。

已归纳：
- -L 算的是显示宽度（中日韩全角字符算 2），不是字符数也不是字节数
- 控制字符（\r \t 等）宽度算 0
- 单词以 isspace 字符分隔（\r \v \f 也算）
- 行数只数 \\n

这一轮确认：
1. 制表符、\\r、控制字符在 -L 里算多少
2. 行尾空格算不算
3. 末行没有换行符时 -L 怎么算
4. 目录操作数在多文件时怎么算、算不算进 total
5. 多个 - 操作数时标准输入只读一次
6. 空文件与只含换行的文件
7. 同一个文件给两次时 total 是不是翻倍
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc6"
TMP.mkdir(exist_ok=True)
(TMP / "adir").mkdir(exist_ok=True)


def setup() -> None:
    (TMP / "tab.txt").write_bytes(b"a\tb\n")
    (TMP / "cr.txt").write_bytes(b"abc\r\n")
    (TMP / "crmid.txt").write_bytes(b"a\rb\n")
    (TMP / "sp.txt").write_bytes(b"ab  \ncd\n")
    (TMP / "nonl.txt").write_bytes(b"abcd")
    (TMP / "nonl2.txt").write_bytes(b"ab\ncdef")
    (TMP / "bs.txt").write_bytes(b"a\x08b\n")
    (TMP / "mix2.txt").write_bytes(b"a\x00b\nc\n")
    (TMP / "wide.txt").write_bytes("漢\nab\n".encode("utf-8"))
    (TMP / "comb.txt").write_bytes("éx\n".encode("utf-8"))
    (TMP / "twice.txt").write_bytes(b"a b\nc\n")


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

    print("== 1. -L 里各种字符算多少宽度 ==")
    show("tab.txt (a\\tb) -L", ["-L", "tab.txt"])
    show("tab.txt -Lc", ["-Lc", "tab.txt"])
    show("cr.txt (abc\\r\\n) -L", ["-L", "cr.txt"])
    show("cr.txt C locale -L", ["-L", "cr.txt"], loc="C")
    show("crmid.txt (a\\rb) -L", ["-L", "crmid.txt"])
    show("bs.txt (a\\bb) -L", ["-L", "bs.txt"])
    show("wide.txt (漢/ab) -L", ["-L", "wide.txt"])
    show("comb.txt (é/x) -L", ["-L", "comb.txt"])
    print()

    print("== 2. 行尾空格与末行无换行 ==")
    show("sp.txt (ab  /cd) -L", ["-L", "sp.txt"])
    show("nonl.txt (abcd) -L", ["-L", "nonl.txt"])
    show("nonl.txt -lwc", ["-lwc", "nonl.txt"])
    show("nonl2.txt (ab/cdef) -L", ["-lwcL", "nonl2.txt"])
    print()

    print("== 3. 含 NUL 的文件 ==")
    show("mix2.txt -lwc", ["-lwc", "mix2.txt"])
    show("mix2.txt -L", ["-L", "mix2.txt"])
    show("mix2.txt -m", ["-m", "mix2.txt"])
    print()

    print("== 4. 目录操作数 ==")
    show("目录单独 -l", ["-l", "adir"])
    show("目录+文件 -lwc", ["-lwc", "adir", "twice.txt"])
    show("文件+目录 -lwc", ["-lwc", "twice.txt", "adir"])
    show("目录+目录 -lwc", ["-lwc", "adir", "adir"])
    print()

    print("== 5. 多个 - 操作数 ==")
    show("两个 -", ["-l", "-", "-"], b"a b\nc\n")
    show("两个 - 加文件", ["-lwc", "-", "-", "twice.txt"], b"a b\nc\n")
    print()

    print("== 6. 同一文件给两次 ==")
    show("twice.txt twice.txt", ["-lwc", "twice.txt", "twice.txt"])
    print()

    print("== 7. 空与只含换行 ==")
    show("空文件 -lwcL", ["-lwcL", "adir/../nonexistent"])
    print()

    print("== 8. 无操作数读标准输入时的行 ==")
    show("stdin 默认", [], b"a b\nc\n")
    show("stdin -m", ["-m"], b"a b\nc\n")
    show("stdin -L", ["-L"], b"a b\nc\n")


if __name__ == "__main__":
    main()
