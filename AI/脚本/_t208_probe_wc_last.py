"""探针九：钉死最后几处判据。

已归纳：
- 列序固定：行数 → 词数 → 字符数(-m) → 字节数(-c) → 最长行(-L)
- 不给选项时默认 行/词/字节；给了就只打印给的
- 一个操作数 + 一列时数字不补空格；否则补到统一宽度
- -L 算显示宽度：制表符推进到 8 的倍数，\\r 视为回车，组合字符宽度 0

悬案：
1. 目录那一行为什么把宽度撑到 7？（缺文件不会）
2. 标准输入参与时宽度为什么固定 7？
3. CRLF 的 -L 怎么算
4. -m 对非法 UTF-8 字节怎么算
5. 行分隔符与数字之间的确切空格数
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WC = r"E:\software\Git\Git\usr\bin\wc.exe"
HERE = Path(__file__).resolve().parent
TMP = HERE / "_data_wc9"
TMP.mkdir(exist_ok=True)
(TMP / "adir").mkdir(exist_ok=True)
(TMP / "locked").write_bytes(b"secret\n")
(TMP / "crlf.txt").write_bytes(b"a\r\nbb\r\n")
(TMP / "cr3.txt").write_bytes(b"abc\rdef\r\n")
(TMP / "tab2.txt").write_bytes(b"ab\tc\n")
(TMP / "tab3.txt").write_bytes(b"abcdefgh\tz\n")
(TMP / "one.txt").write_bytes(b"x\n")
(TMP / "gbk.txt").write_bytes("中文测试\n第二行\n".encode("gb18030"))
(TMP / "bad.txt").write_bytes(b"a\xffb\n")


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
    setup_ = None  # noqa: F841
    print("== 1. 目录撑宽度 ==")
    show("目录单独 -lwc", ["-lwc", "adir"])
    show("目录单独 -l", ["-l", "adir"])
    show("目录 + 文件 -lwc", ["-lwc", "adir", "one.txt"])
    show("文件 + 目录 -lwc", ["-lwc", "one.txt", "adir"])
    show("两个目录 -lwc", ["-lwc", "adir", "adir"])
    show("三个目录 -lwc", ["-lwc", "adir", "adir", "adir"])
    print()

    print("== 2. 标准输入的宽度 ==")
    show("stdin 2列 小", ["-lw"], b"a\n")
    show("stdin 2列 6字节", ["-lw"], b"a b\nc\n")
    show("stdin 2列 100字节", ["-lw"], b"x" * 100)
    show("stdin 4列", ["-lwcL"], b"a\n")
    show("stdin 单列", ["-l"], b"a\n")
    show("stdin + 目录 -lwc", ["-lwc", "-", "adir"], b"a\n")
    show("stdin + 缺文件 -lwc", ["-lwc", "-", "nope.txt"], b"a\n")
    print()

    print("== 3. CRLF 与 \\r ==")
    show("crlf.txt -L", ["-L", "crlf.txt"])
    show("crlf.txt -lwc", ["-lwc", "crlf.txt"])
    show("crlf.txt -m", ["-m", "crlf.txt"])
    show("cr3.txt -L", ["-L", "cr3.txt"])
    print()

    print("== 4. 制表位 ==")
    show("tab2.txt (ab\\tc) -L", ["-L", "tab2.txt"])
    show("tab3.txt (abcdefgh\\tz) -L", ["-L", "tab3.txt"])
    print()

    print("== 5. -m 对非法字节 ==")
    show("gbk.txt -m C.UTF-8", ["-m", "gbk.txt"])
    show("gbk.txt -c", ["-c", "gbk.txt"])
    show("bad.txt -m C.UTF-8", ["-m", "bad.txt"])
    show("bad.txt -c", ["-c", "bad.txt"])
    print()

    print("== 6. 确切字节格式 ==")
    code, out, err = wc(["-lwc", "one.txt"])
    print(f"    单文件多列 bytes={out!r}")
    code, out, err = wc(["-lwc", "one.txt", "one.txt"])
    print(f"    多文件 bytes={out!r}")
    code, out, err = wc(["-l", "one.txt"])
    print(f"    单文件单列 bytes={out!r}")
    code, out, err = wc(["-l", "-"], b"a\n")
    print(f"    stdin 单列 bytes={out!r}")
    code, out, err = wc(["-lwc"], b"a\n")
    print(f"    stdin 无名多列 bytes={out!r}")


if __name__ == "__main__":
    main()
