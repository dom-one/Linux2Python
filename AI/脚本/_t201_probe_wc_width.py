"""探针二：系统地实测 GNU wc 的列宽规则。

观察到的现象彼此冲突，需要靠矩阵来推规则：

- `wc a.txt`      -> b' 3  6 36 a.txt'   （3 列，宽 2）
- `wc -l a.txt`   -> b'3 a.txt'          （1 列，宽 1）
- `wc -l a b`     -> b' 3 a.txt\\n 0 b.txt\\n 3 total'  （1 列，宽 2）
- `wc -lwc a b e` -> b' 3  6 36 a.txt...' （3 列，宽 2）

所以列宽既不是「最大数字的位数」也不是固定值，逐组测出来再归纳。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc2"
TMP.mkdir(exist_ok=True)

# 各种规模的文件，用来改变数字的位数
SMALL = b"a b\nc\n"          # 1 行 / 3 词 / 7 字节
MID = b"a b\nc\n" * 10        # 10 行 / 30 词 / 70 字节
BIG = b"x" * 12345 + b"\n"   # 1 行 / 1 词 / 12346 字节


def setup() -> None:
    (TMP / "s.txt").write_bytes(SMALL)
    (TMP / "m.txt").write_bytes(MID)
    (TMP / "b.txt").write_bytes(BIG)
    (TMP / "e.txt").write_bytes(b"")


def wc(args, stdin_data=None, env=None):
    proc = subprocess.run(
        [WC] + args,
        cwd=str(TMP),
        input=stdin_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def show(label, args, stdin_data=None, env=None):
    code, out, err = wc(args, stdin_data, env)
    print(f"{label:38} rc={code} out={out!r}" + (f" err={err!r}" if err else ""))


def main() -> None:
    setup()

    print("== 1. 单文件，列数与数字位数 ==")
    show("单文件 1列 -l (1位)", ["-l", "s.txt"])
    show("单文件 1列 -l (2位)", ["-l", "m.txt"])
    show("单文件 1列 -l (5位)", ["-l", "b.txt"])
    show("单文件 1列 -c (1位)", ["-c", "s.txt"])
    show("单文件 1列 -c (2位)", ["-c", "m.txt"])
    show("单文件 1列 -c (5位)", ["-c", "b.txt"])
    show("单文件 2列 -lw (1位)", ["-lw", "s.txt"])
    show("单文件 2列 -lw (2位)", ["-lw", "m.txt"])
    show("单文件 3列 -lwc (1位)", ["-lwc", "s.txt"])
    show("单文件 3列 -lwc (2位)", ["-lwc", "m.txt"])
    show("单文件 4列 -lwcL (2位)", ["-lwcL", "m.txt"])
    print()

    print("== 2. 多文件，含 total 行 ==")
    show("2文件 1列 -l (1位)", ["-l", "s.txt", "e.txt"])
    show("2文件 1列 -l (2位)", ["-l", "m.txt", "e.txt"])
    show("2文件 1列 -l (5位)", ["-l", "b.txt", "e.txt"])
    show("2文件 3列 -lwc (1位)", ["-lwc", "s.txt", "e.txt"])
    show("2文件 3列 -lwc (2位)", ["-lwc", "m.txt", "e.txt"])
    show("3文件 3列 -lwc 混位", ["-lwc", "s.txt", "m.txt", "b.txt"])
    show("2文件 4列 -lwcL", ["-lwcL", "m.txt", "e.txt"])
    print()

    print("== 3. 标准输入 ==")
    show("仅stdin 1列 -l", ["-l"], b"a b\nc\n")
    show("仅stdin 3列 -lwc", ["-lwc"], b"a b\nc\n")
    show("仅stdin 3列 -lwc 大", ["-lwc"], b"x" * 12345 + b"\n")
    show("stdin+1文件 1列", ["-l", "-", "s.txt"], b"a b\nc\n")
    show("stdin+1文件 3列", ["-lwc", "-", "s.txt"], b"a b\nc\n")
    show("stdin+1文件 3列 大", ["-lwc", "-", "b.txt"], b"x" * 12345 + b"\n")
    show("仅stdin 无选项", [], b"a b\nc\n")
    show("仅stdin 无选项 大", [], b"x" * 12345 + b"\n")
    show("stdin 无选项 -c", ["-c"], b"a b\nc\n")
    show("stdin 无选项 -w", ["-w"], b"a b\nc\n")
    print()

    print("== 4. 文件名是否打印 ==")
    show("单文件 -lwc", ["-lwc", "m.txt"])
    show("单文件 -lwc --total=always", ["-lwc", "--total=always", "m.txt"])
    show("单文件 -lwc --total=never", ["-lwc", "--total=never", "m.txt"])
    show("多文件 -lwc --total=never", ["-lwc", "--total=never", "m.txt", "e.txt"])
    show("多文件 -lwc --total=always", ["-lwc", "--total=always", "m.txt", "e.txt"])
    print()

    print("== 5. 计数细节 ==")
    # 各种空白字符算不算词分隔
    (TMP / "ws.txt").write_bytes(b"a b\tc\rd\x0ce\x0cf\n")
    show("空白混合 -w", ["-w", "ws.txt"])
    show("空白混合 -l", ["-l", "ws.txt"])
    (TMP / "nl.txt").write_bytes(b"a\nb\n")
    show("结尾有换行 -l", ["-l", "nl.txt"])
    (TMP / "nonl.txt").write_bytes(b"a\nb")
    show("结尾无换行 -l", ["-l", "nonl.txt"])
    show("结尾无换行 -w", ["-w", "nonl.txt"])
    (TMP / "onlynl.txt").write_bytes(b"\n")
    show("只有换行 -lwc", ["-lwc", "onlynl.txt"])
    (TMP / "emptylines.txt").write_bytes(b"\n\n\n")
    show("三个空行 -lwc", ["-lwc", "emptylines.txt"])
    show("三个空行 -L", ["-L", "emptylines.txt"])
    (TMP / "utf8cjk.txt").write_bytes("中文测试\n第二行\n".encode("utf-8"))
    show("utf8 -c", ["-c", "utf8cjk.txt"])
    show("utf8 -m", ["-m", "utf8cjk.txt"])
    show("utf8 -L", ["-L", "utf8cjk.txt"])
    show("utf8 -w", ["-w", "utf8cjk.txt"])
    print()

    print("== 6. 错误路径 ==")
    show("不存在", ["-l", "nope.txt"])
    show("目录", ["-l", "."])
    show("混合", ["-l", "s.txt", "nope.txt", "e.txt"])
    print()

    print("== 7. locale 影响 -m / -L ==")
    import os

    env = dict(os.environ)
    for loc in ("C", "C.UTF-8", "en_US.UTF-8", "zh_CN.GBK"):
        e2 = dict(env)
        e2["LC_ALL"] = loc
        show(f"LC_ALL={loc} utf8 -m", ["-m", "utf8cjk.txt"], env=e2)
        show(f"LC_ALL={loc} utf8 -L", ["-L", "utf8cjk.txt"], env=e2)


if __name__ == "__main__":
    main()
