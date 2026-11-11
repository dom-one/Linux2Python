"""查清「纯高位字节内容」词数分歧的成因。

上一轮逐字节扫描发现: 纯高位字节(0x80-0xFF)且无 ASCII 可打印字符的文件,
本项目数 0 个词, GNU wc 数 1 个词; 而纯控制字符(0x01-0x1F)两边都是 0。

这一轮要确认三件事:
1. 本项目对这类文件的**编码判定**结果是什么(是不是被判成二进制)
2. 解码后交给 _count_words 的**文本**长什么样
3. GNU 那边的规则能不能用 isprint 语义解释
   (拿字节 < 0x80 的控制字符做对照组)
"""

from __future__ import annotations

import locale
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_words_why.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"

sys.path.insert(0, ROOT)
from w2l.commands import wc as wcmod  # noqa: E402


def show(label: str, data: bytes) -> None:
    encoding = wcmod._pick_encoding(data)
    try:
        decoded = data.decode(encoding)
        decoded_repr = repr(decoded)
    except UnicodeDecodeError:
        decoded = wcmod._decode_bytes(data)
        decoded_repr = "%r (兜底解码后)" % decoded
    print("%-26s %-22s -> 编码=%-10s 解码文本=%-22s 词数=%d" % (
        label, repr(data), encoding, decoded_repr, wcmod._count_words(decoded)))


def gnu_words(data: bytes) -> int:
    """在 Git Bash 里把字节喂给 GNU wc, 取它数出的词数。"""
    script = (
        "printf '%s' '$(printf '\\\\x%02x\\\\x%02x\\\\n')' | wc -w"
        % (data[0], data[1] if len(data) > 1 else data[0])
    )
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    try:
        return int(out.split()[0])
    except (ValueError, IndexError):
        return -1


def main() -> None:
    lines: list[str] = []
    print("系统首选编码: %r" % locale.getpreferredencoding(False))
    print("候选编码表: %r" % (wcmod._candidate_encodings(),))

    samples = [
        ("纯高位字节 \\xff\\xfe", b"\xff\xfe\n"),
        ("纯高位字节 \\x80\\x81", b"\x80\x81\n"),
        ("纯控制字符 \\x01\\x02", b"\x01\x02\n"),
        ("纯 NUL", b"\x00\x00\n"),
        ("高位+ASCII", b"\xffa\n"),
        ("高位+中文(utf8)", "中\xff\n".encode("utf-8")),
    ]
    for label, data in samples:
        show(label, data)

    print()
    print("%-26s %-10s %-10s" % ("样本", "本项目", "GNU"))
    for label, data in samples:
        encoding = wcmod._pick_encoding(data)
        decoded = wcmod._decode_bytes(data) if _fails(data, encoding) else data.decode(encoding)
        ours = wcmod._count_words(decoded)
        gnu = gnu_words(data)
        print("%-26s %-10d %-10d" % (label, ours, gnu))
        lines.append("%-26s 本项目=%d GNU=%d" % (label, ours, gnu))

    # 记录 locale 细节
    lines.insert(0, "系统首选编码: %r" % locale.getpreferredencoding(False))
    lines.insert(1, "候选编码表: %r" % (wcmod._candidate_encodings(),))
    lines.insert(2, "")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print()
    print("写入 %s" % OUT)


def _fails(data: bytes, encoding: str) -> bool:
    try:
        data.decode(encoding)
    except UnicodeDecodeError:
        return True
    return False


if __name__ == "__main__":
    main()
