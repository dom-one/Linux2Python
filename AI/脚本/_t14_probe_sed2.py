#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第二轮探测：分支语义、原地编辑、CRLF、多行模式空间。

用法：python AI/脚本/_t14_probe_sed2.py
产物：AI/数据/sed_probe2.txt
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "sed_probe2.txt"

FIXTURE = b"alpha\nbravo\ncharlie\ndelta\necho\n"
CRLF = b"one\r\ntwo\r\nthree\r\n"


def find_sed() -> str:
    found = shutil.which("sed")
    if found:
        return found
    return r"C:\Program Files\Git\usr\bin\sed.exe"


def show(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    if any(byte > 127 for byte in raw):
        return f"{text!r} | raw={raw!r}"
    return repr(text)


def main() -> int:
    sed = find_sed()
    lines: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="sedprobe2_"))
    (tmp / "a.txt").write_bytes(FIXTURE)
    (tmp / "crlf.txt").write_bytes(CRLF)
    (tmp / "nonl.txt").write_bytes(b"no newline at end")

    def case(name: str, argv: list[str], stdin: bytes = b"") -> None:
        proc = subprocess.run(
            [sed, *argv], input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(tmp)
        )
        lines.append(f"### {name}")
        lines.append(f"$ sed {' '.join(argv)}")
        lines.append(f"exit={proc.returncode}")
        lines.append(f"out={show(proc.stdout)}")
        lines.append(f"err={show(proc.stderr)}")
        lines.append("")

    # ---- 分支语义（这次用 raw 字符串，正则里的 \n 是两个字符）----
    case("分支-经典N循环", ["-n", r":a;N;$!ba;s/\n/-/;p"], FIXTURE)
    case("分支-经典N循环无替换", ["-n", r":a;N;$!ba;p"], FIXTURE)
    case("分支-经典写法", ["-n", r":a;N;$!ba;s/\n/ /g;p"], FIXTURE)
    case("分支-条件t", ["-n", r"/bravo/{s/a/X/;t end};p;:end"], FIXTURE)
    case("分支-t不跳转", ["-n", r"/bravo/{s/zzz/X/;t end};p;:end"], FIXTURE)
    case("分支-b到末尾", ["-n", r"/bravo/{b end};p;:end"], FIXTURE)

    # ---- 多行模式空间里的 $ 地址 ----
    case("多行模式空间-N后美元", ["-n", r"N;$p"], FIXTURE)
    case("多行模式空间-N后美元取反", ["-n", r"N;$!d;p"], FIXTURE)
    case("多行模式空间-N配s", ["-n", r"N;s/\n/-/;p"], FIXTURE)

    # ---- 替换里的转义 ----
    case("替换-换行\\n", ["-n", r"s/a/\n/;p"], b"aXa\n")
    case("替换-制表\\t", ["-n", r"s/a/\t/;p"], b"aXa\n")
    case("替换-首字母大写\\u", ["-n", r"s/alpha/\u&/;p"], FIXTURE)
    case("替换-单字母小写\\l", ["-n", r"s/ALPHA/\l&/;p"], FIXTURE)
    case("替换-结束大写\\E", ["-n", r"s/a/\Uab\Ecd/;p"], b"aXa\n")
    case("替换-分组引用", ["-n", r"s/\(a\)\(l\)/\2\1/;p"], FIXTURE)
    case("替换-ERE分组", ["-r", "-n", r"s/(a)(l)/\2\1/;p"], FIXTURE)
    case("替换-ERE竖线", ["-r", "-n", r"s/a|o/X/;p"], FIXTURE)
    case("替换-BRE竖线字面", ["-n", r"s/a|o/X/;p"], FIXTURE)
    case("替换-多行匹配", ["-n", r"s/alpha\nbravo/AB/;p"], FIXTURE)

    # ---- 原地编辑 ----
    inplace = tmp / "inplace.txt"
    inplace.write_bytes(FIXTURE)
    proc = subprocess.run([sed, "-i", r"s/a/A/g", "inplace.txt"], cwd=str(tmp), capture_output=True)
    lines.append("### 原地编辑-无后缀")
    lines.append(f"exit={proc.returncode}")
    lines.append(f"内容={show(inplace.read_bytes())}")
    lines.append(f"目录={sorted(p.name for p in tmp.iterdir())}")
    lines.append("")

    inplace2 = tmp / "inplace2.txt"
    inplace2.write_bytes(FIXTURE)
    proc = subprocess.run([sed, "-i.bak", r"s/a/A/g", "inplace2.txt"], cwd=str(tmp), capture_output=True)
    lines.append("### 原地编辑-带后缀")
    lines.append(f"exit={proc.returncode}")
    lines.append(f"内容={show(inplace2.read_bytes())}")
    lines.append(f"备份={show((tmp / 'inplace2.txt.bak').read_bytes())}")
    lines.append("")

    inplace3 = tmp / "inplace3.txt"
    inplace3.write_bytes(FIXTURE)
    proc = subprocess.run([sed, "-i", "-n", r"s/a/A/g;p", "inplace3.txt"], cwd=str(tmp), capture_output=True)
    lines.append("### 原地编辑-配合-n")
    lines.append(f"exit={proc.returncode}")
    lines.append(f"内容={show(inplace3.read_bytes())}")
    lines.append("")

    inplace4 = tmp / "inplace4.txt"
    inplace4.write_bytes(b"no newline at end")
    proc = subprocess.run([sed, "-i", r"s/no/NOT/", "inplace4.txt"], cwd=str(tmp), capture_output=True)
    lines.append("### 原地编辑-末行无换行")
    lines.append(f"exit={proc.returncode}")
    lines.append(f"内容={show(inplace4.read_bytes())}")
    lines.append("")

    # ---- CRLF 处理 ----
    proc = subprocess.run([sed, r"s/one/1/"], cwd=str(tmp), capture_output=True)
    lines.append("### CRLF-默认")
    lines.append(f"exit={proc.returncode}")
    lines.append(f"out={show(proc.stdout)}")
    lines.append("")
    proc = subprocess.run([sed, "-b", r"s/one/1/"], cwd=str(tmp), capture_output=True)
    lines.append("### CRLF--b")
    lines.append(f"exit={proc.returncode}")
    lines.append(f"out={show(proc.stdout)}")
    lines.append("")

    # ---- 多文件与 -s ----
    (tmp / "m1.txt").write_bytes(b"1 alpha\n")
    (tmp / "m2.txt").write_bytes(b"2 alpha\n")
    proc = subprocess.run([sed, r"s/alpha/A/"], cwd=str(tmp), capture_output=True)
    lines.append("### 多文件-默认(拼接)")
    lines.append(f"exit={proc.returncode}")
    lines.append(f"out={show(proc.stdout)}")
    lines.append("")
    proc = subprocess.run([sed, "-s", "-n", "=", "m1.txt", "m2.txt"], cwd=str(tmp), capture_output=True)
    lines.append("### 多文件-separate行号")
    lines.append(f"exit={proc.returncode}")
    lines.append(f"out={show(proc.stdout)}")
    lines.append("")
    proc = subprocess.run([sed, "-n", "=", "m1.txt", "m2.txt"], cwd=str(tmp), capture_output=True)
    lines.append("### 多文件-默认行号")
    lines.append(f"exit={proc.returncode}")
    lines.append(f"out={show(proc.stdout)}")
    lines.append("")

    # ---- 其它 ----
    case("读标准输入", ["s/a/b/"], FIXTURE)
    case("空输入", ["s/a/b/"], b"")
    case("脚本文件-f", ["-f", "a.txt"], FIXTURE)
    case("忽略未知长选项", ["--follow-symlinks", "s/a/b/"], FIXTURE)
    case("重复-e", ["-e", "s/a/b/", "-e", "s/b/c/"], FIXTURE)
    case("选项与脚本顺序", ["s/a/b/", "-e", "s/b/c/"], FIXTURE)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[result] 报告已写入 {OUT}（{len(lines)} 行）")
    print(f"[result] 临时语料目录 {tmp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
