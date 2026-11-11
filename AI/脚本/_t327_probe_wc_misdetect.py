"""收尾: 查清一个编码误判的坑, 并把 -L 在 UTF-8 区域设置下的对照补上。

t326 的样本 'e' + U+0301(组合重音) 项目给 3、GNU 给 2, 顺着这条线查下去发现:
项目把 b'e\\xcc\\x81\\n' 判成了 gb18030, 而不是 utf-8 —— 因为 gb18030 能严格解出
'e' + 一个汉字, 得分 3 分/字, 压过 utf-8 的解法。

这意味着: 一个「ASCII 字母 + 组合字符」的 UTF-8 文件, 会被本项目当成 GBK 读,
汉字被算成 2 列宽。这一轮把它验实, 并给出能复现的命令。

同时补 -L 在 C.utf8 区域设置下的对照, 确认「组合字符 0 列」这条规则的来源。
"""

from __future__ import annotations

import os
import subprocess
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_misdetect.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"

sys.path.insert(0, ROOT)
from w2l.commands import wc as wcmod  # noqa: E402

SAMPLES = {
    "e + U+0301 组合重音": b"e\xcc\x81\n",
    "a + U+0301": b"a\xcc\x81\n",
    "纯 ASCII": b"hello\n",
    "纯 UTF-8 汉字": "中文\n".encode("utf-8"),
    "GBK 汉字": "中文\n".encode("gb18030"),
    "ASCII + U+0301 + 汉字": b"e\xcc\x81" + "中\n".encode("utf-8"),
}


def bash(script: str) -> bytes:
    proc = subprocess.run([BASH, "-c", script], capture_output=True,
                          stdin=subprocess.DEVNULL)
    return proc.stdout.replace(b"\r\n", b"\n")


def ours(script: str) -> bytes:
    proc = subprocess.run(
        [BASH, "-c", 'cd "%s" && { %s ; } 2>&1' % (ROOT, script)],
        capture_output=True, stdin=subprocess.DEVNULL,
    )
    return proc.stdout.replace(b"\r\n", b"\n")


def main() -> None:
    lines: list[str] = []

    lines.append("### 一、编码判定链条")
    for label, data in SAMPLES.items():
        encoding = wcmod._pick_encoding(data)
        scores = []
        for enc in wcmod._candidate_encodings():
            decoded = wcmod._decode_sample(data, enc)
            if decoded is None:
                scores.append("%s=解不出" % enc)
            else:
                scores.append("%s=%.4f" % (enc, wcmod._text_score(decoded)))
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            text = wcmod._decode_bytes(data)
        lines.append("--- %s" % label)
        lines.append("  原始字节 : %r" % data)
        lines.append("  判定编码 : %s" % encoding)
        lines.append("  各编码得分: %s" % "  ".join(scores))
        lines.append("  解码文本 : %r" % text)
        lines.append("  字符分类 : %s" % ", ".join(
            "U+%04X(%s)" % (ord(c), unicodedata.category(c))
            for c in text if c != "\n"))
        lines.append("  项目 -m  : %d" % len(text))
        lines.append("  项目 -L  : %d" % wcmod._display_width(text))

    lines.append("")
    lines.append("### 二、项目与 GNU 的 -m/-L 对照(默认区域设置 与 C.utf8)")
    for label, data in SAMPLES.items():
        hexed = "".join("\\x%02x" % b for b in data)
        g_def = bash("printf '%s' | wc -m -L" % hexed)
        g_u8 = bash("printf '%s' | env LC_ALL=C.utf8 wc -m -L" % hexed)
        o = ours("printf '%s' | python main.py wc -m -L" % hexed)
        lines.append("--- %s" % label)
        lines.append("  GNU 默认    : %r" % g_def.decode("latin-1"))
        lines.append("  GNU C.utf8  : %r" % g_u8.decode("latin-1"))
        lines.append("  项目        : %r" % o.decode("latin-1"))

    lines.append("")
    lines.append("### 三、可复现的命令(项目)")
    for label, data in SAMPLES.items():
        hexed = "".join("\\x%02x" % b for b in data)
        out = ours("printf '%s' | python main.py wc -lwc -m -L" % hexed)
        lines.append("  printf '%s' | python main.py wc -lwc -m -L  ->  %r"
                     % (hexed, out.decode("latin-1")))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("写入 %s" % OUT)


if __name__ == "__main__":
    main()
