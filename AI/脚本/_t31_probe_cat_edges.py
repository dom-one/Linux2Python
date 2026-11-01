"""探针：GNU cat 8.32 的边界行为与 Python stdout 换行行为。

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


def run(argv: list[str], stdin: bytes = b"") -> tuple[int, bytes, bytes]:
    proc = subprocess.run([GNU_CAT, *argv], input=stdin, capture_output=True)
    return proc.returncode, proc.stdout, proc.stderr


def show(title: str, argv: list[str], stdin: bytes = b"") -> None:
    code, out, err = run(argv, stdin)
    print("=== %s ===" % title)
    print("argv: %r" % (argv,))
    print("code: %d  stdout: %r" % (code, out))
    if err:
        print("stderr: %r" % err)
    print()


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="_t31_cat_", dir=str(DATA)))

    # 只含空格的行：判断 -s / -b 认不认它是 blank
    ws = tmp / "ws.txt"
    ws.write_bytes(b"one\n   \ntwo\n")

    crlf = tmp / "crlf.txt"
    crlf.write_bytes(b"l1\r\nl2\r\n")

    noeol = tmp / "noeol.txt"
    noeol.write_bytes(b"one\ntwo")

    a = tmp / "a.txt"
    a.write_bytes(b"A1\nA2\n")
    b = tmp / "b.txt"
    b.write_bytes(b"B1\nB2\n")

    # 跨文件的空行：a 结尾空行 + b 开头空行
    ea = tmp / "ea.txt"
    ea.write_bytes(b"x\n\n")
    eb = tmp / "eb.txt"
    eb.write_bytes(b"\ny\n")

    print("### blank-line definition ###")
    show("-s with whitespace-only line", ["-s", str(ws)])
    show("-b with whitespace-only line", ["-b", str(ws)])
    show("-n with whitespace-only line", ["-n", str(ws)])
    print()

    print("### CRLF ###")
    show("-n on CRLF", ["-n", str(crlf)])
    show("-E on CRLF", ["-E", str(crlf)])
    show("-b on CRLF", ["-b", str(crlf)])
    print()

    print("### last line without newline ###")
    show("-n on no-eol file", ["-n", str(noeol)])
    show("-E on no-eol file", ["-E", str(noeol)])
    show("-s on no-eol file", ["-s", str(noeol)])
    print()

    print("### multi-file ###")
    show("-n across two files (numbering continuity)", ["-n", str(a), str(b)])
    show("-b across two files", ["-b", str(a), str(b)])
    show("-s across two files (blank at boundary)", ["-s", str(ea), str(eb)])
    show("-n across two files, second lacks eol", ["-n", str(a), str(noeol)])
    print()

    print("### stdin placement ###")
    show("file then -", [str(a), "-"], stdin=b"FROM-STDIN\n")
    show("- then file", ["-", str(a)], stdin=b"FROM-STDIN\n")
    print()

    print("### -v notation rules (byte level, reference only) ###")
    hi = tmp / "hi.bin"
    hi.write_bytes(b"\x80\xff\x01\n")
    show("-v on high bytes", ["-v", str(hi)])
    print()

    print("### python stdout newline behaviour on this box ###")
    probe = tmp / "probe.py"
    probe.write_bytes(
        b"import sys\n"
        b"print('stdout newline:', repr(getattr(sys.stdout, 'newlines', None)))\n"
        b"w = getattr(sys.stdout, 'write', None)\n"
        b"sys.stdout.buffer.write(b'RAW\\n')\n"
        b"sys.stdout.write('TEXT\\n')\n"
        b"sys.stdout.flush()\n"
        b"sys.stderr.write('STDERR\\n')\n"
    )
    proc = subprocess.run([sys.executable, str(probe)], capture_output=True)
    print("stdout bytes: %r" % proc.stdout)
    print("stderr bytes: %r" % proc.stderr)
    print()

    for path in sorted(tmp.rglob("*"), reverse=True):
        if path.is_dir():
            os.rmdir(path)
        else:
            path.unlink()
    os.rmdir(tmp)
    print("temp dir cleaned: %s" % tmp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
