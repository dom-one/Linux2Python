"""探针：记录 GNU cat 8.32 的实测行为，作为实现 cat 指令的对照基准。

只读为主：仅在 AI/数据/ 下建临时目录，不碰仓库源码。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "AI" / "数据"
# MSYS 的 /usr/bin 路径在 Windows 上不存在，必须用 which 取真实可执行路径。
GNU_CAT = shutil.which("cat") or r"E:\software\Git\Git\usr\bin\cat.exe"


def run(argv: list[str], cwd: Path | None = None, stdin: bytes = b"") -> tuple[int, bytes, bytes]:
    proc = subprocess.run(
        [GNU_CAT, *argv],
        cwd=str(cwd or ROOT),
        input=stdin,
        capture_output=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def show(title: str, argv: list[str], cwd: Path | None = None, stdin: bytes = b"") -> None:
    code, out, err = run(argv, cwd, stdin)
    print("=== %s ===" % title)
    print("命令: cat %s" % " ".join(argv))
    print("退出码: %d" % code)
    print("stdout: %r" % out)
    print("stderr: %r" % err)
    print()


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="_t30_cat_", dir=str(DATA)))

    basic = tmp / "basic.txt"
    basic.write_bytes(b"alpha\nbeta\ngamma\n")

    blank = tmp / "blank.txt"
    blank.write_bytes(b"one\n\n\n\ntwo\n")

    mixed = tmp / "mixed.txt"
    mixed.write_bytes(b"a\n\tb\n\nc\n")

    tabs = tmp / "tabs.txt"
    tabs.write_bytes(b"col1\tcol2\n")

    noeol = tmp / "noeol.txt"
    noeol.write_bytes(b"last line no newline")

    crlf = tmp / "crlf.txt"
    crlf.write_bytes(b"line1\r\nline2\r\n")

    empty = tmp / "empty.txt"
    empty.write_bytes(b"")

    utf8 = tmp / "utf8.txt"
    utf8.write_bytes("中文内容\n第二行\n".encode("utf-8"))

    gbk = tmp / "gbk.txt"
    gbk.write_bytes("中文内容\n".encode("gb18030"))

    ctrl = tmp / "ctrl.txt"
    ctrl.write_bytes(b"bell\x07 del\x7f esc\x1b\n")

    sub = tmp / "sub"
    sub.mkdir()

    show("默认输出", [str(basic)])
    show("-n 行号", ["-n", str(basic)])
    show("-n 多行（看编号列宽）", ["-n", str(blank)])
    show("-b 只给非空行编号", ["-b", str(blank)])
    show("-b 与 -n 同开", ["-bn", str(blank)])
    show("-s 压缩空行", ["-s", str(blank)])
    show("-E 显示行尾 $", ["-E", str(basic)])
    show("-T 制表符显示为 ^I", ["-T", str(tabs)])
    show("-A 等价 -vET", ["-A", str(mixed)])
    show("-v 非打印字符", ["-v", str(ctrl)])
    show("-v 对 UTF-8 中文", ["-v", str(utf8)])
    show("无结尾换行", [str(noeol)])
    show("CRLF 原样输出", [str(crlf)])
    show("空文件", [str(empty)])
    show("多文件拼接", [str(basic), str(blank)])
    show("文件不存在", [str(tmp / "nope.txt")])
    show("文件不存在 + 正常文件", [str(tmp / "nope.txt"), str(basic)])
    show("目录作为操作数", [str(sub)])
    show("无操作数读 stdin", [], stdin=b"from stdin\n")
    show("操作数 - 读 stdin", ["-"], stdin=b"from stdin\n")
    show("stdin + -n", ["-n"], stdin=b"one\ntwo\n")
    show("-s 对 stdin", ["-s"], stdin=b"a\n\n\n\nb\n")
    show("-- 之后视为文件名", ["--", str(basic)])
    show("不支持的选项", ["-Z", str(basic)])

    print("=== 编码对照 ===")
    for name in ("utf8.txt", "gbk.txt"):
        code, out, err = run([str(tmp / name)])
        print("%s: code=%d out=%r err=%r" % (name, code, out, err))
    print()

    print("=== 组合优先级：-n -b 同开时谁赢 ===")
    code, out, err = run(["-n", "-b", str(blank)])
    print("code=%d out=%r" % (code, out))
    code, out, err = run(["-b", "-n", str(blank)])
    print("code=%d out=%r" % (code, out))
    print()

    print("=== -n 与 -E 同开 ===")
    code, out, err = run(["-nE", str(basic)])
    print("code=%d out=%r" % (code, out))
    print()

    print("=== 超过 6 位的行号 ===")
    big = tmp / "big.txt"
    big.write_bytes(b"".join(b"line%d\n" % i for i in range(1, 11)))
    code, out, err = run(["-n", str(big)])
    print("code=%d out=%r" % (code, out))
    print()

    for path in sorted(tmp.rglob("*"), reverse=True):
        if path.is_dir():
            os.rmdir(path)
        else:
            path.unlink()
    os.rmdir(tmp)
    print("临时目录已清理: %s" % tmp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
