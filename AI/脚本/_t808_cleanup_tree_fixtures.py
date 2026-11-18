"""清掉 tree 探针留下的临时夹具。

tree_edge（含目录联接）与 tree_junction（自引用联接）留着会污染
「在仓库根目录跑 tree」的结果，自引用联接还会让 tree 递归 64 层。
这两个是探针产物，不是教程夹具，删掉。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = Path(os.path.dirname(os.path.dirname(HERE)))
DATA = ROOT / "AI" / "数据"

# 这些目录里可能含目录联接（junction），先摘掉再删
JUNCTIONS = [
    DATA / "tree_edge" / "link_to_sub",
    DATA / "tree_junction" / "selfref" / "loop",
]

TARGETS = ["tree_edge", "tree_junction"]


def main() -> None:
    for link in JUNCTIONS:
        if link.exists():
            subprocess.run(["cmd", "/c", "rmdir", str(link)], capture_output=True)
            print(f"  摘掉联接 {link}")
    for name in TARGETS:
        target = DATA / name
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            print(f"  删除 {target}")
    print("清理完成")


if __name__ == "__main__":
    main()
