"""查清 wc 词数判定与 GNU 的真实差别。

上一轮差分发现一条不一致: 文件内容 b"\\x00\\x01\\x02\\xff\\xfe\\n"
本项目数 0 个词, Git Bash 的 GNU wc 数 1 个词。

开发任务的进度里写的是「纯二进制内容词数是 0」, 与 GNU 一致——
但实测不是这样。这个探针专门把词判定的各种边界摊开, 弄清 GNU 到底怎么算,
以及差异出在哪一条规则上。

同时确认 Git Bash 里 wc 的版本, 因为不同 coreutils 版本行为可能不同。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_words_probe.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"


def run_ours(base: str, argv: list[str]) -> str:
    cmd = [sys.executable, os.path.join(ROOT, "main.py"), "wc"] + argv
    proc = subprocess.run(cmd, cwd=base, capture_output=True)
    return proc.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")


def run_gnu(base: str, argv: list[str]) -> str:
    quoted = " ".join(argv)
    script = "cd '%s' && wc %s" % (base, quoted)
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    return proc.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")


def main() -> None:
    base = tempfile.mkdtemp(prefix="wc_words_")
    lines: list[str] = []
    try:
        # GNU wc 版本
        proc = subprocess.run([BASH, "-c", "wc --version"], capture_output=True)
        lines.append("GNU wc 版本: %s" % proc.stdout.decode("utf-8", errors="replace").strip())

        # locale 环境
        proc = subprocess.run([BASH, "-c", "echo LANG=$LANG LC_ALL=$LC_ALL"],
                              capture_output=True)
        lines.append("Git Bash locale: %s" % proc.stdout.decode("utf-8", errors="replace").strip())

        samples = {
            "nul_only.dat": b"\x00\x00\x00\n",
            "ctrl_only.dat": b"\x01\x02\x03\n",
            "nul_ctrl_hi.dat": b"\x00\x01\x02\xff\xfe\n",
            "ctrl_print.dat": b"a\x01b\n",
            "print_only.dat": b"abc\n",
            "hi_only.dat": b"\xff\xfe\n",
            "nul_noeol.dat": b"\x00",
            "ctrl_noeol.dat": b"\x01",
            "hi_print.dat": b"\xffa\n",
            "esc.dat": b"\x1b[0m\n",
            "space_sep_ctrl.dat": b"\x01 \x02\n",
            "tab_sep_ctrl.dat": b"\x01\t\x02\n",
        }
        for name, data in samples.items():
            with open(os.path.join(base, name), "wb") as fh:
                fh.write(data)

        lines.append("=" * 70)
        lines.append("%-22s %-28s %-28s %s" % ("文件", "本项目 -w", "GNU -w", "一致?"))
        for name in samples:
            ours = run_ours(base, ["-w", name]).strip()
            gnu = run_gnu(base, ["-w", name]).strip()
            ok = ours.split()[0] == gnu.split()[0]
            lines.append("%-22s %-28s %-28s %s" % (name, ours, gnu, "是" if ok else "★否"))

        # 再看 -c 与 -l 是否也一致, 确认差异只在词数上
        lines.append("=" * 70)
        lines.append("逐项对照 (行/字节):")
        for name in samples:
            ours = run_ours(base, ["-lc", name]).strip()
            gnu = run_gnu(base, ["-lc", name]).strip()
            ok = ours.split()[0] == gnu.split()[0] and ours.split()[1] == gnu.split()[1]
            lines.append("%-22s 本项目=%-20s GNU=%-20s %s" % (name, ours, gnu, "是" if ok else "★否"))

        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        print("写入 %s" % OUT)
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
