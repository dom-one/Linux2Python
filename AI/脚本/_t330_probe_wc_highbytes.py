"""补最后几个数据点: 高位字节的词数分歧、项目与 GNU 的判定差别。

前面那轮样本(nul_ctrl_hi.dat / hi_only.dat)里项目数 0 词、GNU 数 1 词,
但用的字节没记下来。这一轮把字节固定下来, 顺带把「项目为什么数 0」的原因
(判定成什么编码 / 解码后剩什么字符)也打出来。
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_tutorial_words.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"

sys.path.insert(0, ROOT)
from w2l.commands import wc as wcmod  # noqa: E402


def run_bash(command: str, cwd: str) -> tuple[int, bytes]:
    handle, outpath = tempfile.mkstemp(suffix=".txt")
    os.close(handle)
    try:
        script = 'cd "%s" && { %s ; } > "%s" 2>&1' % (cwd, command, outpath)
        proc = subprocess.run([BASH, "-c", script], capture_output=True)
        with open(outpath, "rb") as fh:
            raw = fh.read()
        return proc.returncode, raw.replace(b"\r\n", b"\n")
    finally:
        for _ in range(3):
            try:
                os.remove(outpath)
                break
            except OSError:
                pass


def main() -> None:
    lines: list[str] = []
    samples = [
        ("0x80 三个字节", b"\x80\x80\x80"),
        ("0xA1 三个字节", b"\xa1\xa1\xa1"),
        ("0xFF 三个字节", b"\xff\xff\xff"),
        ("0x41 三个字节", b"AAA"),
        ("0x00 一个字节", b"\x00"),
        ("0x00 + 0x41", b"\x00A"),
        ("0x01 三个字节", b"\x01\x02\x03"),
    ]
    for title, data in samples:
        lines.append("=" * 70)
        lines.append("### %s  %r" % (title, data))
        hexs = "".join("\\x%02x" % b for b in data)
        for label, cmd in [
            ("项目 -w", "printf '%s' | python main.py wc -w" % hexs),
            ("项目 -m", "printf '%s' | python main.py wc -m" % hexs),
            ("GNU C -w", "printf '%s' | env LC_ALL=C wc -w" % hexs),
            ("GNU C -m", "printf '%s' | env LC_ALL=C wc -m" % hexs),
            ("GNU C.utf8 -w", "printf '%s' | env LC_ALL=C.utf8 wc -w" % hexs),
        ]:
            _, raw = run_bash(cmd, ROOT)
            lines.append("  %-14s -> %r" % (label, raw))
        # 项目内部: 判定成什么编码, 解码后是什么文本
        encoding = wcmod._pick_encoding(data)
        text = wcmod._decode_bytes(data)
        lines.append("  项目判定编码    -> %s" % encoding)
        lines.append("  兜底解码后文本  -> %r" % text)
        lines.append("  兜底解码后字符数 -> %d" % len(text))
        lines.append("  项目词数        -> %d" % wcmod._count_words(text))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("写入 %s" % OUT)
    print()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
