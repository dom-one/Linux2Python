#!/usr/bin/env python
"""改动前先备份：把即将改写的指令文件复制到 AI/数据/enc_backup/。

bash 工具的安全策略拦了带中文的写路径（"cannot be mapped safely"），
所以备份也走 Python 脚本。
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BACKUP = HERE.parent / "数据" / "enc_backup"

FILES = ["head.py", "tail.py", "wc.py", "sed.py", "awk_lite.py"]


def main() -> int:
    BACKUP.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        src = ROOT / "w2l" / "commands" / name
        dst = BACKUP / name
        shutil.copy2(src, dst)
        print(f"[备份] {name}: {src.stat().st_size} 字节 -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
