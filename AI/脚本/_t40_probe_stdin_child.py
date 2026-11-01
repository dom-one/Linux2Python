"""探针子进程：把 stdin 原样读出来并 repr 打印。

配合 _t40_probe_stdin_newline.py 使用。
"""

from __future__ import annotations

import sys


def main() -> int:
    data = sys.stdin.read()
    sys.stdout.write(repr(data) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
