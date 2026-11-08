"""探针十八：定案列宽 W 的算法，并补齐边角行为。

待判定的核心：W 到底是
  (A) max(各普通文件字节数位数)
  (B) 各普通文件字节数之和的位数
  (C) total 行字节数的位数（含 stdin 字节）
「9999999 字节 + 1 字节」这一组三者分道扬镳：A → 7，B → 8（和=10000000），C → 8。
已知「99999 + 999999」实测 W=7（max 只会给 6），所以 A 已被排除。

另需定案：
- 目录、缺文件、stdin 各自对 W 的贡献
- 重复 `-` 操作数第二行打印什么
- total 的 -m 是各文件之和吗、-L 是最大值吗
- 非法选项的退出码与报错文字
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc18"
TMP.mkdir(exist_ok=True)
(TMP / "adir").mkdir(exist_ok=True)


def setup() -> None:
    (TMP / "a7.txt").write_bytes(b"a" * 9999999)
    (TMP / "b1.txt").write_bytes(b"b")
    (TMP / "s1.txt").write_bytes(b"x")
    (TMP / "u8.txt").write_bytes("中文\n".encode("utf-8"))
    (TMP / "u8b.txt").write_bytes("中文\n".encode("utf-8"))
    (TMP / "tabs.txt").write_bytes(b"\t\t")
    (TMP / "big.txt").write_bytes(b"c" * 12345678)


def wc(args, stdin_data=None, loc="C.UTF-8", stdin_file=None):
    env = dict(os.environ)
    env["LC_ALL"] = loc
    kwargs = {}
    if stdin_file is not None:
        with open(str(stdin_file), "rb") as handle:
            kwargs["stdin"] = handle
            proc = subprocess.run(
                [WC] + args,
                cwd=str(TMP),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                **kwargs,
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


def show(label, args, stdin_data=None, loc="C.UTF-8", stdin_file=None):
    code, out, err = wc(args, stdin_data, loc, stdin_file)
    print(f"{label}")
    print(f"    args={args!r} rc={code}")
    for line in out.splitlines():
        edges = [m.end() for m in re.finditer(r"\d+", line)]
        print(f"    | {line!r}  右边界={edges}")
    if err:
        print(f"    err={err!r}")


def main() -> None:
    setup()

    print("== 1. W：max 还是 和 ==")
    show("a7(9999999) + b1(1) -lw → A=7 B=8", ["-lw", "a7.txt", "b1.txt"])
    show("a7 + a7 -lw → A=7 B=8", ["-lw", "a7.txt", "a7.txt"])
    print()

    print("== 2. 目录 / 缺文件 / stdin 各自对 W 的贡献 ==")
    show("adir 单独 -lw", ["-lw", "adir"])
    show("adir + s1 -lw", ["-lw", "adir", "s1.txt"])
    show("missing + s1 -lw", ["-lw", "nope.txt", "s1.txt"])
    show("missing 单独", ["-lw", "nope.txt"])
    print()

    print("== 3. 标准输入 ==")
    show("stdin 管道 -lw（2 字节）", ["-lw", "-"], b"a b\n")
    show("stdin 管道 -c（8 位字节）", ["-c", "-"], b"c" * 12345678)
    show("stdin < s1（普通文件，1 字节）", ["-lw"], stdin_file=TMP / "s1.txt")
    show("stdin < big（普通文件，8 位字节）", ["-lw"], stdin_file=TMP / "big.txt")
    print()

    print("== 4. 重复 - 操作数 ==")
    show("两个 -", ["-lw", "-", "-"], b"a b\n")
    print()

    print("== 5. total 的 -m 与 -L ==")
    show("u8 + u8b -m", ["-m", "u8.txt", "u8b.txt"])
    show("u8 + u8b -L", ["-L", "u8.txt", "u8b.txt"])
    show("u8 + u8b -mcL", ["-mcL", "u8.txt", "u8b.txt"])
    print()

    print("== 6. -L 值超出字节数位数时 ==")
    show("tabs(2 字节, tab 展开 16) -L", ["-L", "tabs.txt"])
    show("tabs -cL", ["-cL", "tabs.txt"])
    print()

    print("== 7. 非法选项 ==")
    show("非法选项 -Z", ["-Z", "s1.txt"])
    show("不存在的选项 --bogus", ["--bogus", "s1.txt"])


if __name__ == "__main__":
    main()
