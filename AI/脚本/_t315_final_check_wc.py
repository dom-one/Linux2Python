"""最终核验: locale 到底怎么影响 GNU wc, 以及 README 的说法对不对。

前一轮 (t314) 修好了 locale 写法, 但还有两处要落实:
1. 默认情况(LC_CTYPE=C.UTF-8, LC_ALL 未设) 与 env LC_ALL=C.UTF-8 结果不同,
   说明 MSYS2 对 LC_ALL 的处理有特殊性。要确认默认时 wc 实际处于什么状态。
2. README 与 wc.py 的文档字符串都写着「GNU 在 C 区域设置下中文文件词数是 0」,
   但 t314 实测 LC_ALL=C 下 UTF-8 中文是 1 个词。这个矛盾必须查清楚:
   是我的测法有问题, 还是文档写错了。

办法: 用 locale 命令把 wc 进程真正看到的 locale 打出来,
再用 wc -c/-m/-L 三个数交叉验证 wc 对字节的解读方式。
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_final_check.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"

UTF8_CJK = "\\xe4\\xb8\\xad\\xe6\\x96\\x87\\xe5\\xad\\x97"  # 中文字


def run_bash(script: str) -> str:
    proc = subprocess.run([BASH, "-c", script], capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    return (out + ("[err] " + err.strip() if err.strip() else "")).strip()


def main() -> None:
    lines: list[str] = []

    lines.append("### 一、wc 进程真正看到的 locale")
    for label, prefix in [
        ("(默认, 不加任何 env)", ""),
        ("env LC_ALL=C", "env LC_ALL=C "),
        ("env LC_ALL=C.UTF-8", "env LC_ALL=C.UTF-8 "),
        ("env LC_ALL=zh_CN.UTF-8", "env LC_ALL=zh_CN.UTF-8 "),
        ("env LC_CTYPE=C.UTF-8", "env LC_CTYPE=C.UTF-8 "),
        ("env LANG=C", "env LANG=C "),
    ]:
        loc = run_bash("%slocale 2>&1 | head -3" % prefix)
        lines.append("--- %s" % label)
        lines.append(loc)
    lines.append("")

    lines.append("### 二、README 的说法核实: 「GNU 在 C 区域设置下中文文件词数是 0」")
    lines.append("README 与 wc.py 文档字符串的原话:")
    lines.append("  wc.py: 「GNU 在 C 区域设置下只把可打印的 ASCII 当可打印字符，"
                 "中文文件在 GNU 那边词数是 0」")
    lines.append("实测 (printf 喂 UTF-8 中文三个字 + 换行):")
    for label, prefix in [
        ("(默认)", ""),
        ("env LC_ALL=C", "env LC_ALL=C "),
        ("env LC_ALL=C.UTF-8", "env LC_ALL=C.UTF-8 "),
        ("env LC_ALL=zh_CN.UTF-8", "env LC_ALL=zh_CN.UTF-8 "),
    ]:
        w = run_bash("printf '%s\\n' | %swc -w" % (UTF8_CJK, prefix))
        m = run_bash("printf '%s\\n' | %swc -m" % (UTF8_CJK, prefix))
        c = run_bash("printf '%s\\n' | %swc -c" % (UTF8_CJK, prefix))
        L = run_bash("printf '%s\\n' | %swc -L" % (UTF8_CJK, prefix))
        lines.append("  %-22s 词=%-4s 字符=%-4s 字节=%-4s 最长行=%s" % (
            label, w.split()[0] if w.split() else "?",
            m.split()[0] if m.split() else "?",
            c.split()[0] if c.split() else "?",
            L.split()[0] if L.split() else "?"))
    lines.append("")

    lines.append("### 三、-L 对非法 UTF-8 字节怎么算宽度 (逐字节加)")
    lines.append("一个 ASCII 字符一个字节, 看 -L 怎么随字节数增长:")
    for count in (1, 2, 3, 4, 5, 8):
        hexed = "".join("\\x%02x" % 0xE4 for _ in range(count))
        L = run_bash("printf '%s\\n' | wc -L" % hexed)
        c = run_bash("printf '%s\\n' | wc -c" % hexed)
        lines.append("  %d 个 0xe4 字节: -L=%-4s -c=%s" % (
            count, L.split()[0] if L.split() else "?", c.split()[0] if c.split() else "?"))
    lines.append("")
    lines.append("一个合法 UTF-8 汉字(3 字节 e4 b8 ad):")
    for count in (1, 2, 3):
        hexed = "".join("\\xe4\\xb8\\xad" for _ in range(count))
        L = run_bash("printf '%s\\n' | wc -L" % hexed)
        c = run_bash("printf '%s\\n' | wc -c" % hexed)
        lines.append("  %d 个汉字: -L=%-4s -c=%s" % (
            count, L.split()[0] if L.split() else "?", c.split()[0] if c.split() else "?"))
    lines.append("")

    lines.append("### 四、项目自己的 -L 对同样样本")
    sys.path.insert(0, ROOT)
    from w2l.commands import wc as wcmod
    for label, data in [
        ("3 个 UTF-8 汉字", "中文字\n".encode("utf-8")),
        ("1 个 0xe4 字节", b"\xe4\n"),
        ("3 个 0xe4 字节", b"\xe4\xe4\xe4\n"),
        ("1 个 UTF-8 汉字", "中\n".encode("utf-8")),
    ]:
        encoding = wcmod._pick_encoding(data)
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            text = wcmod._decode_bytes(data)
        lines.append("  %-18s 编码=%-10s 文本=%-20r -L=%d" % (
            label, encoding, text, wcmod._display_width(text)))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("写入 %s" % OUT)
    print()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
