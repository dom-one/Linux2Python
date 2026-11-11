"""分清 GNU 的两条判定路径: 非法 UTF-8 字节 vs 合法的多字节字符。

已知:
- 孤立字节 0xa1 -> GNU 数 1 个词; 孤立字节 0xad -> GNU 数 0 个词
- 合法 UTF-8 的 U+00AD (C2 AD) -> GNU 数 1 个词

也就是说同一个码位, 走「非法字节」路径和走「合法多字节」路径结果不同。
这一轮把 Latin-1 的 0x80-0xFF 全部按两种写法各测一遍:
  写法 A: 孤立字节 <b>
  写法 B: 合法 UTF-8 编码 (C2/C3 前缀 + b)
再对照项目自己的判定, 就能把三边的口径摆清楚。

这是给教程用的最后一块数据, 之后就开始写文档。
"""

from __future__ import annotations

import os
import subprocess
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_gnu_two_paths.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"

sys.path.insert(0, ROOT)
from w2l.commands import wc as wcmod  # noqa: E402


def gnu_words(data: bytes) -> int:
    hexed = "".join("\\x%02x" % b for b in data)
    proc = subprocess.run(
        [BASH, "-c", "printf '%s' | wc -w" % hexed], capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    try:
        return int(out.split()[0])
    except (ValueError, IndexError):
        return -1


def ours_words(data: bytes) -> tuple[str, int]:
    encoding = wcmod._pick_encoding(data)
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError:
        text = wcmod._decode_bytes(data)
    return encoding, wcmod._count_words(text)


def main() -> None:
    lines: list[str] = []
    lines.append("### Latin-1 0x80-0xFF: 孤立字节 vs 合法 UTF-8 编码")
    lines.append("")
    lines.append("%-8s %-8s %-10s %-10s %-10s %-10s %-10s" % (
        "码位", "分类", "Latin1可打印", "GNU(A孤立)", "GNU(Butf8)", "GNU一致?", "项目(B)"))
    lines.append("-" * 86)

    same = 0
    diff = 0
    for value in range(0x80, 0x100):
        lone = bytes([value]) + b"\n"
        utf8 = chr(value).encode("utf-8") + b"\n"
        a = gnu_words(lone)
        b = gnu_words(utf8)
        ok = (a == b)
        if ok:
            same += 1
        else:
            diff += 1
        _, ours_b = ours_words(utf8)
        cat = unicodedata.category(chr(value))
        lines.append("%-8s %-8s %-10s %-10d %-10d %-10s %-10d" % (
            "U+%04X" % value, cat, chr(value).isprintable(), a, b,
            "是" if ok else "★否", ours_b))

    lines.append("-" * 86)
    lines.append("两条路径一致 %d 个码位, 不一致 %d 个" % (same, diff))
    lines.append("")

    # 挑几个代表性的做小结
    lines.append("### 代表性样本小结")
    for value in (0x80, 0xa0, 0xa1, 0xad, 0xae, 0xff):
        lone = bytes([value]) + b"\n"
        utf8 = chr(value).encode("utf-8") + b"\n"
        lines.append("  U+%04X (%s): GNU 孤立字节=%d, GNU UTF-8=%d, 项目 UTF-8=%d" % (
            value, unicodedata.category(chr(value)),
            gnu_words(lone), gnu_words(utf8), ours_words(utf8)[1]))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("写入 %s" % OUT)
    print()
    print("\n".join(lines[-30:]))


if __name__ == "__main__":
    main()
