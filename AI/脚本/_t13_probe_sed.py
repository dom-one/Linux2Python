#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测 Git Bash 里 GNU sed 4.9 的行为基线，产出可读的对照报告。

用法：python AI/脚本/_t13_probe_sed.py
产物：AI/数据/sed_probe.txt
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "sed_probe.txt"

FIXTURE = b"alpha\nbravo\ncharlie\ndelta\necho\n"
NUMFIX = b"1 one\n2 two\n3 three\n4 four\n5 five\n"
NONL = b"no trailing newline"


def find_sed() -> str | None:
    found = shutil.which("sed")
    if found:
        return found
    for candidate in (
        r"C:\Program Files\Git\usr\bin\sed.exe",
        r"C:\Program Files (x86)\Git\usr\bin\sed.exe",
    ):
        if Path(candidate).exists():
            return candidate
    return None


def show(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    if raw and any(byte > 127 for byte in raw):
        return f"{text!r} | raw={raw!r}"
    return repr(text)


def main() -> int:
    sed = find_sed()
    if not sed:
        print("[result] 找不到 sed 可执行文件")
        return 1
    print(f"[result] 使用 sed: {sed}")

    lines: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="sedprobe_"))
    (tmp / "a.txt").write_bytes(FIXTURE)
    (tmp / "num.txt").write_bytes(NUMFIX)
    (tmp / "nonl.txt").write_bytes(NONL)
    (tmp / "s.txt").write_bytes(b"s1\ns2\n")
    (tmp / "script.sed").write_bytes(b"s/a/b/\n")

    def case(name: str, argv: list[str], stdin: bytes = b"", show_stdin: bool = False) -> None:
        proc = subprocess.run(
            [sed, *argv],
            input=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(tmp),
        )
        head = f"$ sed {' '.join(argv)}"
        if show_stdin:
            head += f"   <<< {stdin!r}"
        lines.append(f"### {name}")
        lines.append(head)
        lines.append(f"exit={proc.returncode}")
        lines.append(f"out={show(proc.stdout)}")
        lines.append(f"err={show(proc.stderr)}")
        lines.append("")

    # ---- 基本替换 ----
    case("基本替换-只换第一个", ["s/a/b/"], FIXTURE)
    case("基本替换-g", ["s/a/b/g"], FIXTURE)
    case("基本替换-第N个", ["s/a/b/2"], b"aaa aaa aaa\n")
    case("基本替换-第0个(整行)", ["s/a/b/0"], b"aaa aaa aaa\n")
    case("基本替换-忽略大小写", ["s/A/B/gI"], b"AaA aAa\n")
    case("基本替换-加p标志", ["s/a/b/p"], FIXTURE)
    case("基本替换-反斜杠引用", [r"s/(a)(b)/\2\1/"], b"ab\n")
    case("基本替换-整行引用&", ["s/a/&b/"], b"cat\n")
    case("基本替换-大写\\U", [r"s/a/\Uab/"], b"cat\n")
    case("基本替换-小写\\L", [r"s/A/\Lab/"], b"CAT\n")
    case("基本替换-多命令分号", ["s/a/b/;s/b/c/"], FIXTURE)
    case("基本替换-换行分隔", ["s/a/b/\ns/b/c/"], FIXTURE)

    # ---- 分隔符 ----
    case("分隔符-竖线", ["s|a|b|"], FIXTURE)
    case("分隔符-井号", ["s#a#b#"], FIXTURE)
    case("分隔符-逗号", ["s,a,b,"], FIXTURE)
    case("分隔符-转义", [r"s/a\/b/c/"], b"a/b\n")

    # ---- -n 与选择命令 ----
    case("安静模式-p", ["-n", "p"], FIXTURE)
    case("安静模式-2p", ["-n", "2p"], FIXTURE)
    case("安静模式-正则p", ["-n", "/bravo/p"], FIXTURE)
    case("安静模式-空输入退出码", ["-n", "p"], b"")
    case("安静模式-无匹配退出码", ["-n", "/zzz/p"], FIXTURE)
    case("删除-d", ["/bravo/d"], FIXTURE)
    case("删除-行号", ["2d"], FIXTURE)

    # ---- q / Q / = ----
    case("退出-q", ["2q"], FIXTURE)
    case("退出-q带退出码", ["q 3"], FIXTURE)
    case("退出-Q", ["2Q"], FIXTURE)
    case("行号-=", ["-n", "=;p"], FIXTURE)

    # ---- y / a / i / c ----
    case("转写-y", ["y/abc/xyz/"], b"abcabc\n")
    case("追加-a反斜杠形式", ["1a\\inserted"], FIXTURE)
    case("追加-a单行形式", ["1a inserted"], FIXTURE)
    case("插入-i反斜杠形式", ["1i\\inserted"], FIXTURE)
    case("插入-i单行形式", ["1i inserted"], FIXTURE)
    case("替换-c反斜杠形式", ["1c\\changed"], FIXTURE)
    case("替换-c单行形式", ["1c changed"], FIXTURE)

    # ---- n / N ----
    case("下一行-n", ["-n", "n;p"], FIXTURE)
    case("下一行-N", ["-n", "N;p"], FIXTURE)
    case("下一行-N配p标志", ["-n", "N;$!d;p"], FIXTURE)

    # ---- 地址形式 ----
    case("地址-最后一行", ["-n", "$p"], FIXTURE)
    case("地址-范围", ["-n", "2,3p"], FIXTURE)
    case("地址-正则范围", ["-n", "/bravo/,/charlie/p"], FIXTURE)
    case("地址-逗号加号", ["-n", "2,+2p"], FIXTURE)
    case("地址-波浪步长", ["-n", "1~2p"], FIXTURE)
    case("地址-0到正则", ["-n", "0,/bravo/p"], FIXTURE)
    case("地址-正则加地址", ["-n", "/bravo/,4p"], FIXTURE)
    case("地址-反斜杠正则", ["-n", r"\bravo\p"], FIXTURE)
    case("地址-未匹配范围", ["-n", "/zzz/,/yyy/p"], FIXTURE)

    # ---- 分支与标签 ----
    case("分支-b与标签", ["-n", ":a;N;$!ba;s/\\n/-/;p"], FIXTURE)
    case("分支-t", ["-n", "/bravo/{s/a/X/;t end};p;:end"], FIXTURE)

    # ---- 多文件与 -s ----
    case("多文件-默认拼接", ["s/s/S/"], b"", False)
    case("多文件-separate", ["-s", "s/s/S/"], b"")

    # ---- -e / -f ----
    case("多-e", ["-e", "s/a/b/", "-e", "s/b/c/"], FIXTURE)
    case("脚本文件-f", ["-f", "script.sed"], FIXTURE)
    case("空脚本", [""], FIXTURE)
    case("注释行", ["# comment\ns/a/b/"], FIXTURE)

    # ---- 错误路径 ----
    case("错误-无脚本", [], FIXTURE)
    case("错误-s未闭合", ["s/a/b"], FIXTURE)
    case("错误-无效正则", ["s[/a[/b/"], FIXTURE)
    case("错误-未知指令", ["nosuchcmd"], FIXTURE)
    case("错误-文件不存在", ["s/a/b/", "missing.txt"], b"")
    case("错误-多文件其中一个不存在", ["s/a/b/", "a.txt", "missing.txt"], b"")
    case("错误-目录当文件", ["s/a/b/", "."], b"")

    # ---- 末行无换行 ----
    case("末行无换行", ["s/nonline/nonline/"], NONL)
    case("末行无换行-p", ["-n", "p"], NONL)

    # ---- z 选项 ----
    case("NUL分隔-z", ["-z", "s/a/b/"], b"a\x00b\x00")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[result] 报告已写入 {OUT}（{len(lines)} 行）")
    print(f"[result] 临时语料目录 {tmp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
