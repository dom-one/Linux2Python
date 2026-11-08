"""为 cat 教程准备 GBK 演示文件，并把「文件路径 vs stdin」的差异实测出来。

用法:
    python AI/脚本/_t101_make_gbk_demo.py

为什么需要这个文件:
    教程要演示「GBK 文件被解码成 UTF-8 输出」。这条只在**文件路径**上成立：
    cat.py 里 stdin 分支的编码是写死的 utf-8，不做编码判定。
    而 GBK 字节走 stdin 时会被原样转交（字节守恒），所以光用 printf 管道
    演示不出解码效果，必须落一个真文件。

产出:
    AI/数据/gbk_demo.txt   （GBK 编码，git 已忽略）

产出:
    AI/数据/t101_gbk_demo_report.txt
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "main.py"
DATA = ROOT / "AI" / "数据"
GBK_FILE = DATA / "gbk_demo.txt"
OUT = DATA / "t101_gbk_demo_report.txt"

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)
    print(text)


def run(args: list[str], stdin: bytes = b"") -> tuple[int, bytes, bytes]:
    proc = subprocess.run(
        [sys.executable, str(MAIN), *args],
        input=stdin,
        capture_output=True,
        cwd=str(ROOT),
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    text = "中文内容\n第二行内容\n"
    raw = text.encode("gb18030")
    GBK_FILE.write_bytes(raw)
    say("=== 演示文件已生成 ===")
    say("  路径: %s" % GBK_FILE)
    say("  编码: gb18030")
    say("  原始字节 (%d 个):" % len(raw))
    say("    %s" % " ".join("%02x" % b for b in raw))
    say()

    say("=== 1. 走文件路径：判定出编码，解码成 UTF-8 ===")
    code, out, err = run(["cat", str(GBK_FILE)])
    say("  exit=%d" % code)
    say("  stdout 字节 (%d 个):" % len(out))
    say("    %s" % " ".join("%02x" % b for b in out))
    say("  stdout 文本: %r" % out.decode("utf-8", errors="replace"))
    say()

    say("=== 2. 走 stdin：编码写死 utf-8，GBK 字节原样转交 ===")
    code, out2, err = run(["cat", "-"], stdin=raw)
    say("  exit=%d" % code)
    say("  stdout 字节 (%d 个):" % len(out2))
    say("    %s" % " ".join("%02x" % b for b in out2))
    say("  字节守恒 = %s" % (out2 == raw))
    say()

    say("=== 3. 两者对比 ===")
    say("  文件路径输出 %d 字节，stdin 输出 %d 字节" % (len(out), len(out2)))
    say("  差 %d 字节（GBK 的 2 字节汉字变 UTF-8 的 3 字节）" % (len(out) - len(out2)))
    say()

    say("=== 4. 与 GNU cat 对照 ===")
    bash = r"E:\software\Git\Git\bin\bash.exe"
    if bash and Path(bash).is_file():
        gnu = subprocess.run(
            [bash, "-c", "cat %s | od -c" % GBK_FILE.as_posix()],
            capture_output=True,
        )
        say("  GNU cat 的字节（字节透传，GBK 原样）:")
        for line in gnu.stdout.decode("utf-8", errors="replace").splitlines():
            say("    %s" % line)
        say("  本项目 cat 的字节（解码成 UTF-8）:")
        say("    %s" % " ".join("%02x" % b for b in out))
        say("  → 两者不同，这是本项目刻意的取舍：控制台上中文能正常显示")
    say()

    OUT.write_bytes("\n".join(lines).encode("utf-8"))
    print()
    print("报告已写到 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
