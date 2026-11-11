"""把「项目与 GNU 在词数上的分歧」精确到 Unicode 分类。

上一轮确认: GNU 对单字节的判定 = 该字节按 Latin-1 解释后是否 Unicode 可打印,
逐字节 256 个全部吻合(只有 0x20 空格例外, 因为它同时是空白字符)。

这一轮补两件事:
1. 用真实文件(不是管道)复核「单个高位字节」的分歧, 排除管道喂法的干扰
2. 对**能正常解码**的文本, 找出项目与 GNU 词数还会分歧的 Unicode 分类
   (NBSP、软连字符、零宽空格这类「非空白但不可打印」的字符)

注意: 特殊字符一律用码位构造, 不写字面量——零宽空格、软连字符这类字符
写进源码会被编辑器/写盘流程吃掉, 上一版就是这么翻车的。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_words_categories.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"

sys.path.insert(0, ROOT)
from w2l.commands import wc as wcmod  # noqa: E402

SPECIALS = {
    "nbsp_U00A0": 0x00A0,
    "soft_hyphen_U00AD": 0x00AD,
    "zwsp_U200B": 0x200B,
    "zwnj_U200C": 0x200C,
    "zwj_U200D": 0x200D,
    "ideographic_space_U3000": 0x3000,
    "en_space_U2002": 0x2002,
    "cjk_U4E2D": 0x4E2D,
    "combining_U0301": 0x0301,
    "bom_UFEFF": 0xFEFF,
    "line_sep_U2028": 0x2028,
    "para_sep_U2029": 0x2029,
    "word_joiner_U2060": 0x2060,
}


def run_ours(base: str, name: str) -> int:
    cmd = [sys.executable, os.path.join(ROOT, "main.py"), "wc", "-w", name]
    proc = subprocess.run(cmd, cwd=base, capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    return int(out.split()[0])


def run_gnu(base: str, name: str) -> int:
    script = "cd '%s' && wc -w %s" % (base, name)
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    try:
        return int(out.split()[0])
    except (ValueError, IndexError):
        return -1


def main() -> None:
    base = tempfile.mkdtemp(prefix="wc_cat_")
    lines: list[str] = []
    try:
        lines.append("### 一、真实文件复核: 单个高位字节")
        lines.append("%-10s %-10s %-10s %s" % ("字节", "项目", "GNU", "分歧"))
        for value in (0xa1, 0xad, 0xff, 0x41):
            name = "hi%02x.dat" % value
            with open(os.path.join(base, name), "wb") as fh:
                fh.write(bytes([value]) + b"\n")
            ours = run_ours(base, name)
            gnu = run_gnu(base, name)
            lines.append("%-10s %-10d %-10d %s" % (
                "0x%02x" % value, ours, gnu, "" if ours == gnu else "★"))

        lines.append("")
        lines.append("### 二、能正常解码的文本: 各类非空白字符的词数")
        lines.append("%-26s %-8s %-12s %-8s %-8s %s" % (
            "字符", "码位", "Unicode分类", "项目", "GNU", "分歧"))
        for label, code in SPECIALS.items():
            ch = chr(code)
            name = "sp_%s.txt" % label
            with open(os.path.join(base, name), "wb") as fh:
                fh.write((ch + "\n").encode("utf-8"))
            ours = run_ours(base, name)
            gnu = run_gnu(base, name)
            cat = unicodedata.category(ch)
            lines.append("%-26s %-8s %-12s %-8d %-8d %s" % (
                label, "U+%04X" % code, cat, ours, gnu,
                "" if ours == gnu else "★"))

        lines.append("")
        lines.append("### 三、项目的 _is_printable 判定口径")
        for label, code in SPECIALS.items():
            ch = chr(code)
            lines.append("%-26s _is_printable=%-6s str.isprintable()=%-6s 分类=%s" % (
                label, wcmod._is_printable(ch), ch.isprintable(),
                unicodedata.category(ch)))

        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        print("写入 %s" % OUT)
        print()
        print("\n".join(lines))
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
