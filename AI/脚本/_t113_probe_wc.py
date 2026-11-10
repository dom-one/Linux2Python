"""wc 教程的取证脚本：把要写进文档的行为逐条实测一遍。

产出 AI/数据/_t113_wc_probe.txt，纯文本、可直接读。
只读项目源码 + 在临时目录造语料，不改项目文件。
"""

import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from w2l.commands.wc import (  # noqa: E402
    _count_words,
    _detect_encoding,
    _display_width,
    _pick_encoding,
    _split_lines,
    _text_score,
)
from w2l.context import RunContext  # noqa: E402
from w2l.commands.wc import build_parser, wc  # noqa: E402

OUT = ROOT / "AI" / "数据" / "_t113_wc_probe.txt"

lines_out: list[str] = []


def emit(text=""):
    lines_out.append(text)


def run(argv, cwd=None, stdin_text="", use_bytes_stdin=False):
    namespace = build_parser().parse_args(list(argv))
    out, err = io.StringIO(), io.StringIO()
    stdin = io.BytesIO(stdin_text.encode("utf-8")) if use_bytes_stdin else io.StringIO(stdin_text)
    ctx = RunContext(cwd=Path(cwd), stdout=out, stderr=err, stdin=stdin)
    code = wc(namespace, ctx)
    return code, out.getvalue(), err.getvalue()


def show(title, argv, cwd=None, stdin_text="", use_bytes_stdin=False):
    code, out, err = run(argv, cwd=cwd, stdin_text=stdin_text, use_bytes_stdin=use_bytes_stdin)
    emit(f"### {title}")
    emit(f"$ python main.py wc {' '.join(argv)}")
    emit(f"exit={code}")
    emit(f"stdout={out!r}")
    emit(f"stderr={err!r}")
    emit()


def main():
    tmp = Path(tempfile.mkdtemp(prefix="wcprobe_"))
    emit(f"临时语料目录: {tmp}")
    emit()

    (tmp / "one.txt").write_bytes(b"x\n")
    (tmp / "two.txt").write_bytes(b"a b\nc\n")
    (tmp / "empty.txt").write_bytes(b"")
    (tmp / "noeol.txt").write_bytes(b"a\nb")
    (tmp / "crlf.txt").write_bytes(b"c1\r\nc2\r\n")
    (tmp / "tab.txt").write_bytes(b"a\tb\tc\n")
    (tmp / "big.txt").write_bytes(b"y" * 99 + b"\n")
    (tmp / "bin.dat").write_bytes(b"\x00\x01\x02\xff\xfe\n")
    (tmp / "long.txt").write_bytes(b"x" * 19 + b"\n")
    (tmp / "short.txt").write_bytes(b"z\n")
    (tmp / "cjk.txt").write_bytes("中文\n".encode("utf-8"))
    (tmp / "mix.txt").write_bytes(b"a\x01b\n")
    (tmp / "nonprint.txt").write_bytes(b"\x01\x02\n")
    (tmp / "sub").mkdir()
    (tmp / "gbk.txt").write_bytes("中文内容\n".encode("gb18030"))

    emit("=== 1. 默认三列 / 各选项单列 ===")
    show("默认（行 词 字节）", ["one.txt"], cwd=tmp)
    show("-l", ["-l", "one.txt"], cwd=tmp)
    show("-w", ["-w", "two.txt"], cwd=tmp)
    show("-c", ["-c", "two.txt"], cwd=tmp)
    show("-m", ["-m", "cjk.txt"], cwd=tmp)
    show("-L", ["-L", "tab.txt"], cwd=tmp)

    emit("=== 2. 列序固定，与选项书写顺序无关 ===")
    show("-lwc", ["-lwc", "one.txt"], cwd=tmp)
    show("-clw", ["-clw", "one.txt"], cwd=tmp)
    show("-lwc -m -L", ["-lwc", "-m", "-L", "one.txt"], cwd=tmp)

    emit("=== 3. 行只按 \\n 计 ===")
    show("末行无换行 noeol.txt", ["-lwc", "noeol.txt"], cwd=tmp)
    show("CRLF crlf.txt", ["-lwc", "crlf.txt"], cwd=tmp)

    emit("=== 4. 词的判定 ===")
    show("二进制 bin.dat", ["-lw", "bin.dat"], cwd=tmp)
    show("片段夹控制字符 mix.txt", ["-lw", "mix.txt"], cwd=tmp)
    show("整片段无 Printable nonprint.txt", ["-lw", "nonprint.txt"], cwd=tmp)

    emit("=== 5. total 行 ===")
    show("多文件 -lwc", ["-lwc", "one.txt", "two.txt"], cwd=tmp)
    show("最长行取最大 -L", ["-L", "long.txt", "short.txt"], cwd=tmp)

    emit("=== 6. 标准输入 ===")
    show("不给操作数", [], cwd=tmp, stdin_text="a b\nc\n")
    show("操作数 -", ["-lwc", "-"], cwd=tmp, stdin_text="a b\nc\n")
    show("重复的 -", ["-lw", "-", "-"], cwd=tmp, stdin_text="a b\nc\n")

    emit("=== 7. 列宽模型 ===")
    show("两列 + total", ["-lwc", "one.txt", "big.txt"], cwd=tmp)
    show("只一列不打 total（不对齐）", ["-l", "big.txt"], cwd=tmp)
    show("只一列但打 total", ["-l", "one.txt", "big.txt"], cwd=tmp)
    show("stdin 参与：预留 7 列", ["-lwc", "-"], cwd=tmp, stdin_text="a b\nc\n")
    show("stdin + 普通文件", ["-lwc", "one.txt", "-"], cwd=tmp, stdin_text="a b\nc\n")

    emit("=== 8. 错误路径 ===")
    show("缺文件", ["-l", "nope.txt"], cwd=tmp)
    show("缺文件不影响其它文件", ["-lwc", "one.txt", "nope.txt"], cwd=tmp)
    show("目录", ["-lwc", "sub"], cwd=tmp)

    emit("=== 9. GBK 文件的 -m / -L ===")
    show("gbk.txt -lwc", ["-lwc", "gbk.txt"], cwd=tmp)
    show("gbk.txt -m", ["-m", "gbk.txt"], cwd=tmp)
    show("gbk.txt -L", ["-L", "gbk.txt"], cwd=tmp)
    show("gbk.txt -w", ["-w", "gbk.txt"], cwd=tmp)

    emit("=== 10. 内部函数实测 ===")
    emit(f"_pick_encoding(b'中文内容\\n'.encode('gb18030')) = {_pick_encoding('中文内容\n'.encode('gb18030'))!r}")
    emit(f"_pick_encoding(b'\\x00\\x01') = {_pick_encoding(b'\\x00\\x01')!r}")
    emit(f"_pick_encoding(b'hello\\n') = {_pick_encoding(b'hello\n')!r}")
    emit(f"_detect_encoding(gbk 字节) = {_detect_encoding('中文内容\n'.encode('gb18030'))!r}")
    emit(f"_detect_encoding(utf8 字节) = {_detect_encoding('中文内容\n'.encode('utf-8'))!r}")
    emit(f"_text_score('中文内容') = {_text_score('中文内容')!r}")
    emit(f"_text_score('hello world') = {_text_score('hello world')!r}")
    emit(f"_text_score(gbk 被 cp1252 解出的乱码) = {_text_score('中文内容\n'.encode('gb18030').decode('cp1252'))!r}")
    emit(f"_count_words('a\\x01b') = {_count_words('a\\x01b')}")
    emit(f"_count_words('a b') = {_count_words('a b')}")
    emit(f"_count_words('中文') = {_count_words('中文')}")
    emit(f"_display_width('a\\tb\\tc') = {_display_width('a\tb\tc')}")
    emit(f"_display_width('中文') = {_display_width('中文')}")
    emit(f"_display_width('x'*19) = {_display_width('x'*19)}")
    emit(f"_display_width('c1\\rc2') = {_display_width('c1\rc2')}")
    emit("_split_lines(b'a\\nb') = " + repr(list(_split_lines(iter([b'a\nb']))) ))
    emit("_split_lines(b'a\\nb\\n') = " + repr(list(_split_lines(iter([b'a\nb\n']))) ))
    emit()

    emit("=== 11. 与 Git Bash 的 GNU wc 对照（若可用） ===")
    bash = None
    for cand in ("C:/Program Files/Git/bin/bash.exe", "C:/Program Files/Git/usr/bin/bash.exe"):
        if Path(cand).exists():
            bash = cand
            break
    if bash:
        for args in (["one.txt"], ["-lwc", "one.txt", "two.txt"], ["-L", "tab.txt"], ["-lw", "bin.dat"]):
            proc = subprocess.run(
                [bash, "-lc", "wc " + " ".join(args)],
                cwd=str(tmp),
                capture_output=True,
            )
            emit(f"GNU wc {' '.join(args)} -> {proc.stdout!r}")
    else:
        emit("未找到 Git Bash，跳过 GNU 对照")

    emit()
    emit(f"=== 12. 项目自身文件的实测 ===")
    for f in ("w2l/commands/wc.py", "README.md", "AGENTS.md"):
        p = ROOT / f
        code, out, err = run(["-lwc", f], cwd=ROOT)
        emit(f"{f}: exit={code} stdout={out!r}")
    code, out, err = run(["-lwc"], cwd=ROOT, stdin_text="")
    emit(f"空 stdin 无操作数: exit={code} stdout={out!r}")

    OUT.write_text("\n".join(lines_out), encoding="utf-8")
    print(f"written {OUT}")


if __name__ == "__main__":
    main()
