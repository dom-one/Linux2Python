"""造 du 教程用的固定夹具，落在 AI/数据/du_demo/（gitignore 目录）。

字节数刻意选在 1024 的边界两侧，与 tests/test_du.py 的 tree fixture 一致：
a.txt 10、b.txt 2048、c.txt 100、zero.txt 0、sub/d.txt 5、sub/deeper/e.txt 4096。
合计 6259 字节。

为什么要固定夹具：
预期输出不能凭印象写。源码当示例的预期输出必然随源码改动过期，
用一次性生成的固定夹具，预期输出从此不会过期。

为什么要钉死 mtime：
带 --time 的示例输出里要出现时间戳，不钉死的话每次跑都不一样，
教程里的预期输出块就永远对不上。

夹具每次全量重建（先删后建），保证目录 mtime 不被上一轮的操作带偏。
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "du_demo"

# 相对路径 -> 字节数
LAYOUT = {
    "tree/a.txt": 10,
    "tree/b.txt": 2048,
    "tree/c.txt": 100,
    "tree/zero.txt": 0,
    "tree/sub/d.txt": 5,
    "tree/sub/deeper/e.txt": 4096,
}
EMPTY_DIRS = ["tree/empty"]

# 相对路径 -> (年, 月, 日, 时, 分)
# 目录的 mtime 要比它里面的文件新，--time 的输出才看得出「取子树最新」这条规则
# —— 除了 tree/sub/deeper/e.txt：它的 mtime 比自己的父目录 tree/sub/deeper 还晚，
# 这样那一行就能直接看出目录行取的是「子树里最新的」而不是「目录自己的」。
MTIMES = {
    "tree/a.txt": (2024, 1, 15, 10, 30),
    "tree/b.txt": (2024, 2, 20, 14, 5),
    "tree/c.txt": (2024, 3, 25, 9, 0),
    "tree/zero.txt": (2024, 4, 30, 16, 45),
    "tree/sub/d.txt": (2024, 6, 10, 8, 20),
    "tree/sub/deeper/e.txt": (2024, 7, 16, 10, 0),
    "tree/empty": (2024, 5, 5, 11, 0),
    "tree/sub/deeper": (2024, 7, 15, 19, 40),
    "tree/sub": (2024, 8, 20, 13, 50),
    "tree": (2024, 9, 25, 17, 15),
}


def stamp(fields: tuple[int, int, int, int, int]) -> float:
    year, month, day, hour, minute = fields
    return time.mktime((year, month, day, hour, minute, 0, 0, 0, -1))


def build() -> Path:
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)
    for rel, size in LAYOUT.items():
        target = DATA / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"A" * size)
    for rel in EMPTY_DIRS:
        (DATA / rel).mkdir(parents=True, exist_ok=True)
    # mtime 要从深到浅设：改一个目录的内容会更新它的 mtime，
    # 所以先设文件，再设目录，目录那一层才是最后被写的。
    for rel in sorted(MTIMES, key=lambda p: p.count("/")):
        os.utime(str(DATA / rel), (stamp(MTIMES[rel]), stamp(MTIMES[rel])))
    return DATA


def main() -> None:
    data = build()
    total = 0
    for rel, size in sorted(LAYOUT.items()):
        path = data / rel
        actual = path.stat().st_size
        assert actual == size, (rel, actual, size)
        total += size
    print("已生成 AI/数据/du_demo/（%d 个文件，合计 %d 字节）" % (len(LAYOUT), total))
    for rel in sorted(MTIMES):
        path = data / rel
        y, mo, d, h, mi = MTIMES[rel]
        kind = "目录" if path.is_dir() else "文件"
        print("  %-24s %s  %d 字节  %04d-%02d-%02d %02d:%02d" % (
            rel, kind, path.stat().st_size, y, mo, d, h, mi))


if __name__ == "__main__":
    main()
