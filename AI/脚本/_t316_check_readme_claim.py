"""核实 README 与 wc.py 文档字符串里关于 GNU 的说法。

wc.py 文档字符串写:
  「中文算可打印字符，所以中文文件里的中文算词；GNU 在 C 区域设置下只把
    可打印的 ASCII 当可打印字符，中文文件在 GNU 那边词数是 0」

README 写:
  「GNU 在 C 区域设置下解不出 GBK，会把字符数整个记成 0，中文文件的词数也是 0」

前面实测发现这两句都需要限定条件:
- 「C 区域设置下词数是 0」——在 LC_ALL=C 下实测是 1 个词
- 「字符数整个记成 0」——在 LC_ALL=C 下实测字符数是 10(字节数), 不是 0

这一轮把 GBK 与 UTF-8 中文在四种 locale 下, 把 -w/-m/-c/-L 四个数全打出来,
得到一张能直接写进教程的精确表。
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_readme_claim.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"

SAMPLES = {
    "UTF-8 中文": "中文内容\n".encode("utf-8"),
    "GBK 中文": "中文内容\n".encode("gb18030"),
    "ASCII": b"hello world\n",
    "高位字节": b"\xa1\n",
    "纯二进制": b"\x00\x01\x02\xff\xfe\n",
}

LOCALES = [
    ("默认", ""),
    ("LC_ALL=C", "env LC_ALL=C "),
    ("LC_ALL=C.UTF-8", "env LC_ALL=C.UTF-8 "),
    ("LC_ALL=zh_CN.UTF-8", "env LC_ALL=zh_CN.UTF-8 "),
]


def run_bash(script: str) -> str:
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    return (out + ("[err] " + err.strip() if err.strip() else "")).strip()


def main() -> None:
    lines: list[str] = []
    lines.append("### GNU wc: 样本 × locale, 四个计数全列")
    for label, data in SAMPLES.items():
        hexed = "".join("\\x%02x" % b for b in data)
        lines.append("")
        lines.append("--- %s  原始字节 %r" % (label, data))
        for loc_name, prefix in LOCALES:
            vals = []
            for opt in ("-w", "-m", "-c", "-L"):
                out = run_bash("printf '%s' | %swc %s" % (hexed, prefix, opt))
                vals.append("%s=%s" % (opt, out.split()[0] if out.split() else "?"))
            lines.append("    %-22s %s" % (loc_name, "  ".join(vals)))

    lines.append("")
    lines.append("### 项目自己的结果 (同一批样本)")
    sys.path.insert(0, ROOT)
    from w2l.commands import wc as wcmod
    for label, data in SAMPLES.items():
        encoding = wcmod._pick_encoding(data)
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            text = wcmod._decode_bytes(data)
        lines.append("  %-14s 编码=%-10s 词=%-3d 字符=%-3d 字节=%-3d 最长行=%d" % (
            label, encoding, wcmod._count_words(text), len(text),
            len(data), wcmod._display_width(text)))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("写入 %s" % OUT)
    print()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
