"""探针：GNU cat 的 -E 末行行为、-s/-b 与 CRLF 的关系、-v 的字节规则。

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
    tmp = Path(tempfile.mkdtemp(prefix="_t33_cat_", dir=str(DATA)))

    def make(name: str, data: bytes) -> str:
        p = tmp / name
        p.write_bytes(data)
        return str(p)

    print("### -E on final line without newline ###")
    show("-E single line no eol", ["-E", make("e1.txt", b"abc")])
    show("-E two lines no eol", ["-E", make("e2.txt", b"abc\ndef")])
    show("-E trailing eol", ["-E", make("e3.txt", b"abc\n")])
    show("-E CRLF no final eol", ["-E", make("e4.txt", b"abc\r\ndef")])
    print()

    print("### -T / -v on final line without newline ###")
    show("-T no eol", ["-T", make("t1.txt", b"a\tb")])
    show("-v no eol", ["-v", make("v1.txt", b"a\x01b")])
    print()

    print("### CRLF blank lines: is a lone CR blank? ###")
    crlf_blank = make("cb.txt", b"a\r\n\r\n\r\nb\r\n")
    show("-b on CRLF with blank lines", ["-b", crlf_blank])
    show("-s on CRLF with blank lines", ["-s", crlf_blank])
    show("-n on CRLF with blank lines", ["-n", crlf_blank])
    crlf_one = make("co.txt", b"a\r\n\r\nb\r\n")
    show("-s CRLF one blank line", ["-s", crlf_one])
    print()

    print("### lone CR (old mac) line endings ###")
    cr = make("cr.txt", b"a\rb\nc\n")
    show("-n on lone CR", ["-n", cr])
    show("-E on lone CR", ["-E", cr])
    print()

    print("### -n + -s combination ordering ###")
    mix = make("mix.txt", b"a\n\n\nb\n")
    show("-n -s", ["-n", "-s", mix])
    show("-s -n", ["-s", "-n", mix])
    show("-n -b -s", ["-n", "-b", "-s", mix])
    print()

    print("### -v byte rules ###")
    show("-v on 0x00/0x1f/0x7f", ["-v", make("c1.bin", b"\x00\x1f\x7f")])
    show("-v on 0x80/0xa0/0xff", ["-v", make("c2.bin", b"\x80\xa0\xff")])
    show("-A on 0x80", ["-A", make("c3.bin", b"\x80\n")])
    print()

    print("### -s across stdin boundary ###")
    proc = subprocess.run(
        [GNU_CAT, "-s", make("sa.txt", b"x\n\n")],
        input=b"\ny\n",
        capture_output=True,
    )
    print("  file(stdin) out=%r" % proc.stdout)
    proc = subprocess.run(
        [GNU_CAT, "-s", "-"],
        input=b"p\n\n\nq\n",
        capture_output=True,
    )
    print("  stdin only out=%r" % proc.stdout)
    print()

    print("### does -n counter restart per file? ###")
    a = make("a.txt", b"A\n")
    b = make("b.txt", b"B\n")
    show("-n two files", ["-n", a, b])
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
