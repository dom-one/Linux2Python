#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第三轮探测：用 -f 脚本文件绕开 MSYS 运行时对命令行反斜杠的改写，再补齐若干细节。

用法：python AI/脚本/_t15_probe_sed3.py
产物：AI/数据/sed_probe3.txt
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "sed_probe3.txt"

FIXTURE = b"alpha\nbravo\ncharlie\ndelta\necho\n"


def find_sed() -> str:
    found = shutil.which("sed")
    return found or r"C:\Program Files\Git\usr\bin\sed.exe"


def show(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    if any(byte > 127 for byte in raw):
        return f"{text!r} | raw={raw!r}"
    return repr(text)


def main() -> int:
    sed = find_sed()
    lines: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="sedprobe3_"))
    (tmp / "a.txt").write_bytes(FIXTURE)
    (tmp / "crlf.txt").write_bytes(b"one\r\ntwo\r\nthree\r\n")
    (tmp / "m1.txt").write_bytes(b"1 alpha\n")
    (tmp / "m2.txt").write_bytes(b"2 alpha\n")

    def case(name: str, script: str, argv: list[str] | None = None, stdin: bytes = b"") -> None:
        script_path = tmp / "s.sed"
        script_path.write_bytes(script.encode("utf-8"))
        cmd = [sed, "-f", "s.sed", *(argv or [])]
        proc = subprocess.run(
            cmd, input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(tmp)
        )
        lines.append(f"### {name}")
        lines.append(f"脚本={script!r}")
        lines.append(f"参数={argv!r}")
        lines.append(f"exit={proc.returncode}")
        lines.append(f"out={show(proc.stdout)}")
        lines.append(f"err={show(proc.stderr)}")
        lines.append("")

    # ---- 反斜杠引用（用 -f 传脚本，避开命令行改写）----
    case("BRE分组引用", r"s/\(a\)\(l\)/\2\1/", ["a.txt"])
    case("BRE分组引用带g", r"s/\(a\)/\1\1/g", ["a.txt"])
    case("ERE分组引用", r"s/(a)(l)/\2\1/", ["-r", "a.txt"])
    case("ERE分组引用加r选项", r"s/(a)(l)/\2\1/", ["-r", "a.txt"])
    case("引用未定义分组", r"s/(a)/\2/", ["a.txt"])
    case("BRE字面括号", r"s/(a)(b)/\2\1/", ["a.txt"])

    # ---- 各种 s 标志 ----
    case("标志-gp", r"s/a/A/gp", ["a.txt"])
    case("标志-数字2", r"s/a/A/2", ["a.txt"])
    case("标志-数字超过匹配数", r"s/a/A/9", ["a.txt"])
    case("标志-i", r"s/ALPHA/alpha/i", ["a.txt"])
    case("标志-I", r"s/ALPHA/alpha/I", ["a.txt"])
    case("标志-未知", r"s/a/A/z", ["a.txt"])
    case("标志-w", r"s/a/A/w", ["a.txt"])
    case("标志-e", r"s/a/A/e", ["a.txt"])

    # ---- 脚本里的分号与换行 ----
    case("脚本含分号在正则里", "s/a;b/c/\n", ["a.txt"])
    case("脚本含分号在替换里", "s/a/b;c/\n", ["a.txt"])

    # ---- CRLF ----
    case("CRLF-默认", r"s/one/1/", ["crlf.txt"])
    case("CRLF-二进制模式", r"s/one/1/", ["-b", "crlf.txt"])
    case("CRLF-行尾匹配", r"s/$/!/", ["crlf.txt"])
    case("CRLF-空行判定", r"/^$/p", ["crlf.txt"])

    # ---- 多文件 ----
    case("多文件-默认行号", "-n\n=\n", ["m1.txt", "m2.txt"])
    case("多文件-separate行号", "-n\n=\n", ["-s", "m1.txt", "m2.txt"])
    case("多文件-默认内容", "s/alpha/A/\n", ["m1.txt", "m2.txt"])

    # ---- 范围与地址 ----
    case("范围-终点未找到", "-n\n/bravo/,/zzz/p\n", ["a.txt"])
    case("范围-起点未找到", "-n\n/zzz/,/echo/p\n", ["a.txt"])
    case("地址-加号0", "-n\n2,+0p\n", ["a.txt"])
    case("地址-波浪0", "-n\n1~0p\n", ["a.txt"])
    case("地址-相对负数", "-n\n3,-1p\n", ["a.txt"])

    # ---- 其它命令 ----
    case("y-长度不等", "y/abc/xy/\n", ["a.txt"])
    case("空脚本", "\n", ["a.txt"])
    case("只有注释", "# nothing\n", ["a.txt"])
    case("q在范围内", "-n\n1,3{p;q}\n", ["a.txt"])
    case("Q不带地址", "Q\n", ["a.txt"])
    case("多行替换N", "-n\nN;s/\\n/-/;p\n", ["a.txt"])
    case("标签跳到末尾", "-n\n/bravo/b end\np\n:end\n", ["a.txt"])
    case("不存在的标签", "-n\nb nowhere\np\n", ["a.txt"])

    # ---- 原地编辑细节 ----
    ip1 = tmp / "ip1.txt"
    ip1.write_bytes(FIXTURE)
    (tmp / "s.sed").write_bytes(b"s/a/A/g\n")
    proc = subprocess.run([sed, "-i", "-n", "-f", "s.sed", "ip1.txt"], cwd=str(tmp), capture_output=True)
    lines.append("### 原地编辑-n不打印")
    lines.append(f"exit={proc.returncode}")
    lines.append(f"内容={show(ip1.read_bytes())}")
    lines.append("")

    ip2 = tmp / "ip2.txt"
    ip2.write_bytes(FIXTURE)
    (tmp / "s.sed").write_bytes(b"s/a/A/g\n")
    proc = subprocess.run([sed, "-i", "-f", "s.sed", "ip2.txt"], cwd=str(tmp), capture_output=True)
    lines.append("### 原地编辑-正常")
    lines.append(f"exit={proc.returncode}")
    lines.append(f"内容={show(ip2.read_bytes())}")
    lines.append("")

    ip3 = tmp / "ip3.txt"
    ip3.write_bytes(b"one\r\ntwo\r\n")
    (tmp / "s.sed").write_bytes(b"s/one/1/\n")
    proc = subprocess.run([sed, "-i", "-f", "s.sed", "ip3.txt"], cwd=str(tmp), capture_output=True)
    lines.append("### 原地编辑-CRLF")
    lines.append(f"exit={proc.returncode}")
    lines.append(f"内容={show(ip3.read_bytes())}")
    lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[result] 报告已写入 {OUT}（{len(lines)} 行）")
    print(f"[result] 临时语料目录 {tmp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
