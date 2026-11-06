"""探针三：裸 argparse（选项定义与 head.py 完全一致）到底怎么对待
`-3`、`-n -3`、`-c -5`，以及 _rewrite_argv 改写后有什么不同。

用法:
    python AI/脚本/_t92_probe_head_argparse.py

产出:
    AI/数据/_t92_head_argparse.txt
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "数据", "_t92_head_argparse.txt")

sys.path.insert(0, ROOT)

from w2l.commands.head import _rewrite_argv  # noqa: E402

ARGV_CASES = [
    ["-3", "f.txt"],
    ["-n", "3", "f.txt"],
    ["-n", "-3", "f.txt"],
    ["-c", "-5", "f.txt"],
    ["-c", "5", "f.txt"],
    ["-n", "+3", "f.txt"],
    ["-2k", "f.txt"],
    ["-n", "1b", "f.txt"],
]


def plain_parser() -> argparse.ArgumentParser:
    """选项定义与 head.py 完全一致，但用裸 argparse（没有 _HeadParser）。"""
    parser = argparse.ArgumentParser(prog="python main.py head")
    parser.add_argument("files", nargs="*")
    parser.add_argument("-n", "--lines", dest="count_specs", action="append", metavar="NUM")
    parser.add_argument("-c", "--bytes", dest="count_specs", action="append", metavar="NUM")
    parser.add_argument("-q", "--quiet", "--silent", dest="header_mode", action="store_const", const="quiet")
    parser.add_argument("-v", "--verbose", dest="header_mode", action="store_const", const="verbose")
    parser.add_argument("-z", "--zero-terminated", dest="zero_terminated", action="store_true")
    return parser


def main() -> int:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("### 裸 argparse（无改写）\n")
        for argv in ARGV_CASES:
            handle.write(f"\nargv={argv}\n")
            parser = plain_parser()
            try:
                namespace = parser.parse_args(list(argv))
                handle.write(
                    f"  解析成功: count_specs={namespace.count_specs} "
                    f"files={namespace.files} header_mode={namespace.header_mode}\n"
                )
            except SystemExit as exc:
                handle.write(f"  解析失败: SystemExit({exc.code})\n")

        handle.write("\n\n### _rewrite_argv 改写后（head.py 的真实做法）\n")
        for argv in ARGV_CASES:
            handle.write(f"\nargv={argv}\n")
            handle.write(f"  改写成: {_rewrite_argv(list(argv))}\n")

    print(f"探针输出写到 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
