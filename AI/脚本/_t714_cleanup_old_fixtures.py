"""清理：删掉 wc 那几轮遗留的大夹具文件。

AI/脚本/_data_wc* 是 2026-11-08~09 的 wc tick 留下的夹具，
里面有 1GB / 100MB 级的假文件，AI/ 目录被撑到 3.4 GB。
这些目录已被 .gitignore 忽略（AI/脚本/_data_*/），删掉不影响仓库。

只删 10MB 以上的大文件，小文件留着（可能是脚本还要用的）。
结果打印到终端。
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
SCRIPT_DIR = HERE
THRESHOLD = 10 * 1024 * 1024


def main() -> int:
    removed = 0
    freed = 0
    for pattern in ("_data_wc*", "_data_find*", "_data_sed*", "_data_tail*"):
        for directory in SCRIPT_DIR.glob(pattern):
            if not directory.is_dir():
                continue
            for item in directory.rglob("*"):
                if not item.is_file():
                    continue
                try:
                    size = item.stat().st_size
                except OSError:
                    continue
                if size < THRESHOLD:
                    continue
                try:
                    item.unlink()
                except OSError as exc:
                    print(f"  删不掉 {item}: {exc}")
                    continue
                removed += 1
                freed += size
    print(f"删掉 {removed} 个大文件，释放 {freed / 1024 / 1024:.0f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
