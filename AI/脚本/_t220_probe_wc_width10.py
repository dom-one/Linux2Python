"""探针十九：定案列宽 W 的兜底规则与几处收尾行为。

已知（探针 16/18）：
- 99999 + 999999 → W=7（max 只会给 6）⇒ W 不是「各文件位数的最大值」
- 9999999 + 1 → W=8（和=10000000，位数 8）⇒ W 与「字节数之和」有关
- 目录 + 1 字节文件 → W=7；缺文件 + 1 字节文件 → W=1

待判：
- 管道 stdin（大小事先未知）是否固定贡献 7（探针 18 只看了 2 字节的情况）
- 「和」与「7」如何叠加：dir + a7 + b1 的和是 10000000（8 位），若 W=8 说明
  是 max(和的位数, 7)；若 W=9 说明是「和再加 7」
- 两个都缺文件时 total 行打不打
- 单个 `-` 操作数 + 单列是否也不补空格
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc19"
TMP.mkdir(exist_ok=True)
(TMP / "adir").mkdir(exist_ok=True)


def setup() -> None:
    (TMP / "a7.txt").write_bytes(b"a" * 9999999)
    (TMP / "b1.txt").write_bytes(b"b")
    (TMP / "s1.txt").write_bytes(b"x")


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

    print("== 0. 操作系统看到的目录大小 ==")
    st = os.stat(str(TMP / "adir"))
    print(f"    adir st_size={st.st_size}")
    print(f"    a7 st_size={os.stat(str(TMP / 'a7.txt')).st_size}")
    print()

    print("== 1. 管道 stdin 的宽度兜底 ==")
    show("stdin 管道 8 位字节 -c", ["-c", "-"], b"c" * 12345678)
    show("stdin 管道 9 位字节 -c", ["-c", "-"], b"c" * 999999999)
    show("stdin 管道 1 位字节 -c", ["-c", "-"], b"c")
    show("stdin 管道 2 位字节 -lw", ["-lw", "-"], b"a b\n")
    print()

    print("== 2. 「和」与「7」如何叠加 ==")
    show("dir + a7 + b1 -lw（和=10000000，8 位）", ["-lw", "adir", "a7.txt", "b1.txt"])
    show("stdin + a7 + b1 -lw", ["-lw", "-", "a7.txt", "b1.txt"], b"x\n")
    show("a7 + b1 -lw（无未知项）", ["-lw", "a7.txt", "b1.txt"])
    print()

    print("== 3. 全缺文件时 total 行 ==")
    show("两个都缺", ["-lw", "nope1.txt", "nope2.txt"])
    show("缺 + 目录", ["-lw", "nope.txt", "adir"])
    print()

    print("== 4. 单个 - 操作数 + 单列 ==")
    show("stdin -l", ["-l", "-"], b"a b\n")
    show("stdin -lw", ["-lw", "-"], b"a b\n")
    print()

    print("== 5. 文件名列的规则 ==")
    show("无操作数（纯 stdin）", ["-lw"], b"a b\n")
    show("单个 -", ["-lw", "-"], b"a b\n")
    show("s1 单独", ["-lw", "s1.txt"])


if __name__ == "__main__":
    main()
