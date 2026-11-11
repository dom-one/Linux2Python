"""给 wc 教程采集真实输出。

做法：在临时目录里造一批边界文件，把要写进教程的命令逐条真跑一遍，
把「命令 -> 实际输出」写进 AI/产物/wc_tutorial_probe.txt，供写教程时引用。

为什么要落盘而不是直接打印:
bash 工具的输出会把连续空格吃掉（wc 的对齐全靠连续空格），
print 出来的结果不能直接当预期输出写进文档。
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_tutorial_probe.txt")


def build_tree(base: str) -> None:
    """造出教程里用到的边界文件。"""
    files = {
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
        "cjk.txt": "中文\n".encode("utf-8"),
        "gbk.txt": "中文内容\n".encode("gb18030"),
        "wide.txt": "全角字\n".encode("utf-8"),
    }
    for name, data in files.items():
        with open(os.path.join(base, name), "wb") as fh:
            fh.write(data)
    os.mkdir(os.path.join(base, "sub"))


def run(base: str, argv: list[str], stdin_text: str | None = None) -> tuple[int, str, str]:
    """在 base 目录里跑 python main.py wc <argv>。"""
    cmd = [sys.executable, os.path.join(ROOT, "main.py"), "wc"] + argv
    proc = subprocess.run(
        cmd, cwd=base, capture_output=True,
        input=(stdin_text.encode("utf-8") if stdin_text is not None else b""),
    )
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", errors="replace"),
        proc.stderr.decode("utf-8", errors="replace"),
    )


def main() -> None:
    base = tempfile.mkdtemp(prefix="wc_tut_")
    try:
        build_tree(base)
        cases: list[tuple[str, list[str], str | None]] = [
            ("默认三列", ["one.txt"], None),
            ("默认三列 two", ["two.txt"], None),
            ("-l", ["-l", "one.txt"], None),
            ("-w", ["-w", "two.txt"], None),
            ("-m", ["-m", "cjk.txt"], None),
            ("-m gbk", ["-m", "gbk.txt"], None),
            ("-c", ["-c", "two.txt"], None),
            ("-L tab", ["-L", "tab.txt"], None),
            ("-L wide", ["-L", "wide.txt"], None),
            ("-L crlf", ["-L", "crlf.txt"], None),
            ("-L long+short", ["-L", "long.txt", "short.txt"], None),
            ("多文件 total", ["-lwc", "one.txt", "two.txt"], None),
            ("列序固定 -clw", ["-clw", "one.txt"], None),
            ("列序固定 -wlc", ["-wlc", "one.txt"], None),
            ("全选项", ["-lwc", "-m", "-L", "one.txt"], None),
            ("宽度按字节总和撑开", ["-lwc", "one.txt", "big.txt"], None),
            ("单列不对齐", ["-l", "big.txt"], None),
            ("末行无换行", ["-lwc", "noeol.txt"], None),
            ("CRLF", ["-lwc", "crlf.txt"], None),
            ("空文件", ["-lwc", "empty.txt"], None),
            ("二进制无词", ["-lw", "bin.dat"], None),
            ("片段夹控制字符", ["-lw", "ctrl.txt"], None),
            ("stdin 无操作数", [], "a b\nc\n"),
            ("stdin 显式 -", ["-lwc", "-"], "a b\nc\n"),
            ("stdin 重复 -", ["-lw", "-", "-"], "a b\nc\n"),
            ("stdin 混入文件", ["-lwc", "-", "one.txt"], "a b\nc\n"),
            ("缺文件", ["-l", "nope.txt"], None),
            ("缺文件不影响后面", ["-lwc", "one.txt", "nope.txt"], None),
            ("目录", ["-lwc", "sub"], None),
        ]
        lines = []
        for title, argv, stdin_text in cases:
            code, out, err = run(base, argv, stdin_text)
            lines.append("=" * 60)
            lines.append("# %s" % title)
            lines.append("$ python main.py wc %s" % " ".join(argv))
            if stdin_text is not None:
                lines.append("[stdin=%r]" % stdin_text)
            lines.append("[退出码] %d" % code)
            lines.append("[stdout] %r" % out)
            lines.append("[stderr] %r" % err)
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        print("写入 %s" % OUT)
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
