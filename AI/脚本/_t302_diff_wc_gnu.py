"""把本项目的 wc 与 Git Bash 的 GNU wc 逐条对照。

目的: 教程里要说清哪些行为与 GNU 一致、哪些是本项目的取舍。
写「与 GNU 一致」之前必须实测过, 不能凭源码注释推断。

做法: 同一批文件、同一条命令, 两边各跑一次, 比对 stdout 与退出码。
GNU wc 用 Git Bash 里的 /usr/bin/wc。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_gnu_diff.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"


def run_ours(base: str, argv: list[str], stdin_text: str | None = None):
    cmd = [sys.executable, os.path.join(ROOT, "main.py"), "wc"] + argv
    proc = subprocess.run(
        cmd, cwd=base, capture_output=True,
        input=(stdin_text.encode("utf-8") if stdin_text is not None else b""),
    )
    return proc.returncode, proc.stdout.decode("utf-8", errors="replace")


def run_gnu(base: str, argv: list[str], stdin_text: str | None = None):
    """在 Git Bash 里跑 GNU wc, stdin 走管道喂进去。"""
    quoted = " ".join(a if a != "-" else "-" for a in argv)
    if stdin_text is None:
        script = "cd '%s' && wc %s" % (base, quoted)
        stdin_bytes = b""
    else:
        script = "cd '%s' && printf '%%s' '%s' | wc %s" % (
            base, stdin_text.replace("'", "'\\''"), quoted)
        stdin_bytes = b""
    proc = subprocess.run(
        [BASH, "-c", script], capture_output=True, input=stdin_bytes,
    )
    return proc.returncode, proc.stdout.decode("utf-8", errors="replace")


def main() -> None:
    base = tempfile.mkdtemp(prefix="wc_diff_")
    lines: list[str] = []
    try:
        samples = {
            "one.txt": b"x\n",
            "two.txt": b"a b\nc\n",
            "empty.txt": b"",
            "noeol.txt": b"a\nb",
            "crlf.txt": b"c1\r\nc2\r\n",
            "tab.txt": b"a\tb\tc\n",
            "long.txt": b"x" * 19 + b"\n",
            "short.txt": b"z\n",
            "big.txt": b"y" * 99 + b"\n",
            "bin.dat": b"\x00\x01\x02\xff\xfe\n",
            "ctrl.txt": b"a\x01b\n",
            "many.txt": b"ab\n" * 100,
        }
        for name, data in samples.items():
            with open(os.path.join(base, name), "wb") as fh:
                fh.write(data)
        os.mkdir(os.path.join(base, "sub"))

        cases: list[tuple[str, list[str], str | None]] = [
            ("默认三列", ["one.txt"], None),
            ("默认三列 many", ["many.txt"], None),
            ("-l", ["-l", "one.txt"], None),
            ("-w", ["-w", "two.txt"], None),
            ("-c", ["-c", "two.txt"], None),
            ("-L tab", ["-L", "tab.txt"], None),
            ("-L crlf", ["-L", "crlf.txt"], None),
            ("-L long+short", ["-L", "long.txt", "short.txt"], None),
            ("多文件 total", ["-lwc", "one.txt", "two.txt"], None),
            ("列序固定 -clw", ["-clw", "one.txt"], None),
            ("宽度按字节总和撑开", ["-lwc", "one.txt", "big.txt"], None),
            ("单列不对齐", ["-l", "big.txt"], None),
            ("逐列 many", ["-lwc", "many.txt"], None),
            ("末行无换行", ["-lwc", "noeol.txt"], None),
            ("CRLF", ["-lwc", "crlf.txt"], None),
            ("空文件", ["-lwc", "empty.txt"], None),
            ("二进制无词", ["-lw", "bin.dat"], None),
            ("片段夹控制字符", ["-lw", "ctrl.txt"], None),
            ("stdin 无操作数", [], "a b\nc\n"),
            ("stdin 显式 -", ["-lwc", "-"], "a b\nc\n"),
            ("stdin 重复 -", ["-lw", "-", "-"], "a b\nc\n"),
            ("stdin 混入文件", ["-lwc", "-", "one.txt"], "a b\nc\n"),
            ("目录", ["-lwc", "sub"], None),
            ("目录 + 文件", ["-lwc", "sub", "many.txt"], None),
            ("缺文件", ["-l", "nope.txt"], None),
            ("单列且有 total", ["-l", "many.txt", "many.txt"], None),
        ]

        same = 0
        diff = 0
        for title, argv, stdin_text in cases:
            our_code, our_out = run_ours(base, argv, stdin_text)
            gnu_code, gnu_out = run_gnu(base, argv, stdin_text)
            # 本项目在 Windows 控制台输出 CRLF, Git Bash 里的 GNU wc 输出 LF。
            # 比对前统一成 LF, 否则每条都会「不一致」, 看不出真正的差别。
            our_out = our_out.replace("\r\n", "\n")
            gnu_out = gnu_out.replace("\r\n", "\n")
            ok = our_out == gnu_out
            if ok:
                same += 1
            else:
                diff += 1
            lines.append("=" * 60)
            lines.append("# %s  [%s]" % (title, "一致" if ok else "不一致"))
            lines.append("$ wc %s" % " ".join(argv))
            if stdin_text is not None:
                lines.append("[stdin=%r]" % stdin_text)
            lines.append("[本项目 退出码=%d] %r" % (our_code, our_out))
            lines.append("[GNU     退出码=%d] %r" % (gnu_code, gnu_out))

        lines.append("=" * 60)
        lines.append("汇总: 一致 %d，不一致 %d" % (same, diff))

        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        print("写入 %s" % OUT)
        print("一致 %d，不一致 %d" % (same, diff))
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
