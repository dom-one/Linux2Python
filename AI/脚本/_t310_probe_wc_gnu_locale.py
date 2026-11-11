"""查 GNU 的词数结论**跟 locale 有没有关系**。

这一轮要回答一个关键问题: 项目的 README 与源码注释都写着
「纯二进制内容词数是 0」「与 GNU 一致」, 但实测 GNU 对 b"\\x00\\x01\\x02\\xff\\xfe\\n"
数出 1 个词。

如果 GNU 的答案随 locale 变, 那「与 GNU 一致」这句话就需要限定条件:
到底跟哪个 locale 的 GNU 比。

测试对象:
1. bin.dat = b"\\x00\\x01\\x02\\xff\\xfe\\n"  (测试用例里断言 0 个词)
2. 零宽空格 U+200B 的 UTF-8 字节
3. 孤立高位字节 0xa1
4. 纯中文 UTF-8
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_gnu_locale.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"

SAMPLES = {
    "bin.dat (测试用例里的样本)": b"\x00\x01\x02\xff\xfe\n",
    "zwsp U+200B": "".encode("utf-8"),
    "high byte 0xa1": b"\xa1\n",
    "utf8 chinese": "中文\n".encode("utf-8"),
    "ascii printable": b"A\n",
}

LOCALES = ["", "LC_ALL=C ", "LC_ALL=C.UTF-8 ", "LC_ALL=zh_CN.UTF-8 ",
           "LC_ALL=en_US.UTF-8 "]


def gnu_words(prefix: str, data: bytes) -> str:
    hexed = "".join("\\x%02x" % b for b in data)
    script = "%sprintf '%s' | wc -w" % (prefix, hexed)
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    err = proc.stderr.decode("utf-8", errors="replace").strip()
    if err:
        return "ERR:" + err[:40]
    return out.split()[0] if out.split() else "?"


def main() -> None:
    lines: list[str] = []
    lines.append("### GNU wc 词数随 locale 的变化")
    header = "%-28s" % "样本"
    for loc in LOCALES:
        header += "%-22s" % (loc.strip() or "(默认)")
    lines.append(header)
    lines.append("-" * len(header))

    for label, data in SAMPLES.items():
        row = "%-28s" % label
        for loc in LOCALES:
            row += "%-22s" % gnu_words(loc, data)
        lines.append(row)

    lines.append("")
    lines.append("### 项目在同一批样本上的词数")
    for label, data in SAMPLES.items():
        sys.path.insert(0, ROOT)
        from w2l.commands import wc as wcmod
        encoding = wcmod._pick_encoding(data)
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            text = wcmod._decode_bytes(data)
        lines.append("  %-28s 判定编码=%-10s 文本=%-22r 词数=%d" % (
            label, encoding, text, wcmod._count_words(text)))

    lines.append("")
    lines.append("### GNU 支持哪些 UTF-8 locale")
    proc = subprocess.run([BASH, "-c", "locale -a | grep -i -E 'zh_CN|en_US|C\\.'"],
                          capture_output=True)
    lines.append(proc.stdout.decode("utf-8", errors="replace").strip())

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("写入 %s" % OUT)
    print()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
