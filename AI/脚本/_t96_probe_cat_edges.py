"""cat 教程第二轮边界探针：stdin 换行、-E 与 \\r 的位置、-b/-s 组合的 GNU 对照。

用法:
    python AI/脚本/_t96_probe_cat_edges.py

产出:
    AI/数据/t96_cat_edges_report.txt

这一轮要确认三件事:
1. stdin 走的是二进制流，所以 CRLF 原样保留（源码里 _stdin_chunks 特意找 .buffer）
2. -E 的 $ 落在 \\r 之前还是之后
3. -b -s / -n -s 这类组合与 GNU 是否一致
另外验证 Git Bash 的 printf 能不能造出教程要用的语料（教程里要用 printf 现场造文件）。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "main.py"
OUT = ROOT / "AI" / "数据" / "t96_cat_edges_report.txt"
BASH = r"E:\software\Git\Git\bin\bash.exe"

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)
    print(text)


def run(args: list[str], stdin: bytes = b"", cwd: Path | None = None) -> tuple[int, bytes, bytes]:
    proc = subprocess.run(
        [sys.executable, str(MAIN), *args],
        input=stdin,
        capture_output=True,
        cwd=str(cwd or ROOT),
    )
    return proc.returncode, proc.stdout, proc.stderr


def show(title: str, args: list[str], stdin: bytes = b"") -> None:
    code, out, err = run(args, stdin=stdin)
    say("### %s" % title)
    say("$ python main.py %s" % " ".join(args))
    say("  exit=%d" % code)
    say("  stdout=%r" % out)
    if err:
        say("  stderr=%r" % err)
    say()


def bash(cmd: str) -> tuple[int, bytes, bytes]:
    proc = subprocess.run([BASH, "-c", cmd], capture_output=True, cwd=str(ROOT))
    return proc.returncode, proc.stdout, proc.stderr


def compare(title: str, argv: list[str]) -> None:
    """同一组参数，本项目与 GNU cat 逐字节比。"""
    gnu = subprocess.run(
        [BASH, "-c", "cat %s" % " ".join(argv)],
        capture_output=True,
        cwd=str(ROOT),
    )
    ours = run(["cat", *argv])
    same = gnu.stdout == ours[1]
    say("### %s" % title)
    say("$ cat %s" % " ".join(argv))
    say("  GNU    =%r" % gnu.stdout)
    say("  本项目 =%r" % ours[1])
    say("  一致=%s" % same)
    say()


def main() -> int:
    say("=== 1. stdin 的换行处理 ===")
    show("stdin 是 CRLF", ["cat", "-"], stdin=b"l1\r\nl2\r\n")
    show("stdin 是 LF", ["cat", "-"], stdin=b"l1\nl2\n")
    show("stdin 是 lone CR", ["cat", "-"], stdin=b"l1\rl2\n")
    show("stdin 是 CRLF 空行", ["cat", "-s", "-"], stdin=b"a\n\r\n\r\nb\n")
    show("stdin 是 CRLF + -b：空行内容是 \\r 不算空行",
         ["cat", "-b", "-"], stdin=b"a\n\r\nb\n")
    say()

    say("=== 2. -E 的 $ 落在哪 ===")
    show("-E 遇 CRLF：$ 落在 \\r 之后", ["cat", "-E", "-"], stdin=b"l1\r\n")
    show("-A 遇 CRLF", ["cat", "-A", "-"], stdin=b"l1\r\n")
    say()

    say("=== 3. -b / -s 组合与 GNU 对照 ===")
    tmp = Path(os.environ.get("TEMP", ".")) / "t96cat"
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "blank.txt").write_bytes(b"one\n\n\n\ntwo\n")
    (tmp / "ws.txt").write_bytes(b"one\n   \ntwo\n")
    (tmp / "s1.txt").write_bytes(b"x\n\n")
    (tmp / "s2.txt").write_bytes(b"\ny\n")
    (tmp / "ctrl.txt").write_bytes(b"bell\x07 del\x7f esc\x1b\n")
    (tmp / "high.bin").write_bytes(b"\x80\xa0\xff\n")
    (tmp / "crlf.txt").write_bytes(b"l1\r\nl2\r\n")
    (tmp / "noeol.txt").write_bytes(b"one\ntwo")
    tmp_bash = tmp.as_posix()

    for title, argv in [
        ("-b -s", ["-b", "-s", "blank.txt"]),
        ("-n -s", ["-n", "-s", "blank.txt"]),
        ("-b 含空格行", ["-b", "ws.txt"]),
        ("-s 含空格行", ["-s", "ws.txt"]),
        ("-s 跨文件", ["-s", "s1.txt", "s2.txt"]),
        ("-b 跨文件", ["-b", "s1.txt", "s2.txt"]),
        ("-n 跨文件", ["-n", "s1.txt", "s2.txt"]),
        ("-v ctrl", ["-v", "ctrl.txt"]),
        ("-v high", ["-v", "high.bin"]),
        ("-e ctrl", ["-e", "ctrl.txt"]),
        ("-t tabs 语义", ["-t", "ctrl.txt"]),
        ("-A ctrl", ["-A", "ctrl.txt"]),
        ("CRLF + -E", ["-E", "crlf.txt"]),
        ("CRLF + -b", ["-b", "crlf.txt"]),
        ("noeol + -E", ["-E", "noeol.txt"]),
        ("noeol + -b", ["-b", "noeol.txt"]),
    ]:
        gnu = subprocess.run(
            [BASH, "-c", "cd %s && cat %s" % (tmp_bash, " ".join(argv))],
            capture_output=True,
        )
        ours = run(["cat", *argv], cwd=tmp)
        same = gnu.stdout == ours[1]
        say("  %-14s GNU=%r" % (title, gnu.stdout))
        say("  %-14s 本项目=%r" % ("", ours[1]))
        say("  %-14s 一致=%s" % ("", same))
    say()

    say("=== 4. Git Bash 的 printf 能不能造出教程要用的语料 ===")
    printf_cases = [
        ("LF", "printf 'l1\\nl2\\n'"),
        ("CRLF", "printf 'l1\\r\\nl2\\r\\n'"),
        ("控制字符", "printf 'bell\\a del\\177 esc\\033\\n'"),
        ("高位字节", "printf '\\200\\240\\377\\n'"),
        ("NUL", "printf 'a\\000b\\n'"),
        ("空行串", "printf 'one\\n\\n\\n\\ntwo\\n'"),
    ]
    for title, cmd in printf_cases:
        code, out, err = bash(cmd)
        say("  %-10s %s" % (title, cmd))
        say("  %-10s -> %r (exit=%d)" % ("", out, code))
        if err:
            say("  %-10s stderr=%r" % ("", err))
    say()

    say("=== 5. printf 造出的语料喂给本项目 cat ===")
    pipe_cases = [
        ("控制字符 -v", "printf 'bell\\a del\\177 esc\\033\\n' | python main.py cat -v -"),
        ("控制字符 -e", "printf 'bell\\a del\\177 esc\\033\\n' | python main.py cat -e -"),
        ("高位字节 -v", "printf '\\200\\240\\377\\n' | python main.py cat -v -"),
        ("CRLF 原样", "printf 'l1\\r\\nl2\\r\\n' | python main.py cat -"),
        ("CRLF 字节", "printf 'l1\\r\\nl2\\r\\n' | python main.py cat - | od -c"),
        ("NUL 原样", "printf 'a\\000b\\n' | python main.py cat - | od -c"),
        ("空行 -s", "printf 'one\\n\\n\\n\\ntwo\\n' | python main.py cat -s -"),
        ("空行 -b", "printf 'one\\n\\n\\n\\ntwo\\n' | python main.py cat -b -"),
    ]
    for title, cmd in pipe_cases:
        code, out, err = bash(cmd)
        say("  %-14s $ %s" % (title, cmd))
        say("  %-14s   -> %r (exit=%d)" % ("", out, code))
        if err:
            say("  %-14s   stderr=%r" % ("", err))
    say()

    say("=== 6. 管道 vs 控制台的换行差异 ===")
    say("  上面的输出都是管道（重定向到临时文件）抓的，走 newline='' 分支。")
    say("  在真终端里 stdout.isatty() 为真，reconfigure(newline='') 不执行，")
    say("  Python 默认把 \\n 写成 \\r\\n。")
    say()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes("\n".join(lines).encode("utf-8"))
    print()
    print("报告已写到 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
