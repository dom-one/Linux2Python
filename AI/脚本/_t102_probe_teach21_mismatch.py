"""取证：teach/21 草稿里 4 处「预期输出与实际不符」的真实原因。

用法:
    python AI/脚本/_t102_probe_teach21_mismatch.py

产出:
    AI/数据/t102_teach21_mismatch_report.txt

为什么需要这个脚本:
    草稿里有多处 od -c 的字节转储。手抄八进制极易错位（一个字节错一位，
    整行的字符含义就变了），所以这里不手算，全部由程序实跑后原样落盘，
    文档里直接贴程序吐出的字节。

四处待查:
    1. cat -E w2l/errors.py    文档预期疑似漏了结尾的引号
    2. cat gbk_demo.txt | od -c 文档预期是「原始 GBK 字节」，但管道走的是 cat
                              （cat 已经解码过了），命令本身与意图不符
    3. cat gbk_demo.txt | od -c 文档的 od 转储疑似抄错（每行 16 字节的边界）
    4. cat nope.txt w2l/errors.py  文档预期只列 stdout，核对器是 2>&1 合并的
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "main.py"
DATA = ROOT / "AI" / "数据"
GBK_FILE = DATA / "gbk_demo.txt"
OUT = DATA / "t102_teach21_mismatch_report.txt"

BASH = Path(r"E:\software\Git\Git\bin\bash.exe")

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


def run_bash(command: str) -> tuple[int, bytes]:
    """跑一条 bash 命令（教程里的命令是 bash 风格）。"""
    if not BASH.is_file():
        return -1, "(找不到 Git Bash)".encode("utf-8")
    proc = subprocess.run(
        [str(BASH), "-c", command],
        capture_output=True,
        cwd=str(ROOT),
    )
    return proc.returncode, proc.stdout + proc.stderr


def show(title: str, payload: bytes) -> None:
    say("  %s" % title)
    for row in payload.decode("utf-8", errors="replace").splitlines():
        say("    | %s" % row)
    say()


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)

    say("=== 现场 1：cat -E w2l/errors.py ===")
    code, out, err = run(["cat", "-E", "w2l/errors.py"])
    say("  exit=%d" % code)
    say("  stdout 原始字节:")
    show("按行看 stdout（repr，能看出结尾引号）:",
         repr(out).encode("utf-8"))
    say("  逐行 repr:")
    for row in out.splitlines():
        say("    %r" % row)
    say()

    say("=== 现场 2/3：GBK 文件的两种看字节方式 ===")
    if not GBK_FILE.is_file():
        say("  GBK 演示文件不存在，先用脚本生成")
        gen = subprocess.run(
            [sys.executable, str(ROOT / "AI" / "脚本" / "_t101_make_gbk_demo.py")],
            capture_output=True, cwd=str(ROOT))
        say("  生成脚本 exit=%d" % gen.returncode)
        say()
    if GBK_FILE.is_file():
        raw = GBK_FILE.read_bytes()
        say("  源文件 %d 字节" % len(raw))
        show("源文件 od -c（不经本项目 cat）:",
             run_bash("od -c AI/数据/gbk_demo.txt")[1])

        code, out, err = run(["cat", str(GBK_FILE)])
        say("  本项目 cat 走文件路径：exit=%d，stdout %d 字节" % (code, len(out)))
        show("cat 的 stdout 文本:", out)
        show("cat 的 stdout 再过 od -c（这才是管道里看到的）:",
             run_bash("python main.py cat AI/数据/gbk_demo.txt | od -c")[1])

        code2, out2, err2 = run(["cat", "-"], stdin=raw)
        say("  本项目 cat 走 stdin：exit=%d，stdout %d 字节" % (code2, len(out2)))
        show("stdin 的 stdout 再过 od -c:",
             run_bash("python main.py cat - < AI/数据/gbk_demo.txt | od -c")[1])
    say()

    say("=== 现场 4：错误路径，stdout 与 stderr 分开看 ===")
    code, out, err = run(["cat", "nope.txt", "w2l/errors.py"])
    say("  exit=%d" % code)
    show("stdout（只含文件内容）:", out)
    show("stderr（只含错误信息）:", err)
    show("2>&1 合并后的顺序（核对器就是这样跑的）:",
         run_bash("python main.py cat nope.txt w2l/errors.py 2>&1")[1])
    say("  合并后 stderr 的行排在第几行:",
         run_bash("python main.py cat nope.txt w2l/errors.py 2>&1 | head -1")[1])
    say()

    say("=== 现场 5：目录当操作数 ===")
    code, out, err = run(["cat", "w2l"])
    say("  exit=%d" % code)
    show("stdout:", out)
    show("stderr:", err)
    say()

    say("=== 现场 6：文档引用的其它内部量 ===")
    code, out, err = run_bash(
        "python -c \"from w2l.commands.cat import _candidate_encodings;print(_candidate_encodings())\"")
    say("  _candidate_encodings():")
    show("输出:", out)
    code, out, err = run_bash(
        "python -c \"from w2l.commands.cat import _text_score;print(_text_score('中文内容'), _text_score('ÖÐÎÄÄÚÈÝ'))\"")
    show("_text_score 对比:", out)
    code, out, err = run_bash(
        "python -c \"from w2l.commands.cat import _pick_encoding;print(_pick_encoding(b'a\\x00b'))\"")
    show("_pick_encoding 含 NUL:", out)
    say()

    OUT.write_bytes("\n".join(lines).encode("utf-8"))
    print()
    print("报告已写到 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
