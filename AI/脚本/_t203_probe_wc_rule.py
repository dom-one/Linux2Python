"""探针四：把 GNU wc 的列宽规则彻底钉死，并程序化解析字段位置。

已归纳出的候选规则（来自探针二、三）：

- 输出列的顺序固定为：行数 → 词数 → 字符数(-m) → 字节数(-c) → 最长行(-L)
- 只给 -m 时，字符数列顶替默认的字节数列
- 单文件模式：行数 = 1、词数 = 1、字符数 = 1、字节数 = 1、最长行 = 1
- 多文件模式：行数 = 2、词数 = 2、字符数 = 2、字节数 = 2、最长行 = 2
- 多文件时多打一行 total

还有三处没定：

1. 单文件多列时，列宽是否含「没被打印的列」？（u.txt -lm 得到宽度 2，
   而打印出来的只有 2 和 9，1 位就够，说明宽度含隐藏的字节列 23）
2. 标准输入出现时，宽度是不是固定 7？
3. -L（最长行）算的是字符数还是显示宽度？

这一轮用程序解析字段起止位置，不再靠肉眼数空格。
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc4"
TMP.mkdir(exist_ok=True)


def setup() -> None:
    (TMP / "big.txt").write_bytes(b"x" * 12345 + b"\n")     # 1 行 1 词 12346 字节
    (TMP / "mid.txt").write_bytes(b"a b\n" * 100)             # 100 行 200 词 400 字节
    (TMP / "cjk.txt").write_bytes("中文测试\n第二行\n".encode("utf-8"))
    (TMP / "mix.txt").write_bytes("abc中文\n".encode("utf-8"))
    (TMP / "empty.txt").write_bytes(b"")


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


def parse(out: str):
    """把输出每行解析成 [(start, end, text)] 的数字字段 + 尾部名字。"""
    rows = []
    for line in out.splitlines():
        fields = [(m.start(), m.end(), m.group()) for m in re.finditer(r"\d+", line)]
        rows.append((line, fields))
    return rows


def widths_of(out: str) -> list[list[int]]:
    """每行每个数字字段的右边界（列对齐位置）。"""
    res = []
    for line, fields in parse(out):
        res.append([end for _, end, _ in fields])
    return res


def show(label, args, stdin_data=None, loc="C.UTF-8"):
    code, out, err = wc(args, stdin_data, loc)
    print(f"{label}")
    print(f"    args={args!r} rc={code}")
    for line, fields in parse(out):
        print(f"    | {line!r}  数字右边界={[e for _, e, _ in fields]}")
    if err:
        print(f"    err={err!r}")


def main() -> None:
    setup()

    print("== 1. 单文件多列：宽度是否含隐藏列 ==")
    show("big.txt 只打 -l（字节 5 位）", ["-l", "big.txt"])
    show("big.txt 打 -lw（词 1 位，字节 5 位）", ["-lw", "big.txt"])
    show("big.txt 打 -lwc", ["-lwc", "big.txt"])
    show("mid.txt 只打 -l", ["-l", "mid.txt"])
    show("mid.txt 打 -lw", ["-lw", "mid.txt"])
    show("cjk.txt 打 -lm（字符 9，字节 23）", ["-lm", "cjk.txt"])
    show("cjk.txt 打 -lw（词 2，字符 9，字节 23）", ["-lw", "cjk.txt"])
    print()

    print("== 2. 多文件：宽度含 total 与隐藏列 ==")
    show("big+mid 只打 -l", ["-l", "big.txt", "mid.txt"])
    show("big+mid 打 -lw", ["-lw", "big.txt", "mid.txt"])
    show("empty+empty 只打 -l", ["-l", "empty.txt", "empty.txt"])
    print()

    print("== 3. 标准输入的宽度 ==")
    show("stdin 3列", ["-lwc"], b"a b\nc\n")
    show("stdin + big.txt 3列", ["-lwc", "-", "big.txt"], b"q\n")
    (TMP / "huge.txt").write_bytes(b"x" * 12345678)
    show("stdin + huge.txt(8位) 3列", ["-lwc", "-", "huge.txt"], b"q\n")
    show("huge.txt 单文件 -c", ["-c", "huge.txt"])
    show("stdin 单文件 -c 8位", ["-c"], b"x" * 12345678)
    show("huge.txt + mid.txt -l", ["-l", "huge.txt", "mid.txt"])
    print()

    print("== 4. -L 到底怎么算 ==")
    show("mix.txt -L (abc中文)", ["-L", "mix.txt"])
    show("mix.txt -Lc", ["-Lc", "mix.txt"])
    show("mix.txt -Lm", ["-Lm", "mix.txt"])
    show("mix.txt -L C locale", ["-L", "mix.txt"], loc="C")
    show("cjk.txt -L", ["-L", "cjk.txt"])
    show("cjk.txt -L C locale", ["-L", "cjk.txt"], loc="C")
    show("ascii 长行 -L", ["-L", "big.txt"])
    print()

    print("== 5. 字符数 -m 的 locale 行为 ==")
    (TMP / "gbk.txt").write_bytes("中文测试\n第二行\n".encode("gb18030"))
    show("gbk -m C locale", ["-m", "gbk.txt"], loc="C")
    show("gbk -m C.UTF-8", ["-m", "gbk.txt"])
    show("gbk -c", ["-c", "gbk.txt"])
    show("gbk -w", ["-w", "gbk.txt"])
    print()

    print("== 6. 词与行的边界 ==")
    (TMP / "ws.txt").write_bytes(b"a b\tc\rd\x0be\x0cf\n")
    show("混合空白 -w", ["-w", "ws.txt"])
    show("混合空白 -l", ["-l", "ws.txt"])
    show("只有空白", ["-lwc", "ws.txt"])
    (TMP / "nonl.txt").write_bytes(b"a\nb")
    show("末行无换行 -lwc", ["-lwc", "nonl.txt"])
    (TMP / "crlf.txt").write_bytes(b"a\r\nb\r\n")
    show("CRLF -lwc", ["-lwc", "crlf.txt"])
    show("CRLF -w", ["-w", "crlf.txt"])
    show("CRLF -L", ["-L", "crlf.txt"])
    print()

    print("== 7. 字段右边界汇总（宽度规则）==")
    for label, args, data in [
        ("单文件 -lwc", ["-lwc", "mid.txt"], None),
        ("多文件 -lwc", ["-lwc", "mid.txt", "empty.txt"], None),
        ("stdin -lwc", ["-lwc"], b"a b\nc\n"),
    ]:
        code, out, err = wc(args, data)
        print(f"    {label}: {widths_of(out)}")


if __name__ == "__main__":
    main()
