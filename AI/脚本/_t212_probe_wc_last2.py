"""探针十二：最后几处判据。

已归纳的完整模型：
- 列序固定：行数(-l) → 词数(-w) → 字符数(-m) → 字节数(-c) → 最长行(-L)
- 不给任何选项时默认打印 行/词/字节；给了就只打印给的（-m 与 -c 可并存，
  字符数列排在字节数列前面）
- 整个输出只有一个数字时（一个操作数 + 一列）不补空格
- 其余情况所有列右对齐到统一宽度 W，列间一个空格，末列后一个空格接文件名
- W = max(已知文件与 total 的全部统计量的位数)，标准输入或目录参与时 W 至少 7
- total 行只在操作数 ≥ 2 时出现；缺文件不打印行只报错；目录打印全 0 行但不计入 total

这一轮确认：
1. 两个操作数（其中一个缺）+ 一列时补不补空格
2. -L 的 \\r 语义：\\r 之后的列宽算不算进本行最大宽度
3. -L 的制表符宽度（只含制表符的行）
4. -L 的全角字符宽度
5. -L 与行尾空白的关系
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc12"
TMP.mkdir(exist_ok=True)


def setup() -> None:
    (TMP / "one.txt").write_bytes(b"x\n")
    (TMP / "big.txt").write_bytes(b"x" * 999998 + b"\n")
    # \r 之后还有内容：最大宽度算不算前面那段
    (TMP / "cr.rst").write_bytes(b"abcdefgh\rz\n")
    (TMP / "cr2.rst").write_bytes(b"ab\rcd\n")
    # 只含制表符
    (TMP / "tab.rst").write_bytes(b"\t\n")
    (TMP / "tab2.rst").write_bytes(b"\t\t\n")
    # 全角字符
    (TMP / "wide.rst").write_bytes("漢字\n".encode("utf-8"))
    (TMP / "wide2.rst").write_bytes("漢字テスト\n".encode("utf-8"))
    # 行尾空格
    (TMP / "sp.rst").write_bytes(b"ab   \ncd\n")
    # 只有换行
    (TMP / "nl.rst").write_bytes(b"\n\n\n")
    # 空文件
    (TMP / "e.rst").write_bytes(b"")


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

    print("== 1. 两操作数（一个缺）+ 一列 ==")
    show("缺 + 文件 -l", ["-l", "nope.txt", "one.txt"])
    show("文件 + 缺 -l", ["-l", "one.txt", "nope.txt"])
    show("缺 + 大文件 -l", ["-l", "nope.txt", "big.txt"])
    show("缺 + 缺 -l", ["-l", "nope.txt", "nope2.txt"])
    show("单文件 -l", ["-l", "one.txt"])
    print()

    print("== 2. -L 的 \\r 语义 ==")
    show("cr.rst (abcdefgh\\rz) -L", ["-L", "cr.rst"])
    show("cr2.rst (ab\\rcd) -L", ["-L", "cr2.rst"])
    print()

    print("== 3. -L 的制表符 ==")
    show("tab.rst (\\t) -L", ["-L", "tab.rst"])
    show("tab2.rst (\\t\\t) -L", ["-L", "tab2.rst"])
    print()

    print("== 4. -L 的全角字符 ==")
    show("wide.rst (漢字) -L", ["-L", "wide.rst"])
    show("wide2.rst (漢字テスト) -L", ["-L", "wide2.rst"])
    show("wide.rst C locale -L", ["-L", "wide.rst"], loc="C")
    print()

    print("== 5. 行尾空格与空行 ==")
    show("sp.rst (ab   /cd) -L", ["-L", "sp.rst"])
    show("nl.rst (三个换行) -lwcL", ["-lwcL", "nl.rst"])
    show("e.rst (空) -lwcL", ["-lwcL", "e.rst"])
    print()

    print("== 6. 词数与空白 ==")
    show("sp.rst -lw", ["-lw", "sp.rst"])
    show("nl.rst -lw", ["-lw", "nl.rst"])


if __name__ == "__main__":
    main()
