"""决定性测试: Git Bash 里 isprint() 对高位字节是什么口径。

上一轮发现 GNU 的词数判定等价于「字节按 Latin-1 解释后是否 Unicode 可打印」,
但说不清机制。这一轮用两个独立办法交叉验证:

办法一: tr -d '[:print:]' —— tr 用的是 isprint, 删掉被判为可打印的字节,
       看剩下的字节是不是正好是「被判不可打印」的那些。
办法二: 用 printf 把单个字节喂给 `grep -c .` 这类不依赖 locale 的工具,
       再用 od 确认字节没丢。

同时把项目的 _is_printable 与 Latin-1 口径逐字节对照, 确认两边判据一致。
"""

from __future__ import annotations

import os
import subprocess
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_isprint_probe.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"

sys.path.insert(0, ROOT)
from w2l.commands import wc as wcmod  # noqa: E402


def bash(script: str) -> str:
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    return (out + ("[err] " + err if err.strip() else "")).strip()


def main() -> None:
    lines: list[str] = []

    # 办法一: tr -d '[:print:]' 删掉被判为可打印的字节
    lines.append("### 办法一: tr -d '[:print:]' (删掉被判可打印的字节)")
    lines.append("%-10s %-22s %-22s %s" % ("字节", "删后剩下的字节", "Latin-1可打印", "项目_is_printable"))
    disagree = []
    for value in (0x01, 0x41, 0x7f, 0x80, 0x9f, 0xa0, 0xa1, 0xac, 0xad, 0xae, 0xff):
        script = "printf '\\x%02x' | tr -d '[:print:]' | od -An -tx1 | tr -d ' \\n'" % value
        left = bash(script)
        latin_printable = chr(value).isprintable()
        proj = wcmod._is_printable(chr(value))
        # 剩下字节 => tr 认为不可打印
        tr_says_printable = (left == "")
        lines.append("%-10s %-22s %-22s %s" % (
            "0x%02x" % value, left or "(空=判为可打印)",
            latin_printable, proj))
        if tr_says_printable != latin_printable:
            disagree.append(value)
    lines.append("")
    lines.append("tr 与 Latin-1 口径不一致的字节: %s" % (
        ", ".join("0x%02x" % v for v in disagree) if disagree else "无"))
    lines.append("")

    # 办法二: 项目 _is_printable 与 Latin-1 Unicode 口径逐字节全对照
    lines.append("### 办法二: 项目 _is_printable(chr(b)) vs chr(b).isprintable() 全 256 字节")
    diff = []
    for value in range(256):
        ch = chr(value)
        if wcmod._is_printable(ch) != ch.isprintable():
            diff.append(value)
    lines.append("不一致的字节: %s" % (
        ", ".join("0x%02x" % v for v in diff) if diff else "无 —— 两者口径完全一致"))
    lines.append("")

    # 项目口径的排除集合
    excluded = {}
    for value in range(256):
        ch = chr(value)
        if not wcmod._is_printable(ch):
            excluded.setdefault(unicodedata.category(ch), []).append(value)
    lines.append("### 项目 _is_printable 排除掉的字节, 按 Unicode 分类分组")
    for cat in sorted(excluded):
        values = excluded[cat]
        lines.append("  分类 %s: %d 个字节 (%s ... %s)" % (
            cat, len(values),
            "0x%02x" % min(values), "0x%02x" % max(values)))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("写入 %s" % OUT)
    print()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
