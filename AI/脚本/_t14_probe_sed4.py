#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四轮探测：分清 -r 是否真的生效、ERE 模式支不支持反向引用、补齐地址与范围语义。

用法：python AI/脚本/_t14_probe_sed4.py
产物：AI/数据/sed_probe4.txt
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "sed_probe4.txt"

FIXTURE = b"alpha\nbravo\ncharlie\ndelta\necho\n"


def find_sed() -> str:
    return shutil.which("sed") or r"C:\Program Files\Git\usr\bin\sed.exe"


def show(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    return f"{text!r} | raw={raw!r}" if any(b > 127 for b in raw) else repr(text)


def main() -> int:
    sed = find_sed()
    lines: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="sedprobe4_"))
    (tmp / "a.txt").write_bytes(FIXTURE)
    (tmp / "crlf.txt").write_bytes(b"one\r\ntwo\r\nthree\r\n")
    (tmp / "m1.txt").write_bytes(b"1 alpha\n")
    (tmp / "m2.txt").write_bytes(b"2 alpha\n")

    def raw_case(name: str, cmd: list[str], stdin: bytes = b"") -> None:
        proc = subprocess.run(
            [sed, *cmd], input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(tmp)
        )
        lines.append(f"### {name}")
        lines.append(f"$ sed {' '.join(cmd)}")
        lines.append(f"exit={proc.returncode}")
        lines.append(f"out={show(proc.stdout)}")
        lines.append(f"err={show(proc.stderr)}")
        lines.append("")

    def script_case(name: str, script: str, opts: list[str], files: list[str]) -> None:
        path = tmp / "s.sed"
        path.write_bytes(script.encode("utf-8"))
        raw_case(name, [*opts, "-f", "s.sed", *files])

    # ---- -r 到底有没有生效：用「ERE 分组 vs BRE 字面括号」当判别器 ----
    script_case("判别器-无-r", "s/(a)(l)/X/\n", [], ["a.txt"])
    script_case("判别器-r在-f前", "s/(a)(l)/X/\n", ["-r"], ["a.txt"])
    script_case("判别器-r在-f后", "s/(a)(l)/X/\n", [], ["a.txt"])
    raw_case("判别器-r命令行在脚本前", ["-r", "s/(a)(l)/X/", "a.txt"])

    # ---- ERE 模式下的反向引用 ----
    script_case("ERE-RHS反向引用", "s/(a)(l)/\\2\\1/\n", ["-r"], ["a.txt"])
    script_case("ERE-LHS反向引用", "s/(a)\\1/X/\n", ["-r"], ["a.txt"])
    script_case("BRE-RHS反向引用", "s/\\(a\\)\\(l\\)/\\2\\1/\n", [], ["a.txt"])
    script_case("BRE-LHS反向引用", "s/\\(a\\)\\1/X/\n", [], ["a.txt"])

    # ---- 地址与范围（选项放命令行）----
    script_case("范围-终点未找到", "-n\n/bravo/,/zzz/p\n", [], ["a.txt"])
    script_case("范围-起点未找到", "-n\n/zzz/,/echo/p\n", ["-n"], ["a.txt"])
    script_case("地址-加号0", "2,+0p\n", ["-n"], ["a.txt"])
    script_case("地址-波浪0", "1~0p\n", ["-n"], ["a.txt"])
    script_case("地址-负数", "3,-1p\n", ["-n"], ["a.txt"])
    script_case("地址-行号0", "0p\n", ["-n"], ["a.txt"])
    script_case("地址-超出范围", "99p\n", ["-n"], ["a.txt"])
    script_case("多文件-separate行号", "=\n", ["-n", "-s"], ["m1.txt", "m2.txt"])
    script_case("多文件-默认行号", "=\n", ["-n"], ["m1.txt", "m2.txt"])

    # ---- CRLF 复核 ----
    script_case("CRLF-空行判定", "/^$/p\n", [], ["crlf.txt"])
    script_case("CRLF-匹配one", "/one/p\n", [], ["crlf.txt"])
    script_case("CRLF-匹配one加b", "/one/p\n", ["-b"], ["crlf.txt"])
    script_case("CRLF-整行匹配", "/^one$/p\n", [], ["crlf.txt"])

    # ---- 其它细节 ----
    script_case("分支-经典循环", ":a\nN\n$!ba\ns/\\n/-/\np\n", ["-n"], ["a.txt"])
    script_case("标签跳末尾", "/bravo/b end\np\n:end\n", ["-n"], ["a.txt"])
    script_case("不存在的标签", "b nowhere\np\n", ["-n"], ["a.txt"])
    script_case("多行替换N", "N\ns/\\n/-/\np\n", ["-n"], ["a.txt"])
    script_case("q带退出码", "q 3\n", [], ["a.txt"])
    script_case("追加a多行", "1a\\\nline2\n", [], ["a.txt"])
    script_case("替换c多行", "1c\\\nnew\n", [], ["a.txt"])
    script_case("空脚本", "\n", [], ["a.txt"])
    script_case("只有注释", "# nothing\n", [], ["a.txt"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[result] 报告已写入 {OUT}（{len(lines)} 行）")
    print(f"[result] 临时语料目录 {tmp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
