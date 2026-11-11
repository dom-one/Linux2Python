"""最终对照: locale × 样本 矩阵, 定清项目与 GNU 词数的边界。

前面的探针已经定位到三处需要收口的分歧:
1. 孤立高位字节: 项目 0 个词, GNU 1 个词
2. Cf 类零宽字符: 项目 0 个词, GNU 1 个词
3. README 声称「GNU 在 C 区域设置下中文文件词数是 0」, 但实测 LC_ALL=C 下是 1

第 3 条关系到 README 里「与 GNU 的差异」那几段写得对不对, 必须查实。

这一轮把样本 × locale 摆成矩阵, 每一格都跑 GNU 与项目,
输出一张能直接写进教程的对照表。
"""

from __future__ import annotations

import os
import subprocess
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_matrix.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"

sys.path.insert(0, ROOT)
from w2l.commands import wc as wcmod  # noqa: E402

SAMPLES = {
    "ASCII 文字": b"hello world\n",
    "纯控制字符": b"\x01\x02\x03\n",
    "含 NUL": b"\x00\x01\x02\xff\xfe\n",
    "孤立高位字节 0xa1": b"\xa1\n",
    "UTF-8 中文": "中文内容\n".encode("utf-8"),
    "UTF-8 中文+英文": "中文内容 hello\n".encode("utf-8"),
    "GBK 中文": "中文内容\n".encode("gb18030"),
    "UTF-8 零宽空格": "\n".encode("utf-8"),
}

LOCALES = [
    ("默认(C.UTF-8)", ""),
    ("LC_ALL=C", "LC_ALL=C "),
    ("LC_ALL=zh_CN.UTF-8", "LC_ALL=zh_CN.UTF-8 "),
]


def gnu_words(prefix: str, data: bytes) -> str:
    hexed = "".join("\\x%02x" % b for b in data)
    proc = subprocess.run(
        [BASH, "-c"], capture_output=True)  # 占位, 下面重写
    return ""


def gnu_words(prefix: str, data: bytes) -> str:
    hexed = "".join("\\x%02x" % b for b in data)
    script = "%sprintf '%s' | wc -w" % (prefix, hexed)
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    err = proc.stderr.decode("utf-8", errors="replace").strip()
    if err:
        return "ERR"
    return out.split()[0] if out.split() else "?"


def project_words(data: bytes) -> tuple[str, int]:
    encoding = wcmod._pick_encoding(data)
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError:
        text = wcmod._decode_bytes(data)
    return encoding, wcmod._count_words(text)


def main() -> None:
    lines: list[str] = []
    lines.append("### 词数矩阵: 样本 × locale (GNU) 对比项目")
    lines.append("")
    head = "%-24s %-10s" % ("样本", "项目")
    for name, _ in LOCALES:
        head += "%-18s" % ("GNU " + name)
    lines.append(head)
    lines.append("-" * len(head))

    for label, data in SAMPLES.items():
        encoding, ours = project_words(data)
        row = "%-24s %-10s" % (label, str(ours))
        for _, prefix in LOCALES:
            row += "%-18s" % gnu_words(prefix, data)
        lines.append(row)

    lines.append("")
    lines.append("### 各样本的解码链")
    for label, data in SAMPLES.items():
        encoding, ours = project_words(data)
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            text = wcmod._decode_bytes(data)
        lines.append("  %-24s 原始=%-34r 编码=%-10s 文本=%-24r 词数=%d" % (
            label, data, encoding, text, ours))

    lines.append("")
    lines.append("### -L 最长行显示宽度: 项目 vs GNU")
    lsamples = {
        "ASCII": b"hello\n",
        "制表符": b"a\tb\tc\n",
        "CRLF": b"c1\r\nc2\r\n",
        "UTF-8 中文": "中文字\n".encode("utf-8"),
        "GBK 中文": "中文字\n".encode("gb18030"),
        "无换行": b"abcdef",
    }
    lhead = "%-24s %-12s %-18s %-18s" % ("样本", "项目-L", "GNU 默认-L", "GNU zh_CN-L")
    lines.append(lhead)
    lines.append("-" * len(lhead))
    for label, data in lsamples.items():
        encoding = wcmod._pick_encoding(data)
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            text = wcmod._decode_bytes(data)
        ours_l = wcmod._display_width(text)
        hexed = "".join("\\x%02x" % b for b in data)
        g1 = bash_wc_L("", hexed)
        g2 = bash_wc_L("LC_ALL=zh_CN.UTF-8 ", hexed)
        lines.append("%-24s %-12d %-18s %-18s" % (label, ours_l, g1, g2))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("写入 %s" % OUT)
    print()
    print("\n".join(lines))


def bash_wc_L(prefix: str, hexed: str) -> str:
    script = "%sprintf '%s' | wc -L" % (prefix, hexed)
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    err = proc.stderr.decode("utf-8", errors="replace").strip()
    if err:
        return "ERR"
    return out.split()[0] if out.split() else "?"


if __name__ == "__main__":
    main()
