"""探针子进程：把 0-255 的字节经 surrogateescape 写进 stdout。

配合 _t43_probe_surrogate.py 使用。
"""

from __future__ import annotations

import sys


def main() -> int:
    data = bytes(range(256))
    text = data.decode("utf-8", errors="surrogateescape")
    sys.stdout.reconfigure(encoding="utf-8", errors="surrogateescape", newline="")
    sys.stdout.write(text)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
