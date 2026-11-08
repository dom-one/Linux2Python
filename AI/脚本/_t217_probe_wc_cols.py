"""探针十七：-L / -m 列的格式与列宽。

要弄清的：
- -L 列是否与其它列共用同一个宽度 W
- -L 单独一列时（单文件单列）是否也不补空格
- -m 与 -c 同开时的排列与各自宽度
- total 行的 -L 是最大值还是别的
- -L 的显示宽度语义（tab 展开、\\r 回车、CJK 全角 2）
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc17"
TMP.mkdir(exist_ok=True)


def setup() -> None:
    (TMP / "a.txt").write_bytes(b"abc\ndef\n")
    (TMP / "b.txt").write_bytes(b"x" * 30 + b"\n")
    (TMP / "wide.txt").write_bytes("中文测试\n第二行\n".encode("utf-8"))
    (TMP / "tab.txt").write_bytes(b"a\tb\tc\n")
    (TMP / "cr.txt").write_bytes(b"abcdefgh\rz\n")


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

    print("== 1. -L 列与其它列的宽度关系 ==")
    show("a.txt -lL（a.txt 4 字节，-L 值 3）", ["-lL", "a.txt"])
    show("b.txt -lL（b.txt 31 字节，-L 值 30）", ["-lL", "b.txt"])
    show("b.txt -L（单文件单列）", ["-L", "b.txt"])
    show("b.txt -cL", ["-cL", "b.txt"])
    print()

    print("== 2. -L 的 total 行 ==")
    show("a.txt b.txt -L", ["-L", "a.txt", "b.txt"])
    show("a.txt b.txt -lL", ["-lL", "a.txt", "b.txt"])
    print()

    print("== 3. -m 与 -c ==")
    show("wide.txt -m", ["-m", "wide.txt"])
    show("wide.txt -mc", ["-mc", "wide.txt"])
    show("wide.txt -cm", ["-cm", "wide.txt"])
    show("wide.txt -lwmcL", ["-lwmcL", "wide.txt"])
    print()

    print("== 4. -L 显示宽度语义复核 ==")
    show("wide.txt -L", ["-L", "wide.txt"])
    show("tab.txt -L", ["-L", "tab.txt"])
    show("cr.txt -L", ["-L", "cr.txt"])
    print()

    print("== 5. -m 在 C locale 下 ==")
    show("wide.txt -m (C locale)", ["-m", "wide.txt"], loc="C")


if __name__ == "__main__":
    main()
