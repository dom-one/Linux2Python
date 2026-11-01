"""探针：GNU cat 的 blank 判定规则、仓库 grep 的编码判定实测、stdout 换行行为。

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
GNU_CAT = shutil.which("cat") or r"E:\software\Git\Git\usr\bin\cat.exe"


def gnu(argv: list[str]) -> tuple[int, bytes, bytes]:
    proc = subprocess.run([GNU_CAT, *argv], capture_output=True)
    return proc.returncode, proc.stdout, proc.stderr


def show(title: str, argv: list[str]) -> None:
    code, out, err = gnu(argv)
    print("--- %s" % title)
    print("    argv=%r" % (argv,))
    print("    code=%d out=%r" % (code, out))
    print()


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="_t32_cat_", dir=str(DATA)))

    # blank 判定：空行 / 纯空格行 / 混合
    mix = tmp / "mix.txt"
    mix.write_bytes(b"a\n\n\nb\n")          # 两个连续空行
    ws2 = tmp / "ws2.txt"
    ws2.write_bytes(b"a\n  \n  \nb\n")      # 两个连续纯空格行
    ws1 = tmp / "ws1.txt"
    ws1.write_bytes(b"a\n  \n\nb\n")        # 空格行 + 空行
    tab1 = tmp / "tab1.txt"
    tab1.write_bytes(b"a\n\t\n\t\nb\n")      # 两个连续制表符行

    print("### blank definition for -s ###")
    show("-s two empty lines", ["-s", str(mix)])
    show("-s two whitespace-only lines", ["-s", str(ws2)])
    show("-s whitespace then empty", ["-s", str(ws1)])
    show("-s two tab-only lines", ["-s", str(tab1)])
    print()

    print("### blank definition for -b ###")
    show("-b two empty lines", ["-b", str(mix)])
    show("-b two whitespace-only lines", ["-b", str(ws2)])
    show("-b whitespace then empty", ["-b", str(ws1)])
    show("-b two tab-only lines", ["-b", str(tab1)])
    print()

    print("### -s + -b together ###")
    show("-sb", ["-sb", str(ws2)])
    show("-bs", ["-bs", str(ws2)])
    print()

    print("### -e alias and -A ###")
    basic = tmp / "basic.txt"
    basic.write_bytes(b"a\tb\n")
    show("-e", ["-e", str(basic)])
    show("-A", ["-A", str(basic)])
    show("-v only", ["-v", str(basic)])
    show("-ET", ["-ET", str(basic)])
    print()

    print("### repo grep encoding detection in practice ###")
    for label, data in (
        ("utf8", "中文内容\n".encode("utf-8")),
        ("gbk", "中文内容\n".encode("gb18030")),
        ("cp1252", "café au lait\n".encode("cp1252")),
        ("latin1", "café au lait\n".encode("latin-1")),
        ("utf8bom", b"\xef\xbb\xbfhello\n"),
        ("binary", b"\x00\x01\x02\xff\xfe\n"),
    ):
        f = tmp / ("enc_%s.bin" % label)
        f.write_bytes(data)
        proc = subprocess.run(
            [sys.executable, str(ROOT / "main.py"), "grep", "-a", "au", str(f)],
            capture_output=True,
        )
        print("  %-9s code=%d out=%r err=%r" % (label, proc.returncode, proc.stdout[:120], proc.stderr[:80]))
    print()

    print("### stdout newline translation inside repo cli ###")
    f = tmp / "nl.txt"
    f.write_bytes(b"one\ntwo\n")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "grep", "one", str(f)],
        capture_output=True,
    )
    print("  grep out bytes: %r" % proc.stdout)
    print()

    for path in sorted(tmp.rglob("*"), reverse=True):
        if path.is_dir():
            os.rmdir(path)
        else:
            path.unlink()
    os.rmdir(tmp)
    print("temp dir cleaned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
