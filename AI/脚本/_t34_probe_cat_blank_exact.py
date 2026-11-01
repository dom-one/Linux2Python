"""探针：定死 GNU cat 对「空行」的判定口径，以及行号列宽。

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


def gnu(argv: list[str]) -> bytes:
    proc = subprocess.run([GNU_CAT, *argv], capture_output=True)
    return proc.stdout


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="_t34_cat_", dir=str(DATA)))

    def make(name: str, data: bytes) -> str:
        p = tmp / name
        p.write_bytes(data)
        return str(p)

    variants = {
        "empty_line": b"a\n\nb\n",
        "space_line": b"a\n \nb\n",
        "tab_line": b"a\n\t\nb\n",
        "cr_line": b"a\n\r\nb\n",
        "vtab_line": b"a\n\v\nb\n",
        "mixed_ws": b"a\n \t \nb\n",
        "trailing_space": b"a\n   \nb\n",
    }

    print("### -b: which lines get numbers? ###")
    for label, data in variants.items():
        path = make("b_%s.txt" % label, data)
        out = gnu(["-b", path])
        print("  %-15s in=%-22r out=%r" % (label, data, out))
    print()

    print("### -s: which lines get squeezed? ###")
    for label, data in variants.items():
        path = make("s_%s.txt" % label, data)
        out = gnu(["-s", path])
        print("  %-15s in=%-22r out=%r" % (label, data, out))
    print()

    print("### -n: numbering width for 1..12 ###")
    many = make("many.txt", b"".join(b"l%d\n" % i for i in range(1, 13)))
    out = gnu(["-n", many])
    print("  out=%r" % out)
    print()

    print("### -n: width for 100..101 ###")
    big = make("big.txt", b"".join(b"l%d\n" % i for i in range(99, 102)))
    out = gnu(["-n", big])
    print("  out=%r" % out)
    print()

    print("### -b counter: does a blank line consume a number? ###")
    seq = make("seq.txt", b"a\n\nb\n\nc\n")
    print("  -b  out=%r" % gnu(["-b", seq]))
    print("  -n  out=%r" % gnu(["-n", seq]))
    print()

    print("### -v: M- notation variants ###")
    for label, data in {
        "0x80": b"\x80",
        "0x9f": b"\x9f",
        "0xa0": b"\xa0",
        "0xff": b"\xff",
        "0x01": b"\x01",
        "0x1b": b"\x1b",
        "0x7f": b"\x7f",
        "tab": b"\t",
    }.items():
        print("  %-6s -> %r" % (label, gnu(["-v", make("v_%s.bin" % label, data)])))
    print()

    print("### -A on high byte + tab ###")
    print("  %r" % gnu(["-A", make("a1.bin", b"\x80\t\n")]))
    print()

    print("### -e equals -E? ###")
    e = make("e.txt", b"a\tb\n")
    print("  -e %r" % gnu(["-e", e]))
    print("  -E %r" % gnu(["-E", e]))
    print()

    print("### -s with 3 consecutive blank lines ###")
    print("  %r" % gnu(["-s", make("s3.txt", b"a\n\n\n\nb\n")]))
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
