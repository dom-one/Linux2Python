"""验证「GNU 的可打印性判定 = 把单字节当 Latin-1 码位看 Unicode 分类」这个假设。

逐字节扫描得到的分歧集合是:
  分歧(GNU 数 1 个词): 0xa1-0xac, 0xae-0xff
  一致(两边都 0):       0x00-0xa0, 0xad

这组边界正好等于「Latin-1 码位里 Unicode 分类为可打印的字符」:
  U+00A1-U+00AC  可打印(¡¢£¤¥¦§¨©ª«¬)
  U+00AD         SOFT HYPHEN, 分类 Cf(格式), 不可打印
  U+00AE-U+00FF  可打印(®¯°±²³´µ¶·¸¹º»¼½¾¿À-ÿ)
  U+0080-U+00A0  控制字符与不换行空格, 不可打印

假设成立的话, Python 的 str.isprint() 对 chr(byte) 的判定应当与扫描结果
完全吻合。这一轮把两者逐字节对照, 确认吻合; 并顺带查:
1. 中文 UTF-8 文件在 GNU 的 C 区域设置下词数是多少(README 有断言)
2. 本项目内部对这个样本的判定链条
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_latin1_hypothesis.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"

sys.path.insert(0, ROOT)
from w2l.commands import wc as wcmod  # noqa: E402


def gnu_words_of_bytes(data: bytes) -> int:
    """把原始字节喂给 Git Bash 的 GNU wc, 取词数。"""
    hexed = "".join("\\x%02x" % b for b in data)
    script = "printf '%s' | wc -w" % hexed
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    try:
        return int(out.split()[0])
    except (ValueError, IndexError):
        return -1


def main() -> None:
    lines: list[str] = []
    mismatches = []
    lines.append("### 假设检验: GNU 词数 == 「片段里有字节在 Latin-1 映射下 Unicode 可打印」")
    lines.append("%-8s %-10s %-12s %-14s %s" % ("字节", "GNU", "chr.isprint", "GNU是否可打印", "一致?"))
    lines.append("-" * 72)

    for value in range(256):
        gnu = gnu_words_of_bytes(bytes([value]) + b"\n")
        # Python 的 str.isprintable() 与 C 的 iswprint 口径基本一致:
        # 空格算可打印, 但它同时是空白字符, 所以不影响判定。
        printable = chr(value).isprintable()
        # GNU 数成 1 个词 <=> 该字节在 Latin-1 映射下是可打印字符
        gnu_printable = (gnu == 1)
        ok = gnu_printable == printable
        if not ok:
            mismatches.append(value)
        if value < 0x7f or value in (0x7f, 0x80, 0x9f, 0xa0, 0xa1, 0xac, 0xad, 0xae, 0xff):
            lines.append("%-8s %-10d %-12s %-14s %s" % (
                "0x%02x" % value, gnu, printable, gnu_printable, "是" if ok else "★否"))

    lines.append("-" * 72)
    lines.append("假设不成立的字节: %s" % (
        ", ".join("0x%02x" % v for v in mismatches) if mismatches else "无 —— 假设成立"))

    # 中文 UTF-8 文件在 GNU 的 C 区域设置下数几个词
    lines.append("")
    lines.append("### 中文 UTF-8 文件的词数")
    sample = "中文内容 hello\n".encode("utf-8")
    gnu = gnu_words_of_bytes(sample)
    encoding = wcmod._pick_encoding(sample)
    text = sample.decode(encoding)
    lines.append("内容: %r" % sample)
    lines.append("GNU 词数: %d" % gnu)
    lines.append("项目判定编码: %s -> %r" % (encoding, text))
    lines.append("项目词数: %d" % wcmod._count_words(text))

    # 纯中文
    sample2 = "中文内容\n".encode("utf-8")
    gnu2 = gnu_words_of_bytes(sample2)
    encoding2 = wcmod._pick_encoding(sample2)
    text2 = sample2.decode(encoding2)
    lines.append("")
    lines.append("内容: %r" % sample2)
    lines.append("GNU 词数: %d" % gnu2)
    lines.append("项目判定编码: %s -> %r" % (encoding2, text2))
    lines.append("项目词数: %d" % wcmod._count_words(text2))

    # GBK 中文
    sample3 = "中文内容\n".encode("gb18030")
    gnu3 = gnu_words_of_bytes(sample3)
    encoding3 = wcmod._pick_encoding(sample3)
    try:
        text3 = sample3.decode(encoding3)
    except UnicodeDecodeError:
        text3 = wcmod._decode_bytes(sample3)
    lines.append("")
    lines.append("内容: %r (GBK)" % sample3)
    lines.append("GNU 词数: %d" % gnu3)
    lines.append("项目判定编码: %s -> %r" % (encoding3, text3))
    lines.append("项目词数: %d" % wcmod._count_words(text3))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("写入 %s" % OUT)
    print()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
