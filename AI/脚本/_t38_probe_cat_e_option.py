"""探针：GNU cat 的 -e 与 -E 到底差在哪。

只读：仅在 AI/数据/ 下建临时目录，不碰仓库源码。
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
    tmp = Path(tempfile.mkdtemp(prefix="_t38_e_", dir=str(DATA)))

    def make(name: str, data: bytes) -> str:
        p = tmp / name
        p.write_bytes(data)
        return str(p)

    cases = {
        "lf": b"a\n",
        "crlf": b"a\r\n",
        "cr_only": b"a\rb\n",
        "ctrl01": b"a\x01b\n",
        "tab": b"a\tb\n",
        "del": b"a\x7fb\n",
        "high": b"a\x80b\n",
        "esc": b"a\x1bb\n",
        "bel": b"a\x07b\n",
        "vtab": b"a\x0bb\n",
    }

    print("%-10s %-14s %-14s %-14s %-14s" % ("case", "-E", "-e", "-v", "-A"))
    for label, data in cases.items():
        path = make("%s.bin" % label, data)
        print("%-10s %-14r %-14r %-14r %-14r" % (
            label,
            gnu(["-E", path]),
            gnu(["-e", path]),
            gnu(["-v", path]),
            gnu(["-A", path]),
        ))
    print()

    print("### -e 与其他选项组合 ###")
    path = make("crlf.bin", b"a\r\n")
    for opts in (["-e", "-n"], ["-E", "-n"], ["-e", "-T"], ["-e", "-s"], ["-e", "-b"]):
        print("  %-12s -> %r" % (" ".join(opts), gnu([*opts, path])))
    print()

    print("### -e 对高位的处理（是否等价 -v）###")
    hi = make("hi.bin", b"a\x80b\n")
    for opts in (["-e"], ["-v"], ["-E"], ["-vE"], ["-e", "-T"]):
        print("  %-10s -> %r" % (" ".join(opts), gnu([*opts, hi])))
    print()

    print("### -e 是否隐含 -T（制表符）###")
    tb = make("tb.bin", b"a\tb\n")
    for opts in (["-e"], ["-E"], ["-T"], ["-v"], ["-A"]):
        print("  %-6s -> %r" % (" ".join(opts), gnu([*opts, tb])))
    print()

    for p in sorted(tmp.rglob("*"), reverse=True):
        if p.is_dir():
            os.rmdir(p)
        else:
            p.unlink()
    os.rmdir(tmp)
    print("temp dir cleaned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
