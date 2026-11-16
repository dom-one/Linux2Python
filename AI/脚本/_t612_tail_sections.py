"""算 tail.py 各部分的行数占比，给教程正文用（正文里的比例不能靠估）。

用法:
    python AI/脚本/_t612_tail_sections.py

分四段：
1. 计数语法与参数改写：_rewrite_argv 到 _suffix_multiplier 结束
2. 跟随模式：_Follower 类到 _follow_loop 结束
3. 内容读取：_read_some 到 _iter_lines 结束
4. 其余：入口、选项构建、输出与编码判定
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TAIL_PY = os.path.join(ROOT, "w2l", "commands", "tail.py")

# (段名, 起始标记, 结束标记)
SECTIONS = [
    ("计数语法与参数改写", "def _rewrite_argv", "def _prepare_stdout"),
    ("跟随模式", "class _Follower", "def _pid_alive"),
    ("内容读取", "def _read_some", "# ---------------------------------------------------------------- 跟随模式"),
]


def line_of(src: str, marker: str) -> int:
    idx = src.find(marker)
    if idx < 0:
        raise SystemExit("找不到标记：%s" % marker)
    return src[:idx].count("\n") + 1


def main() -> int:
    with open(TAIL_PY, "r", encoding="utf-8") as fh:
        src = fh.read()
    total = src.count("\n") + 1
    print("总行数 %d" % total)
    covered = []
    for name, start_marker, end_marker in SECTIONS:
        start = line_of(src, start_marker)
        end = line_of(src, end_marker) - 1
        covered.append((start, end))
        span = end - start + 1
        print("%-16s 第 %4d ~ %4d 行，%4d 行，占 %.1f%%"
              % (name, start, end, span, span * 100.0 / total))
    covered.sort()
    gaps = []
    cursor = 1
    for start, end in covered:
        if start > cursor:
            gaps.append((cursor, start - 1))
        cursor = end + 1
    if cursor <= total:
        gaps.append((cursor, total))
    other = sum(e - s + 1 for s, e in gaps)
    print("%-16s 其余 %d 行，占 %.1f%%" % ("其余", other, other * 100.0 / total))
    print("明细：%s" % ", ".join("%d~%d" % g for g in gaps))
    return 0


if __name__ == "__main__":
    sys.exit(main())
