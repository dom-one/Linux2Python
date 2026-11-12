"""清理探针留下的大文件。

背景：ctypes 的 SetFilePointerEx + SetEndOfFile 在 E 盘上并没有生成稀疏文件，
大尺寸的探针语料实打实占了磁盘（AI/数据 一度到 14 GB）。

这里只删探针生成的 .bin 语料，probe_out.txt / diff_out.txt 这些结果文件保留。
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "AI" / "数据"

KEEP_SUFFIXES = (".txt",)


def main() -> int:
    removed = 0
    freed = 0
    for path in sorted(DATA.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() in KEEP_SUFFIXES:
            continue
        size = path.stat().st_size
        path.unlink()
        removed += 1
        freed += size
        print(f"删除 {path.relative_to(ROOT)}  ({size} 字节)")

    # 空目录一并清掉
    for path in sorted(DATA.rglob("*"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass

    print(f"共删除 {removed} 个文件，名义体积 {freed / 1024**3:.2f} GB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
