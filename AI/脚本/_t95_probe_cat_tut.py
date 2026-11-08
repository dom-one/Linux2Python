"""为 cat 教程实测行为，产出教程里要写的「预期输出」。

用法:
    python AI/脚本/_t95_probe_cat_tut.py

产出:
    AI/数据/t95_cat_tut_report.txt

要点:
- 语料一律用 write_bytes 写。Windows 上 write_text 会把 \\n 翻成 \\r\\n，
  测的就不是「LF 文件」而是「CRLF 文件」了。
- 输出一律按字节打印（repr 或 od 风格），避免控制台编码把内容改掉。
"""

from __future__ import annotations

import locale
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "main.py"
OUT = ROOT / "AI" / "数据" / "t95_cat_tut_report.txt"

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)
    print(text)


def run(args: list[str], stdin: bytes = b"", cwd: Path | None = None) -> tuple[int, bytes, bytes]:
    """跑 python main.py <args>，返回 (退出码, stdout 字节, stderr 字节)。"""
    proc = subprocess.run(
        [sys.executable, str(MAIN), *args],
        input=stdin,
        capture_output=True,
        cwd=str(cwd or ROOT),
    )
    return proc.returncode, proc.stdout, proc.stderr


def show(title: str, args: list[str], stdin: bytes = b"", cwd: Path | None = None) -> None:
    code, out, err = run(args, stdin=stdin, cwd=cwd)
    say("### %s" % title)
    say("$ python main.py %s" % " ".join(repr(a) if (" " in a or not a) else a for a in args))
    say("  exit=%d" % code)
    say("  stdout=%r" % out)
    if err:
        say("  stderr=%r" % err)
    say()


def show_bytes(title: str, args: list[str], stdin: bytes = b"") -> None:
    """把 stdout 按 od -c 风格摊开，用来展示字节级行为。"""
    code, out, err = run(args, stdin=stdin)
    say("### %s" % title)
    say("$ python main.py %s" % " ".join(args))
    say("  exit=%d" % code)
    say("  bytes: %s" % " ".join("%02x" % b for b in out))
    say("  repr : %r" % out)
    if err:
        say("  stderr=%r" % err)
    say()


def main() -> int:
    say("=== 环境 ===")
    say("python %s" % sys.version.split()[0])
    say("locale.getpreferredencoding(False) = %r" % locale.getpreferredencoding(False))
    say("stdout encoding = %r" % (sys.stdout.encoding,))
    say()

    tmp = Path(tempfile.mkdtemp(prefix="t95cat_"))
    say("=== 语料目录 %s ===" % tmp)
    say()

    # 全部用 write_bytes，保证是真 LF
    (tmp / "basic.txt").write_bytes(b"alpha\nbeta\ngamma\n")
    (tmp / "blank.txt").write_bytes(b"one\n\n\n\ntwo\n")
    (tmp / "ws.txt").write_bytes(b"one\n   \ntwo\n")
    (tmp / "tabs.txt").write_bytes(b"col1\tcol2\n")
    (tmp / "noeol.txt").write_bytes(b"one\ntwo")
    (tmp / "crlf.txt").write_bytes(b"l1\r\nl2\r\n")
    (tmp / "ctrl.txt").write_bytes(b"bell\x07 del\x7f esc\x1b\n")
    (tmp / "high.bin").write_bytes(b"\x80\xa0\xff\n")
    (tmp / "gbk.txt").write_bytes("中文内容\n".encode("gb18030"))
    (tmp / "s1.txt").write_bytes(b"x\n\n")
    (tmp / "s2.txt").write_bytes(b"\ny\n")
    (tmp / "many.txt").write_bytes(b"".join(b"l%d\n" % i for i in range(1, 13)))
    (tmp / "sub").mkdir()
    say("语料写好了（write_bytes，真 LF）")
    say()

    # ---------- 1. 默认输出 ----------
    show("默认：原样输出", ["cat", str(tmp / "basic.txt")])
    show("默认：多文件连接，中间不加分隔符",
         ["cat", str(tmp / "basic.txt"), str(tmp / "basic.txt")])

    # ---------- 2. 行号 ----------
    show("-n：所有行编号", ["cat", "-n", str(tmp / "basic.txt")])
    show("-b：只给非空行编号", ["cat", "-b", str(tmp / "blank.txt")])
    show("-n -b：-b 覆盖 -n（顺序无关）",
         ["cat", "-n", "-b", str(tmp / "blank.txt")])
    show("-b -n：反过来也一样", ["cat", "-b", "-n", str(tmp / "blank.txt")])
    show("编号跨文件连续累计",
         ["cat", "-n", str(tmp / "basic.txt"), str(tmp / "basic.txt")])
    show("编号列宽：第 10 行开始左边界右移", ["cat", "-n", str(tmp / "many.txt")])

    # ---------- 3. 行尾 $ 与制表符 ----------
    show("-E：行尾加 $", ["cat", "-E", str(tmp / "basic.txt")])
    show("-E：末行无换行不补 $", ["cat", "-E", str(tmp / "noeol.txt")])
    show("-T：制表符显示成 ^I", ["cat", "-T", str(tmp / "tabs.txt")])

    # ---------- 4. 压空行 ----------
    show("-s：连续空行压成一行", ["cat", "-s", str(tmp / "blank.txt")])
    show("-s：含空格的行不是空行，不压", ["cat", "-s", str(tmp / "ws.txt")])
    show("-s：压紧状态跨文件延续",
         ["cat", "-s", str(tmp / "s1.txt"), str(tmp / "s2.txt")])
    show("-n -s：编号与压紧同时开", ["cat", "-n", "-s", str(tmp / "blank.txt")])
    show("-b -s：编号与压紧同时开", ["cat", "-b", "-s", str(tmp / "blank.txt")])

    # ---------- 5. 非打印字符 ----------
    show("-v：控制字符 ^ 记号", ["cat", "-v", str(tmp / "ctrl.txt")])
    show("-v：高位字节 M- 记号", ["cat", "-v", str(tmp / "high.bin")])
    show("-e：等价 -vE", ["cat", "-e", str(tmp / "ctrl.txt")])
    show("-t：等价 -vT", ["cat", "-t", str(tmp / "tabs.txt")])
    show("-A：等价 -vET", ["cat", "-A", str(tmp / "tabs.txt")])
    show("-A 作用在含控制字符的文件上", ["cat", "-A", str(tmp / "ctrl.txt")])

    # ---------- 6. 编码判定 ----------
    show("GBK 文件解码成 UTF-8 输出", ["cat", str(tmp / "gbk.txt")])
    show_bytes("GBK 文件输出字节数变成 3 倍", ["cat", str(tmp / "gbk.txt")])

    # ---------- 7. 二进制 ----------
    show_bytes("二进制逐字节原样转交（NUL 判定）",
               ["cat", str(tmp / "high.bin")])
    blob = tmp / "blob.bin"
    blob.write_bytes(bytes(range(256)))
    code, out, err = run(["cat", str(blob)])
    say("### 全 256 字节二进制文件")
    say("  exit=%d  len=%d" % (code, len(out)))
    say("  前 16 字节: %s" % " ".join("%02x" % b for b in out[:16]))
    say("  末 16 字节: %s" % " ".join("%02x" % b for b in out[-16:]))
    say()

    # ---------- 8. CRLF 与末行 ----------
    show_bytes("CRLF 原样转交", ["cat", str(tmp / "crlf.txt")])
    show_bytes("末行无换行，输出也不补", ["cat", str(tmp / "noeol.txt")])

    # ---------- 9. 标准输入 ----------
    show("不给操作数读标准输入", ["cat"], stdin=b"from stdin\n")
    show("- 表示标准输入", ["cat", "-"], stdin=b"from stdin\n")
    show("文件和 - 可以混排，位置即读取顺序",
         ["cat", str(tmp / "basic.txt"), "-"], stdin=b"tail\n")

    # ---------- 10. 错误路径 ----------
    show("文件不存在", ["cat", str(tmp / "nope.txt")])
    show("文件不存在不影响其余文件",
         ["cat", str(tmp / "nope.txt"), str(tmp / "basic.txt")])
    show("目录当操作数", ["cat", str(tmp / "sub")])

    # ---------- 11. 编码评分内部逻辑 ----------
    say("=== _text_score 内部逻辑 ===")
    sys.path.insert(0, str(ROOT))
    from w2l.commands.cat import _detect_encoding, _pick_encoding, _text_score

    gbk_bytes = "中文内容".encode("gb18030")
    say("gb18030 字节: %s" % " ".join("%02x" % b for b in gbk_bytes))
    for enc in ("utf-8", locale.getpreferredencoding(False), "gb18030", "latin-1"):
        try:
            text = gbk_bytes.decode(enc)
        except UnicodeDecodeError:
            say("  %-12s 解不出" % enc)
            continue
        say("  %-12s score=%.4f  %r" % (enc, _text_score(text), text))
    say("  判定结果 _pick_encoding = %r" % _pick_encoding(gbk_bytes))
    say("  判定结果 _detect_encoding = %r" % _detect_encoding(gbk_bytes))
    say()

    say("=== 候选编码顺序 ===")
    from w2l.commands.cat import _candidate_encodings

    say("  %r" % (_candidate_encodings(),))
    say()

    say("=== 高位字节文件的判定 ===")
    for name in ("high.bin", "ctrl.txt", "gbk.txt"):
        raw = (tmp / name).read_bytes()
        say("  %-10s _pick_encoding=%r" % (name, _pick_encoding(raw)))
    say()

    # ---------- 12. 与 GNU cat 对照 ----------
    say("=== 与 Git Bash 的 GNU cat 对照 ===")
    bash = r"E:\software\Git\Git\bin\bash.exe"
    if os.path.isfile(bash):
        pairs = [
            ("默认", ["cat", "basic.txt"]),
            ("-n", ["cat", "-n", "basic.txt"]),
            ("-b", ["cat", "-b", "blank.txt"]),
            ("-E", ["cat", "-E", "basic.txt"]),
            ("-T", ["cat", "-T", "tabs.txt"]),
            ("-s", ["cat", "-s", "blank.txt"]),
            ("-v ctrl", ["cat", "-v", "ctrl.txt"]),
            ("-v high", ["cat", "-v", "high.bin"]),
            ("-e ctrl", ["cat", "-e", "ctrl.txt"]),
            ("-A tabs", ["cat", "-A", "tabs.txt"]),
            ("CRLF", ["cat", "crlf.txt"]),
            ("noeol", ["cat", "noeol.txt"]),
            ("多文件 -n", ["cat", "-n", "basic.txt", "basic.txt"]),
        ]
        # bash 里的路径要用正斜杠，反斜杠在 bash 里是转义符
        tmp_bash = tmp.as_posix()
        for title, argv in pairs:
            gnu = subprocess.run(
                [bash, "-c", "cd %s && cat %s" % (tmp_bash, " ".join(argv[1:]))],
                capture_output=True,
            )
            ours = run(["cat", *argv[1:]], cwd=tmp)
            same = gnu.stdout == ours[1]
            say("  %-12s GNU=%r" % (title, gnu.stdout))
            say("  %-12s 本项目=%r" % ("", ours[1]))
            say("  %-12s 一致=%s" % ("", same))
            if gnu.returncode != 0:
                say("  %-12s GNU stderr=%r" % ("", gnu.stderr))
    else:
        say("  没找到 Git Bash，跳过对照")
    say()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes("\n".join(lines).encode("utf-8"))
    print()
    print("报告已写到 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
