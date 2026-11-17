"""生成 find 教程里 -delete 那一步用的可丢弃小目录。

每次运行都重建，重复跑教程不会出错。

用法:
    python AI/脚本/_t707_make_delete_demo.py
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DEMO = Path(ROOT) / "AI" / "数据" / "find_delete_demo"

FILES = [
    ("keep.txt", b"keep\n"),
    ("drop.tmp", b"drop\n"),
    ("sub/keep2.txt", b"keep2\n"),
    ("sub/drop2.tmp", b"drop2\n"),
]


def main() -> None:
    if DEMO.exists():
        shutil.rmtree(DEMO)
    DEMO.mkdir(parents=True)
    for rel, content in FILES:
        target = DEMO / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    print("已生成 AI/数据/find_delete_demo/（4 个文件）")


if __name__ == "__main__":
    main()
