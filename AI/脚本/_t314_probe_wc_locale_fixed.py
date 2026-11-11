"""修正前一轮的两个方法错误。

前一轮 (t313) 有两个错, 会让写进教程的结论是错的:

错一: 用了 `LC_ALL=C printf ... | wc -w`。
      shell 的变量前置赋值只作用于 `printf` 这一个命令, 管道另一端的 `wc`
      拿到的还是原环境。所以三列 locale 结果一模一样, 那张表是假的。
      正确写法是 `env LC_ALL=C wc -w` 或 `export LC_ALL=C; ...`。

错二: UTF-8 中文样本的 `-L` 结果是 4, 三个汉字按显示宽度应该是 6 列。
      先确认字节是不是真的喂对了(printf 的 \\x 转义 + od 复核),
      再确认 GNU 那边到底怎么算。

这一轮把两处都做对, 并加 od 复核每一步的字节流。
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_locale_fixed.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"


def run_bash(script: str) -> str:
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    return (out + ("[err] " + err.strip() if err.strip() else "")).strip()


def main() -> None:
    lines: list[str] = []

    lines.append("### 一、先确认字节流是对的")
    lines.append("printf 的 \\x 转义 + od 复核:")
    lines.append(run_bash("printf '\\xe4\\xb8\\xad\\xe6\\x96\\x87\\xe5\\xad\\x97\\n' | od -An -tx1"))
    lines.append("")
    lines.append("GBK 字节:")
    lines.append(run_bash("printf '\\xd6\\xd0\\xce\\xc4\\xc4\\xda\\xc8\\xdd\\n' | od -An -tx1"))
    lines.append("")

    lines.append("### 二、locale 正确写法对照 (env 前缀作用于整个管道)")
    lines.append("错误写法(前置赋值只管 printf):")
    lines.append("  LC_ALL=C printf '\\xa1\\n' | wc -w  -> %s"
                 % run_bash("LC_ALL=C printf '\\xa1\\n' | wc -w"))
    lines.append("正确写法(env 作用于 wc):")
    lines.append("  printf '\\xa1\\n' | env LC_ALL=C wc -w  -> %s"
                 % run_bash("printf '\\xa1\\n' | env LC_ALL=C wc -w"))
    lines.append("  printf '\\xa1\\n' | env LC_ALL=C.UTF-8 wc -w  -> %s"
                 % run_bash("printf '\\xa1\\n' | env LC_ALL=C.UTF-8 wc -w"))
    lines.append("  printf '\\xa1\\n' | env LC_ALL=zh_CN.UTF-8 wc -w  -> %s"
                 % run_bash("printf '\\xa1\\n' | env LC_ALL=zh_CN.UTF-8 wc -w"))
    lines.append("")

    lines.append("### 三、词数 × locale 矩阵 (env 正确写法)")
    samples = {
        "ASCII 文字": b"hello world\n",
        "纯控制字符": b"\x01\x02\x03\n",
        "含 NUL+高位": b"\x00\x01\x02\xff\xfe\n",
        "孤立高位字节 0xa1": b"\xa1\n",
        "孤立高位字节 0xad": b"\xad\n",
        "UTF-8 中文": "中文内容\n".encode("utf-8"),
        "GBK 中文": "中文内容\n".encode("gb18030"),
        "UTF-8 零宽空格": "\u200b\n".encode("utf-8"),
    }
    locales = ["", "LC_ALL=C", "LC_ALL=C.UTF-8", "LC_ALL=zh_CN.UTF-8"]
    head = "%-22s" % "样本"
    for loc in locales:
        head += "%-20s" % (loc or "(默认)")
    lines.append(head)
    lines.append("-" * len(head))
    for label, data in samples.items():
        row = "%-22s" % label
        for loc in locales:
            hexed = "".join("\\x%02x" % b for b in data)
            prefix = ("env %s " % loc) if loc else ""
            out = run_bash("printf '%s' | %swc -w" % (hexed, prefix))
            row += "%-20s" % (out.split()[0] if out.split() else "?")
        lines.append(row)
    lines.append("")

    lines.append("### 四、-L 显示宽度 × locale (env 正确写法)")
    lsamples = {
        "ASCII 5 字符": b"hello\n",
        "制表符展开": b"a\tb\tc\n",
        "CRLF": b"c1\r\nc2\r\n",
        "UTF-8 三个汉字": "中文字\n".encode("utf-8"),
        "GBK 三个汉字": "中文字\n".encode("gb18030"),
        "无结尾换行": b"abcdef",
    }
    head = "%-22s" % "样本"
    for loc in locales:
        head += "%-20s" % (loc or "(默认)")
    lines.append(head)
    lines.append("-" * len(head))
    for label, data in lsamples.items():
        row = "%-22s" % label
        for loc in locales:
            hexed = "".join("\\x%02x" % b for b in data)
            prefix = ("env %s " % loc) if loc else ""
            out = run_bash("printf '%s' | %swc -L" % (hexed, prefix))
            row += "%-20s" % (out.split()[0] if out.split() else "?")
        lines.append(row)
    lines.append("")

    lines.append("### 五、-L 的字节数对照 (确认 wc 看到的确实是那些字节)")
    lines.append("UTF-8 三个汉字的字节数: %s" % run_bash(
        "printf '\\xe4\\xb8\\xad\\xe6\\x96\\x87\\xe5\\xad\\x97\\n' | wc -c"))
    lines.append("UTF-8 三个汉字的字符数: %s" % run_bash(
        "printf '\\xe4\\xb8\\xad\\xe6\\x96\\x87\\xe5\\xad\\x97\\n' | wc -m"))
    lines.append("UTF-8 三个汉字的 -L:    %s" % run_bash(
        "printf '\\xe4\\xb8\\xad\\xe6\\x96\\x87\\xe5\\xad\\x97\\n' | wc -L"))
    lines.append("UTF-8 三个汉字的 -L(zh):%s" % run_bash(
        "printf '\\xe4\\xb8\\xad\\xe6\\x96\\x87\\xe5\\xad\\x97\\n' | env LC_ALL=zh_CN.UTF-8 wc -L"))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("写入 %s" % OUT)
    print()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
