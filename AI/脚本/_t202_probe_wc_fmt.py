"""探针三：逐字符分析 GNU wc 的列宽与列序。

要回答四个问题：

1. 列宽 number_width 到底按什么算？（是「打印出来的数字的最大位数」，
   还是「所有统计量含未打印列的最大位数」？）
2. total 行是否参与列宽计算？
3. -L 列是否参与列宽计算？
4. -c 与 -m 同时给时的列序，以及 -m 是否顶替 -c 的位置？
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc3"
TMP.mkdir(exist_ok=True)

C = "C.UTF-8"


def setup() -> None:
    # 行数 1 位、词数 1 位、字节 5 位
    (TMP / "a.txt").write_bytes(b"x" * 12345 + b"\n")
    # 行数 3 位、词数 3 位、字节 3 位
    (TMP / "b.txt").write_bytes(b"a b\n" * 100)
    # 长行 20 字符
    (TMP / "c.txt").write_bytes(b"y" * 20 + b"\n")
    # utf8 中文
    (TMP / "u.txt").write_bytes("中文测试\n第二行\n".encode("utf-8"))
    (TMP / "e.txt").write_bytes(b"")


def wc(args, stdin_data=None, loc=C):
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


def widths(out: str) -> list[list[int]]:
    """把每行拆成字段，返回每行各字段的宽度。"""
    rows = []
    for line in out.splitlines():
        # 末字段是文件名（可能含空格），前面都是数字
        m = re.match(r"^((?:\s*\d+)*)\s*(\S.*)?$", line)
        if not m:
            rows.append([len(line)])
            continue
        nums = re.findall(r"\d+", m.group(1))
        # 用位置还原每个数字字段的宽度
        fields = []
        for num in nums:
            idx = line.index(num, 0)
            fields.append(idx + len(num))
        rows.append(fields)
    return rows


def show(label, args, stdin_data=None, loc=C):
    code, out, err = wc(args, stdin_data, loc)
    print(f"{label}")
    print(f"    args={args} out={out!r}")
    print(f"    行={out.splitlines()}")


def main() -> None:
    setup()

    print("== A. 只打印 -l，列宽是否受隐藏的字节列影响 ==")
    show("a.txt 只有字节是5位", ["-l", "a.txt"])
    show("b.txt 只有行/词是3位", ["-l", "b.txt"])
    show("a+b 都只打 -l", ["-l", "a.txt", "b.txt"])
    print()

    print("== B. total 行是否影响列宽 ==")
    # 造两个 999 行的文件，total = 1998（4位），单个都是 3 位
    (TMP / "p.txt").write_bytes(b"a\n" * 999)
    (TMP / "q.txt").write_bytes(b"b\n" * 999)
    show("两文件各999行 total=1998", ["-l", "p.txt", "q.txt"])
    show("两文件各999行 -lwc", ["-lwc", "p.txt", "q.txt"])
    print()

    print("== C. -L 是否影响列宽 ==")
    show("c.txt 长行20，只打 -l", ["-l", "c.txt"])
    show("c.txt 长行20，打 -lL", ["-lL", "c.txt"])
    show("c.txt 长行20，和 a.txt 一起只打 -l", ["-l", "c.txt", "a.txt"])
    print()

    print("== D. -c 与 -m 的列序（utf8 文件：23字节 / 9字符）==")
    show("u.txt -c", ["-c", "u.txt"])
    show("u.txt -m", ["-m", "u.txt"])
    show("u.txt -cm", ["-cm", "u.txt"])
    show("u.txt -mc", ["-mc", "u.txt"])
    show("u.txt -lwcm", ["-lwcm", "u.txt"])
    show("u.txt -lwmc", ["-lwmc", "u.txt"])
    show("u.txt 默认", ["u.txt"])
    show("u.txt -lm", ["-lm", "u.txt"])
    show("u.txt -lc", ["-lc", "u.txt"])
    print()

    print("== E. 标准输入的列宽 ==")
    show("stdin 3列 小", ["-lwc"], b"a b\nc\n")
    show("stdin 3列 大字节", ["-lwc"], b"x" * 12345 + b"\n")
    show("stdin 1列 -l", ["-l"], b"a b\nc\n")
    show("stdin 1列 -c", ["-c"], b"x" * 12345 + b"\n")
    show("stdin 1列 -c 小", ["-c"], b"ab\n")
    show("stdin 2列 -lw", ["-lw"], b"a b\nc\n")
    show("stdin 4列 -lwcL", ["-lwcL"], b"a b\nc\n")
    show("stdin+文件 1列", ["-l", "-", "a.txt"], b"q\n")
    show("stdin+文件 3列", ["-lwc", "-", "a.txt"], b"q\n")
    print()

    print("== F. 目录操作数的细节 ==")
    show("目录", ["-l", "."])
    show("目录+文件", ["-l", ".", "a.txt"])
    show("目录+文件 -lwc", ["-lwc", ".", "a.txt"])
    print()

    print("== G. --files0-from ==")
    show("files0", ["--files0-from=-"], b"a.txt\x00b.txt\x00")
    show("files0 -l", ["-l", "--files0-from=-"], b"a.txt\x00b.txt\x00")


if __name__ == "__main__":
    main()
