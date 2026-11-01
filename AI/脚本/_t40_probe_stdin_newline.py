"""探针：sys.stdin 在 Windows 上读文本时会不会把 CRLF 归一成 LF。

只读：不修改仓库源码。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "_t40_probe_stdin_child.py"


def child() -> None:
    data = sys.stdin.read()
    sys.stdout.write(repr(data) + "\n")
    sys.stdout.flush()


def main() -> int:
    payload = b"a\r\nb\rc\n"
    for label, code in (
        ("plain read", "import sys; sys.stdout.write(repr(sys.stdin.read()))"),
        ("buffer read", "import sys; sys.stdout.write(repr(sys.stdin.buffer.read()))"),
    ):
        proc = subprocess.run(
            [sys.executable, "-c", code],
            input=payload,
            capture_output=True,
        )
        print("%-14s -> %r" % (label, proc.stdout))

    print()
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=payload,
        capture_output=True,
    )
    print("child script  -> %r" % proc.stdout)
    print("input payload -> %r" % payload)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        child()
    else:
        sys.exit(main())
