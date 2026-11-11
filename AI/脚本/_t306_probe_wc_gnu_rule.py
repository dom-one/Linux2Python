"""查清 GNU wc 词数规则的真正判据。

逐字节扫描发现: 项目数 0 个词、GNU 数 1 个词的字节恰好是
0xa1-0xac 与 0xae-0xff, 而 0x80-0xa0、0xad 两边一致(都是 0)。

这个边界不像「可打印性」的边界, 更像某种编码的边界。这一轮:
1. 看 Git Bash 里 wc 实际跑在什么 locale 下 (locale 输出 + locale -a)
2. 换 LC_ALL 再测一遍, 看答案跟 locale 有没有关系
3. 试双字节组合, 看 GNU 是不是在按「多字节字符」处理
4. 用 strace 之类的方式不行, 改用「能不能用 isprint 语义解释」来交叉验证
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_gnu_rule.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"


def bash(script: str) -> str:
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    if err.strip():
        out += "[stderr] " + err.strip()
    return out.strip()


def main() -> None:
    lines: list[str] = []

    lines.append("### locale 环境")
    lines.append(bash("locale"))
    lines.append("")
    lines.append("### 可用 locale")
    lines.append(bash("locale -a 2>/dev/null | head -20"))
    lines.append("")

    # 单字节喂给 GNU wc, 换不同 LC_ALL
    lines.append("### 单字节样本在不同 LC_ALL 下的词数")
    lines.append("%-10s %-12s %-12s %-12s" % ("字节", "默认", "LC_ALL=C", "LC_ALL=C.UTF-8"))
    for value in (0x01, 0x41, 0x7f, 0x80, 0x9f, 0xa0, 0xa1, 0xad, 0xae, 0xff):
        row = []
        for prefix in ("", "LC_ALL=C ", "LC_ALL=C.UTF-8 "):
            script = "%sprintf '\\x%02x\\n' | wc -w" % (prefix, value)
            out = bash(script)
            row.append(out.split()[0] if out.split() else "?")
        lines.append("%-10s %-12s %-12s %-12s" % ("0x%02x" % value, *row))
    lines.append("")

    # 双字节组合: 高位字节 + ASCII
    lines.append("### 高位字节后面跟 ASCII")
    for value in (0xa1, 0xad, 0xff):
        script = "printf '\\x%02xA\\n' | wc -w" % value
        lines.append("0x%02x + 'A': %s" % (value, bash(script)))
    lines.append("")

    # 两个高位字节
    lines.append("### 两个高位字节")
    for pair in ("\\xa1\\xa2", "\\xad\\xae", "\\xff\\xff"):
        script = "printf '%s\\n' | wc -w" % pair
        lines.append("%s: %s" % (pair, bash(script)))
    lines.append("")

    # 高位字节后面跟空格再跟 ASCII
    lines.append("### 高位字节 + 空格 + ASCII (看是不是断开成两个词)")
    for value in (0xa1, 0xff):
        script = "printf '\\x%02x A\\n' | wc -w" % value
        lines.append("0x%02x + ' A': %s" % (value, bash(script)))
    lines.append("")

    # 高位字节 + 空格 + 另一个高位字节
    lines.append("### 高位字节 + 空格 + 高位字节")
    script = "printf '\\xa1 \\xff\\n' | wc -w"
    lines.append("0xa1 + ' ' + 0xff: %s" % bash(script))
    lines.append("")

    # 用 od 确认字节确实喂对了
    lines.append("### 确认字节没被 printf 吃掉")
    lines.append(bash("printf '\\xa1\\n' | od -An -tx1"))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("写入 %s" % OUT)
    print()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
