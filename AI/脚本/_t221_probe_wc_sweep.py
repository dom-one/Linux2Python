"""探针二十：扫描列宽 W 的规律（决定性）。

已定案（探针 16/18/19/20）：
- 普通文件：W = max(各文件字节数位数, 字节数之和位数)
  （99999+999999 → 7；9999999+1 → 8，即按「和」而不是按「各文件最大值」）
- 缺文件：不打印行、不计入 total、也不贡献宽度
- 目录：打印一行全 0、报错，贡献宽度下限 7
- 输出只有一个数字时（一个操作数 + 一列）完全不补空格

未解释：
- 管道 stdin：-l 单独 → W=1，-lw 两列 → W=7，-c 单独 → W=字节数位数
  「多列 + 非普通文件 → 7」这个说法还没验证，可能是：
  (a) 非普通文件贡献固定下限 7（与列数无关），但 -l 的实测 W=1 与之矛盾
  (b) 与列数有关（≥2 列时才有 7）
  (c) 与某一列的语义有关（比如词数）

本探针扫一遍：管道/普通文件 × 各种列组合 × 不同大小，
把每个输出的首个数字字段宽度算出来对照。
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc21"
TMP.mkdir(exist_ok=True)

COMBOS = [
    ["-l"],
    ["-w"],
    ["-m"],
    ["-c"],
    ["-L"],
    ["-lw"],
    ["-lc"],
    ["-wc"],
    ["-mc"],
    ["-lL"],
    ["-wL"],
    ["-mL"],
    ["-cL"],
    ["-lwc"],
    ["-lwmc"],
    ["-lwmcL"],
]


def setup() -> None:
    (TMP / "r4.txt").write_bytes(b"a b\n")
    (TMP / "r8.txt").write_bytes(b"a" * 12345678)
    (TMP / "r1.txt").write_bytes(b"a")


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


def widths(line: str) -> list[int]:
    """按数字串右边界推算每个数字字段的宽度。"""
    ends = [m.end() for m in re.finditer(r"\d+", line)]
    if len(ends) < 2:
        return [ends[0]] if ends else []
    out = []
    prev_end = 0
    for end in ends:
        out.append(end - prev_end - (1 if prev_end else 0))
        prev_end = end
    return out


def show(label, args, stdin_data=None):
    code, out, err = wc(args, stdin_data)
    lines = out.splitlines()
    parts = []
    for line in lines:
        parts.append(f"{line!r} w={widths(line)}")
    print(f"{label:38s} rc={code} " + " | ".join(parts))
    if err:
        print(f"{'':38s} err={err!r}")


def main() -> None:
    setup()

    print("== A. 管道 stdin，4 字节 ==")
    for combo in COMBOS:
        show("pipe " + "".join(combo), combo, b"a b\n")

    print()
    print("== B. 管道 stdin，12345678 字节 ==")
    for combo in COMBOS:
        show("pipe8 " + "".join(combo), combo, b"a" * 12345678)

    print()
    print("== C. 普通文件 r4.txt（4 字节） ==")
    for combo in COMBOS:
        show("r4 " + "".join(combo), combo + ["r4.txt"])

    print()
    print("== D. 普通文件 r8.txt（12345678 字节） ==")
    for combo in COMBOS:
        show("r8 " + "".join(combo), combo + ["r8.txt"])

    print()
    print("== E. 管道 stdin，多词（1000 词） ==")
    for combo in COMBOS:
        show("pipe1000 " + "".join(combo), combo, b"x " * 1000)

    print()
    print("== F. 管道 stdin + 普通文件 r4 ==")
    for combo in COMBOS:
        show("pipe+r4 " + "".join(combo), combo + ["-", "r4.txt"], b"a b\n")


if __name__ == "__main__":
    main()
