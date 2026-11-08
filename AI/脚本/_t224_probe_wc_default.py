"""探针二十四：最后一个判别项 + 默认列确认。

待判：
- 非普通文件（管道 stdin、目录）到底是「给宽度下限 7」还是「贡献一个 7 位数」
  pipe + 7 位文件：下限模型 → W=7；贡献模型 → 9999999 + 1000000 = 10999999 → W=8
  pipe + 8 位文件：下限模型 → W=8；贡献模型 → 99999999 + 1000000 = 100999999 → W=9
- 不给任何选项时默认打印哪几列
- 标准输入重定向自普通文件时，它的大小是否计入宽度
- 目录 + 缺文件时宽度怎么算
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc24"
TMP.mkdir(exist_ok=True)
(TMP / "adir").mkdir(exist_ok=True)


def setup() -> None:
    (TMP / "seven.txt").write_bytes(b"a" * 9999999)
    (TMP / "eight.txt").write_bytes(b"a" * 99999999)
    (TMP / "tiny.txt").write_bytes(b"x")
    (TMP / "text.txt").write_bytes(b"one\ntwo\n")


def wc(args, stdin_data=None, stdin_file=None):
    env = dict(os.environ)
    env["LC_ALL"] = "C.UTF-8"
    kwargs = {}
    if stdin_file is not None:
        with open(str(stdin_file), "rb") as handle:
            proc = subprocess.run(
                [WC] + args,
                cwd=str(TMP),
                stdin=handle,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
        return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr
    proc = subprocess.run(
        [WC] + args,
        cwd=str(TMP),
        input=stdin_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr


def show(label, args, stdin_data=None, stdin_file=None):
    code, out, err = wc(args, stdin_data, stdin_file)
    print(f"{label}")
    print(f"    args={args!r} rc={code}")
    for line in out.splitlines():
        print(f"    | {line!r}")
    if err:
        print(f"    err={err!r}")


def main() -> None:
    setup()

    print("== 1. 非普通文件：下限 7 还是贡献 7 位数 ==")
    show("pipe + seven(7 位) -lw → 下限=7 贡献=8", ["-lw", "-", "seven.txt"], b"x\n")
    show("pipe + eight(8 位) -lw → 下限=8 贡献=9", ["-lw", "-", "eight.txt"], b"x\n")
    show("dir + seven -lw → 下限=7 贡献=8", ["-lw", "adir", "seven.txt"])
    show("dir + eight -lw → 下限=8 贡献=9", ["-lw", "adir", "eight.txt"])
    print()

    print("== 2. 默认列 ==")
    show("不给选项（普通文件）", ["text.txt"])
    show("不给选项（stdin）", [], b"one\ntwo\n")
    print()

    print("== 3. stdin 重定向自普通文件时的大小 ==")
    show("stdin<eight + seven -lw", ["-lw", "seven.txt"], stdin_file=TMP / "eight.txt")
    show("stdin<tiny + seven -lw", ["-lw", "seven.txt"], stdin_file=TMP / "tiny.txt")
    print()

    print("== 4. 目录 + 缺文件 ==")
    show("dir + 缺 -lw", ["-lw", "adir", "nope.txt"])
    show("缺 + 缺 -lw", ["-lw", "nope.txt", "nope2.txt"])
    print()

    print("== 5. 空文件 ==")
    (TMP / "empty.txt").write_bytes(b"")
    show("empty -lw", ["-lw", "empty.txt"])
    show("empty + seven -lw", ["-lw", "empty.txt", "seven.txt"])


if __name__ == "__main__":
    main()
