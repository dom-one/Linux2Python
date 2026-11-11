"""查清特殊字符样本的**判定链条**, 解释上一轮表格里的数字。

上一轮发现项目的词数与 GNU 在两类样本上不一致:
1. 孤立高位字节(0xa1-0xff)
2. Cf 类零宽字符(U+200B/U+200C/U+200D/U+FEFF/U+2060)

但表格里 soft_hyphen(U+00AD) 明明 _is_printable=False, 项目词数却是 1。
这说明**词数不只取决于 _is_printable, 还取决于先把内容解成了什么**——
编码判定是前置步骤, 解出来的文本变了, 后面数词的结果就跟着变。

这一轮把每个样本的完整链条打出来:
原始字节 -> 判定编码 -> 解码后的文本 -> 文本里每个字符的分类 -> 词数 -> GNU 词数
"""

from __future__ import annotations

import os
import subprocess
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_words_chain.txt")
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
    "cjk_U4E2D": 0x4E2D,
    "combining_U0301": 0x0301,
    "bom_UFEFF": 0xFEFF,
    "word_joiner_U2060": 0x2060,
    "fullwidth_A_FF21": 0xFF21,
}


def gnu_words_of(data: bytes) -> int:
    hexed = "".join("\\x%02x" % b for b in data)
    proc = subprocess.run(
        [BASH, "-c", "printf '%s' | wc -w" % hexed], capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    try:
        return int(out.split()[0])
    except (ValueError, IndexError):
        return -1


def main() -> None:
    lines: list[str] = []
    lines.append("### 每个样本的完整判定链条")
    lines.append("")
    for label, code in SPECIALS.items():
        ch = chr(code)
        data = (ch + "\n").encode("utf-8")
        encoding = wcmod._pick_encoding(data)
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            text = wcmod._decode_bytes(data)
        # 逐字符列分类, 看解码后到底是什么
        chars = []
        for c in text:
            if c == "\n":
                continue
            chars.append("U+%04X(%s,%s,可打印=%s)" % (
                ord(c), c if c.isprintable() else "·",
                unicodedata.category(c), wcmod._is_printable(c)))
        ours = wcmod._count_words(text)
        gnu = gnu_words_of(data)
        lines.append("--- %s" % label)
        lines.append("  原始字节     : %r" % data)
        lines.append("  判定编码     : %s" % encoding)
        lines.append("  解码后文本   : %r" % text)
        lines.append("  字符分类     : %s" % ("; ".join(chars) or "(空)"))
        lines.append("  项目词数     : %d" % ours)
        lines.append("  GNU 词数     : %d" % gnu)
        lines.append("  是否一致     : %s" % ("是" if ours == gnu else "★否"))
        lines.append("")

    # 孤立高位字节: 同样打链条
    lines.append("### 孤立高位字节的链条")
    for value in (0xa1, 0xad, 0xff):
        data = bytes([value]) + b"\n"
        encoding = wcmod._pick_encoding(data)
        try:
            text = data.decode(encoding)
            how = "直接解码"
        except UnicodeDecodeError:
            text = wcmod._decode_bytes(data)
            how = "兜底解码(解不出的字节被跳过)"
        ours = wcmod._count_words(text)
        gnu = gnu_words_of(data)
        lines.append("--- 0x%02x" % value)
        lines.append("  原始字节   : %r" % data)
        lines.append("  判定编码   : %s" % encoding)
        lines.append("  解码方式   : %s" % how)
        lines.append("  解码后文本 : %r" % text)
        lines.append("  项目词数   : %d" % ours)
        lines.append("  GNU 词数   : %d" % gnu)
        lines.append("")

    # 候选编码表与文本打分, 解释「为什么会选这个编码」
    lines.append("### 候选编码表")
    lines.append("  %r" % (wcmod._candidate_encodings(),))
    lines.append("")
    lines.append("### 各候选编码对样本的打分")
    for label, code in list(SPECIALS.items())[:4]:
        data = (chr(code) + "\n").encode("utf-8")
        rows = []
        for enc in wcmod._candidate_encodings():
            decoded = wcmod._decode_sample(data, enc)
            if decoded is None:
                rows.append("%s=解不出" % enc)
            else:
                rows.append("%s=%.4f(%r)" % (
                    enc, wcmod._text_score(decoded), decoded))
        lines.append("  %-24s %s" % (label, "  ".join(rows)))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("写入 %s" % OUT)
    print()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
