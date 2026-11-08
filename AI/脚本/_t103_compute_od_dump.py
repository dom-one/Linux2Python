"""独立复算：teach/21 草稿里 od -c 八进制转储的正确值。

用法:
    python AI/脚本/_t103_compute_od_dump.py

产出:
    AI/数据/t103_od_dump.txt

为什么单独一个脚本:
    草稿里的 od -c 转储是手抄的八进制，一个字节错一位整行含义就变。
    这里做两件事，互相印证：
    1. 直接跑 GNU od -c，拿它的原始输出
    2. 自己按 od 的格式（每行 16 字节、八进制三列）重算一遍
    两条路结果一致，才敢往文档里写。

关键：od 的八进制是三位一列、不足补零，行首是八进制偏移。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASH = Path(r"E:\software\Git\Git\bin\bash.exe")
OUT = ROOT / "AI" / "数据" / "t103_od_dump.txt"

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)
    print(text)


def run_bash(command: str) -> bytes:
    proc = subprocess.run([str(BASH), "-c", command],
                          capture_output=True, cwd=str(ROOT))
    return proc.stdout


def my_od(data: bytes) -> str:
    """按 od -c 的格式自己排一遍：每行 16 字节，字节用八进制三列表示。"""
    rows = []
    for offset in range(0, len(data), 16):
        chunk = data[offset:offset + 16]
        cells = []
        for byte in chunk:
            if byte == 0x0A:
                cells.append("  \\n")
            elif byte == 0x09:
                cells.append("  \\t")
            elif 0x20 <= byte < 0x7F:
                cells.append("   %s" % chr(byte))
            else:
                cells.append(" %03o" % byte)
        rows.append("%07o %s" % (offset, " ".join(cells)))
    return "\n".join(rows)


def compare(title: str, data: bytes, gnu: bytes) -> None:
    say("=== %s ===" % title)
    say("  字节数: %d" % len(data))
    say("  我算的 od -c:")
    for row in my_od(data).splitlines():
        say("    %s" % row)
    say("  GNU od -c 原文:")
    for row in gnu.decode("utf-8", errors="replace").splitlines():
        say("    %s" % row)
    say("  两条路是否逐字相同: %s"
        % ("是" if my_od(data).strip() == gnu.decode("utf-8", errors="replace").strip() else "否"))
    say()


def main() -> int:
    if not BASH.is_file():
        say("找不到 Git Bash，无法复算")
        OUT.write_bytes("\n".join(lines).encode("utf-8"))
        return 1

    # 1) 源文件的原始 GBK 字节（直接 od 文件，不经本项目 cat）
    raw = (ROOT / "AI" / "数据" / "gbk_demo.txt").read_bytes()
    compare("源文件原始字节（od 直接读文件）",
            raw, run_bash("od -c AI/数据/gbk_demo.txt"))

    # 2) 本项目 cat 走文件路径后的输出字节
    decoded = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "cat", "AI/数据/gbk_demo.txt"],
        capture_output=True, cwd=str(ROOT)).stdout
    compare("本项目 cat 走文件路径的输出字节",
            decoded, run_bash("python main.py cat AI/数据/gbk_demo.txt | od -c"))

    # 3) 同一文件走 stdin 的输出字节
    stdin_out = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "cat", "-"],
        input=raw, capture_output=True, cwd=str(ROOT)).stdout
    compare("本项目 cat 走 stdin 的输出字节",
            stdin_out, run_bash("python main.py cat - < AI/数据/gbk_demo.txt | od -c"))

    # 4) 把解码结果再解回文本，确认语义没变
    say("=== 语义核对 ===")
    say("  文件路径输出解码成 UTF-8 文本: %r" % decoded.decode("utf-8"))
    say("  stdin 输出解码成 UTF-8 文本: %r" % stdin_out.decode("utf-8", errors="replace"))
    say("  stdin 是否与源文件逐字节相同: %s" % (stdin_out == raw))
    say()

    OUT.write_bytes("\n".join(lines).encode("utf-8"))
    print()
    print("报告已写到 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
