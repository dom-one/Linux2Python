"""cat 教程第三轮探针：-v 与 -T 的先后、-A 对 CRLF、gb18030 解高位字节、--help。

用法:
    python AI/脚本/_t97_probe_cat_order.py

产出:
    AI/数据/t97_cat_order_report.txt

这一轮要钉死的四件事:
1. -v 时制表符不会被转成 ^I（_show_nonprinting 保留 0x09），-T 才会转
2. -v 与 -T 同开时，谁都不看命令行顺序，看的是 _show_content 里的固定顺序
3. -A 对 CRLF：\\r 显示成 ^M
4. gb18030 能不能解高位字节——这决定了 high.bin 走文本路还是二进制路
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "main.py"
OUT = ROOT / "AI" / "数据" / "t97_cat_order_report.txt"
BASH = r"E:\software\Git\Git\bin\bash.exe"

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


def show(title: str, args: list[str], stdin: bytes = b"") -> None:
    code, out, err = run(args, stdin=stdin)
    say("### %s" % title)
    say("$ python main.py %s" % " ".join(args))
    say("  exit=%d  stdout=%r" % (code, out))
    if err:
        say("  stderr=%r" % err)
    say()


def gnu_compare(title: str, argv: list[str], stdin: bytes = b"") -> None:
    gnu = subprocess.run(
        [BASH, "-c", "cat %s | od -c" % " ".join(argv)],
        input=stdin,
        capture_output=True,
        cwd=str(ROOT),
    )
    ours = run(["cat", *argv], stdin=stdin)
    say("### %s" % title)
    say("  GNU od -c   = %r" % gnu.stdout)
    say("  本项目字节  = %r" % ours[1])
    say("  一致(去 od 头) 需人工看 od 行")
    say()


def main() -> int:
    say("=== 1. -v 不转制表符，-T 才转 ===")
    show("默认：制表符原样", ["cat", "-"], stdin=b"col1\tcol2\n")
    show("-v：制表符仍是真制表符", ["cat", "-v", "-"], stdin=b"col1\tcol2\n")
    show("-T：制表符变 ^I", ["cat", "-T", "-"], stdin=b"col1\tcol2\n")
    show("-vT：^I", ["cat", "-vT", "-"], stdin=b"col1\tcol2\n")
    show("-Tv：^I（顺序无关）", ["cat", "-Tv", "-"], stdin=b"col1\tcol2\n")
    show("-vt：真制表符", ["cat", "-vt", "-"], stdin=b"col1\tcol2\n")
    say()

    say("=== 2. -A 对 CRLF：\\r 显示成 ^M ===")
    show("-A 遇 CRLF", ["cat", "-A", "-"], stdin=b"l1\r\nl2\r\n")
    show("-v 遇 CRLF：\\r 显示成 ^M", ["cat", "-v", "-"], stdin=b"l1\r\nl2\r\n")
    show("-E 遇 CRLF：$ 落在 \\r 之后", ["cat", "-E", "-"], stdin=b"l1\r\n")
    say()

    say("=== 3. gb18030 能不能解高位字节 ===")
    sys.path.insert(0, str(ROOT))
    from w2l.commands.cat import _candidate_encodings, _decode_sample, _pick_encoding, _text_score

    say("  候选编码 = %r" % (_candidate_encodings(),))
    for label, raw in [
        ("high.bin", b"\x80\xa0\xff\n"),
        ("ctrl.txt", b"bell\x07 del\x7f esc\x1b\n"),
        ("gbk", "中文内容\n".encode("gb18030")),
        ("ascii", b"plain ascii\n"),
    ]:
        say("  %s = %r" % (label, raw))
        for enc in _candidate_encodings():
            text = _decode_sample(raw, enc)
            if text is None:
                say("     %-10s 解不出" % enc)
            else:
                say("     %-10s score=%.4f  %r" % (enc, _text_score(text), text))
        say("     => _pick_encoding = %r" % _pick_encoding(raw))
    say()

    say("=== 4. 含 NUL 就一定是二进制 ===")
    say("  _pick_encoding(b'a\\x00b') = %r" % _pick_encoding(b"a\x00b"))
    say()

    say("=== 5. --help 输出 ===")
    code, out, err = run(["cat", "--help"])
    say("  exit=%d" % code)
    say(out.decode("utf-8", errors="replace"))
    say()

    say("=== 6. GNU 对照：-v 与 -T 的组合 ===")
    gnu_compare("-v 制表符", ["-v", "-"], stdin=b"col1\tcol2\n")
    gnu_compare("-vT 制表符", ["-vT", "-"], stdin=b"col1\tcol2\n")
    gnu_compare("-A CRLF", ["-A", "-"], stdin=b"l1\r\nl2\r\n")
    gnu_compare("-v CRLF", ["-v", "-"], stdin=b"l1\r\nl2\r\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes("\n".join(lines).encode("utf-8"))
    print()
    print("报告已写到 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
