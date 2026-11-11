"""最终对照: 用 locale -a 里真实存在的名字跑 GNU, 与项目逐项比。

前两轮踩了两个坑, 这轮避开:
1. `LC_ALL=C printf ... | wc` 的前置赋值只作用于 printf, 管不到 wc。
   这轮一律用 `env LC_ALL=xxx wc`, 让 env 把变量设进 wc 的进程环境。
2. 名字要取自 `locale -a` 的真实列表: 里面是 C.utf8 / zh_CN / zh_CN.utf8,
   没有 C.UTF-8。用不存在的名字会静默退回默认 locale, 结论就是假的。

要回答的核心问题: 项目的数字到底与「哪个 locale 的 GNU」一致?
依据是项目按判定出的编码解码再统计, 天然属于 UTF-8 世界, 所以重点看
C.utf8 与 zh_CN.utf8; 同时把 C 与 zh_CN(GBK 区域设置)也列出来做对照。

附带把「列宽逐列算」做出一个能看出来的例子:
制表符展开后的显示宽度(17)远大于字节数(6), 两列的宽度就会不同。
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_final_matrix.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"

SAMPLES = {
    "ASCII": b"hello world\n",
    "UTF-8 中文": "中文内容\n".encode("utf-8"),
    "GBK 中文": "中文内容\n".encode("gb18030"),
    "高位字节 0xa1": b"\xa1\n",
    "纯二进制": b"\x00\x01\x02\xff\xfe\n",
    "零宽空格": "\u200b\n".encode("utf-8"),
}

LOCALES = [
    ("默认", ""),
    ("C", "env LC_ALL=C "),
    ("C.utf8", "env LC_ALL=C.utf8 "),
    ("zh_CN", "env LC_ALL=zh_CN "),
    ("zh_CN.utf8", "env LC_ALL=zh_CN.utf8 "),
]


def run_bash(script: str) -> str:
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    return (out + ("[err] " + err.strip() if err.strip() else "")).strip()


def project_counts(data: bytes) -> dict:
    sys.path.insert(0, ROOT)
    from w2l.commands import wc as wcmod
    encoding = wcmod._pick_encoding(data)
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError:
        text = wcmod._decode_bytes(data)
    return {
        "w": wcmod._count_words(text),
        "m": len(text),
        "c": len(data),
        "L": wcmod._display_width(text),
    }


def main() -> None:
    lines: list[str] = []

    lines.append("### 零、locale -a 里真实存在的名字")
    lines.append(run_bash("locale -a | grep -E '^(C|zh_CN|en_US)' | head -10"))
    lines.append("")

    lines.append("### 一、每个样本: 项目 vs 各 locale 的 GNU (四列计数)")
    for label, data in SAMPLES.items():
        hexed = "".join("\\x%02x" % b for b in data)
        ours = project_counts(data)
        lines.append("")
        lines.append("--- %s   原始字节 %r" % (label, data))
        lines.append("    %-14s 词=%-3d 字符=%-3d 字节=%-3d 最长行=%d" % (
            "项目", ours["w"], ours["m"], ours["c"], ours["L"]))
        for loc_name, prefix in LOCALES:
            vals = []
            for opt in ("-w", "-m", "-c", "-L"):
                out = run_bash("printf '%s' | %swc %s" % (hexed, prefix, opt))
                vals.append(int(out.split()[0]) if out.split() else -1)
            gnu = dict(zip(("w", "m", "c", "L"), vals))
            same = all(gnu[k] == ours[k] for k in ("w", "m", "c", "L"))
            mark = "完全一致" if same else "有差异"
            lines.append("    %-14s 词=%-3d 字符=%-3d 字节=%-3d 最长行=%-3d  %s" % (
                "GNU " + loc_name, gnu["w"], gnu["m"], gnu["c"], gnu["L"], mark))

    lines.append("")
    lines.append("### 二、列宽逐列算: 造一个两列宽度不同的例子")
    lines.append("内容 b'a\\tb\\tc\\n': 6 字节, 但显示宽度 17 (制表符展开到 8 的倍数)")
    lines.append("")
    for argv in ("-lL", "-lc", "-L", "-l"):
        out = run_bash("printf 'a\\tb\\tc\\n' | wc %s" % argv)
        lines.append("  wc %-4s -> %r" % (argv, out))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("写入 %s" % OUT)
    print()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
