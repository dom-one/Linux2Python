"""生成 find 教程里 -mmin 那一步用的「刚创建」的文件。

文件的 mtime 就是当前时间。GNU findutils 4.10 的 -mmin 把「当前这一分钟」
算作第 1 分钟，所以刚建的文件落在 -mmin 1 而不是 -mmin 0。

用法:
    python AI/脚本/_t708_make_mtime_demo.py
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DEMO = Path(ROOT) / "AI" / "数据" / "find_mtime_demo"


def main() -> None:
    if DEMO.exists():
        shutil.rmtree(DEMO)
    DEMO.mkdir(parents=True)
    (DEMO / "just_now.txt").write_bytes(b"now\n")
    print("已生成 AI/数据/find_mtime_demo/just_now.txt（mtime = 当前时间）")


if __name__ == "__main__":
    main()
