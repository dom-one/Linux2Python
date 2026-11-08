"""探针二十二：精确测每一列的宽度。

上一轮发现列宽不是统一的 W，而是逐列不同：
- 管道 stdin 的 行/词 两列宽度是 7（与内容大小无关）
- 管道 stdin 的 字符/字节 两列宽度随实际字节数变化（8 位字节 → 8）
- 普通文件的 行/词 列宽度等于该文件字节数的位数

要定案的：
- 普通文件的 行/词 列宽度 = 该文件字节数位数，还是「所有文件字节数之和」的位数
- total 行是否参与列宽（total 的字节数更大时会撑宽）
- stdin 的 7 是不是下限（stdin 内容 8 位时会不会变成 8）
- 目录贡献的 7 与 stdin 的 7 是不是同一个来源

测法：用不含数字的文件名（避免文件名里的数字干扰列宽解析），
按「数字右边界」推算每一列的字段宽度。
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc22"
TMP.mkdir(exist_ok=True)
(TMP / "adir").mkdir(exist_ok=True)


def setup() -> None:
    (TMP / "tiny.txt").write_bytes(b"a")
    (TMP / "nine.txt").write_bytes(b"a" * 9)
    (TMP / "ten.txt").write_bytes(b"a" * 10)
    (TMP / "hundred.txt").write_bytes(b"a" * 100)
    (TMP / "seven.txt").write_bytes(b"a" * 9999999)
    (TMP / "eight.txt").write_bytes(b"a" * 99999999)
    (TMP / "nine8.txt").write_bytes(b"a" * 999999999)


def wc(args, stdin_data=None):
    env = dict(os.environ)
    env["LC_ALL"] = "C.UTF-8"
    proc = subprocess.run(
        [WC] + args,
        cwd=str(TMP),
        input=stdin_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr


def col_widths(line: str) -> list[int]:
    """按数字右边界推算每列字段宽度（列间恰好一个空格）。"""
    ends = [m.end() for m in re.finditer(r"\d+", line)]
    if not ends:
        return []
    widths = [ends[0]]
    for prev, end in zip(ends, ends[1:]):
        widths.append(end - prev - 1)
    return widths


def show(label, args, stdin_data=None):
    code, out, err = wc(args, stdin_data)
    parts = []
    for line in out.splitlines():
        parts.append(f"{line!r} w={col_widths(line)}")
    print(f"{label:34s} rc={code} " + " | ".join(parts))
    if err:
        print(f"{'':34s} err={err!r}")


def main() -> None:
    setup()

    print("== 1. 单文件，各列宽度 ==")
    for name in ("tiny.txt", "nine.txt", "ten.txt", "hundred.txt", "seven.txt", "eight.txt", "nine8.txt"):
        show(f"{name} -lw", ["-lw", name])
        show(f"{name} -c", ["-c", name])
        show(f"{name} -lwmc", ["-lwmc", name])
    print()

    print("== 2. 两个文件：和是否撑宽 ==")
    show("nine+hundred -lw", ["-lw", "nine.txt", "hundred.txt"])
    show("nine+hundred -c", ["-c", "nine.txt", "hundred.txt"])
    show("hundred+hundred -lw", ["-lw", "hundred.txt", "hundred.txt"])
    print()

    print("== 3. total 行是否撑宽 ==")
    show("nine+hundred -lw（含 total）", ["-lw", "nine.txt", "hundred.txt"])
    show("nine+hundred -lw（只有 total 有大数）", ["-lw", "nine.txt", "nine.txt"])
    print()

    print("== 4. stdin 的 7 是不是下限 ==")
    show("stdin 4 字节 -lw", ["-lw", "-"], b"a b\n")
    show("stdin 8 位字节 -lw", ["-lw", "-"], b"a" * 99999999)
    show("stdin 9 位字节 -lw", ["-lw", "-"], b"a" * 999999999)
    show("stdin 8 位字节 -c", ["-c", "-"], b"a" * 99999999)
    print()

    print("== 5. 目录的 7 与 stdin 的 7 ==")
    show("adir -lw", ["-lw", "adir"])
    show("adir+tiny -lw", ["-lw", "adir", "tiny.txt"])
    show("adir+nine8 -lw", ["-lw", "adir", "nine8.txt"])
    show("stdin+nine8 -lw", ["-lw", "-", "nine8.txt"], b"a b\n")
    print()

    print("== 6. total 行里出现更大的数 ==")
    show("hundred+hundred -c", ["-c", "hundred.txt", "hundred.txt"])
    show("hundred+hundred -lw", ["-lw", "hundred.txt", "hundred.txt"])
    show("nine8+nine8 -lw", ["-lw", "nine8.txt", "nine8.txt"])
    show("nine8+nine8 -c", ["-c", "nine8.txt", "nine8.txt"])


if __name__ == "__main__":
    main()
