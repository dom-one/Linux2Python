#!/usr/bin/env python
"""从备份恢复被改坏的指令文件。"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BACKUP = HERE.parent / "数据" / "enc_backup"

FILES = ["head.py", "tail.py", "wc.py", "sed.py", "awk_lite.py"]


def main() -> int:
    for name in FILES:
        src = BACKUP / name
        dst = ROOT / "w2l" / "commands" / name
        shutil.copy2(src, dst)
        print(f"[恢复] {name} <- {src} ({dst.stat().st_size} 字节)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
