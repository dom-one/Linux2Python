"""生成 find 教程用的固定夹具。

夹具落在 AI/数据/find_demo/（该目录在 .gitignore 里，不进仓库）。
内容与大小固定，教程里的预期输出不会随源码改动而过期。

用法:
    python AI/脚本/_t700_make_find_demo.py
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DEMO = Path(ROOT) / "AI" / "数据" / "find_demo"

# (相对路径, 字节内容, mtime 偏移秒数)
# mtime 偏移 0 表示「保持当前时间」，负数表示「往前推」。
FILES = [
    ("a.txt", b"hello\n", 0),
    ("B.txt", b"upper\n", 0),
    ("notes.md", b"# t\n", 0),
    ("empty.log", b"", 0),
    (".hidden", b"x\n", 0),
    ("old.txt", b"old\n", -10 * 86400),
    ("big.bin", b"X" * 2000, 0),
    ("sub/deep.txt", b"deep\n", 0),
    ("sub/code.py", b"print(1)\n", 0),
    ("sub2/nested.txt", b"nested\n", 0),
]

DIRS = [
    "sub",
    "sub/empty_dir",
    "sub2",
]


def main() -> None:
    if DEMO.exists():
        shutil.rmtree(DEMO)
    DEMO.mkdir(parents=True)

    for rel in DIRS:
        (DEMO / rel).mkdir(parents=True, exist_ok=True)

    now = time.time()
    for rel, content, offset in FILES:
        target = DEMO / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        if offset:
            stamp = now + offset
            os.utime(target, (stamp, stamp))

    total = sum(1 for _ in DEMO.rglob("*")) + 1
    print(f"已生成 AI/数据/find_demo/（{total} 个条目）")


if __name__ == "__main__":
    main()
