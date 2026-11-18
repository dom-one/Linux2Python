"""生成 tree 教程用的固定夹具。

夹具落在 AI/数据/ 下（.gitignore 已忽略），文件内容与 mtime 都写死，
所以教程里引用的预期输出不会随运行时间变化。

两个夹具：

一、tree_demo —— 主演示夹具
   - 文件名故意大小写混排（B.txt / a.txt），演示「按码位序排」不是按 Windows
     的大小写不敏感序排。
   - 混着目录与文件，演示默认排序不把目录提前（--dirsfirst 才提前）。
   - mtime 从 2020 到 2026 依次铺开，演示 -t（旧的在前）与 -D（半年内显示
     时刻、更早显示年份）。
   - big.bin 固定 2048 字节，演示 -h 的 K 单位换算。
   - empty_dir 是空目录，演示「根目录为空时不计入目录数」。
   - sub 故意排在 tools 前面（sub 不是最后一个兄弟），这样它的子项行上会出现
     竖线，能看清 UTF-8 竖线后面跟的是不换行空格（U+00A0）而不是普通空格。

二、tree_deep —— 三层夹具
   专门用来演示 -P 命中目录时的展开范围：hit/ 下面是 mid/，mid/ 下面是叶子文件。
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = Path(ROOT) / "AI" / "数据"
DEMO = DATA / "tree_demo"
DEEP = DATA / "tree_deep"

# (相对路径, 内容字节, 本地时间元组)
DEMO_FILES = [
    (".hidden", b"hidden\n", (2020, 9, 13, 20, 26, 40)),
    ("B.txt", b"upper\n", (2022, 6, 24, 8, 0, 0)),
    ("a.txt", b"hello\n", (2024, 1, 1, 8, 0, 0)),
    ("big.bin", b"z" * 2048, (2025, 1, 1, 8, 0, 0)),
    ("notes.md", b"# note\n", (2026, 11, 18, 10, 30, 0)),
    ("sub/code.py", b"print(1)\n", (2026, 11, 17, 9, 15, 0)),
    ("sub/deep.txt", b"deep\n", (2026, 11, 19, 0, 5, 0)),
    ("tools/run.txt", b"run\n", (2026, 11, 18, 8, 0, 0)),
]

DEMO_DIRS = ["sub", "empty_dir", "tools"]

# 三层夹具：hit/mid/leaf.txt
DEEP_FILES = [
    ("plain.txt", b"p\n", (2026, 11, 18, 8, 0, 0)),
    ("hit/direct.txt", b"d\n", (2026, 11, 18, 9, 0, 0)),
    ("hit/mid/leaf.txt", b"l\n", (2026, 11, 18, 10, 0, 0)),
    ("hit/mid/leaf2.txt", b"l2\n", (2026, 11, 18, 11, 0, 0)),
]

DEEP_DIRS = ["hit", "hit/mid"]


def _stamp(parts: tuple[int, ...]) -> float:
    """把本地时间元组转成纪元秒。"""
    return time.mktime(tuple(parts) + (0, 0, -1))


def _build(base: Path, files, dirs) -> None:
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)

    for name in dirs:
        (base / name).mkdir(parents=True, exist_ok=True)

    for rel, payload, when in files:
        target = base / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        stamp = _stamp(when)
        os.utime(target, (stamp, stamp))

    # 目录的 mtime 要在内容写完之后再设，否则加文件会把它顶掉
    for name in dirs:
        stamp = _stamp((2026, 11, 19, 1, 0, 0))
        os.utime(base / name, (stamp, stamp))
    # 根目录自己的 mtime 也要钉死：-D 会打根目录那一行
    stamp = _stamp((2026, 11, 19, 1, 0, 0))
    os.utime(base, (stamp, stamp))


def main() -> None:
    _build(DEMO, DEMO_FILES, DEMO_DIRS)
    _build(DEEP, DEEP_FILES, DEEP_DIRS)
    print("已生成 AI/数据/tree_demo/（8 个文件）与 AI/数据/tree_deep/（4 个文件）")


if __name__ == "__main__":
    main()
