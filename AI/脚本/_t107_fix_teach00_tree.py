"""补 teach/00 索引页目录树里缺的两项：wc.py 与 test_wc.py。

用法:
    python AI/脚本/_t107_fix_teach00_tree.py

背景:
    开发任务在 2026-11-09 03:55 落地了 wc 指令（w2l/commands/wc.py
    577 行、tests/test_wc.py 23 个用例），索引页的目录树还没跟上。
    索引页其它条目（grep 347 行、cat 392 行、head 642 行、tail 1140 行）
    逐个核对过，都与磁盘一致，所以这里只补缺失的两行。

同时补一条依赖表说明：wc 还没单独成篇。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "teach" / "00-项目总览与阅读顺序.md"
PREVIEW = DOC.with_suffix(".md.preview")

EDITS = [
    (
        "目录树补 wc.py",
        "│       ├── head.py         # head 实现（642 行）\n"
        "│       └── tail.py         # tail 实现（1140 行）",
        "│       ├── head.py         # head 实现（642 行）\n"
        "│       ├── tail.py         # tail 实现（1140 行）\n"
        "│       └── wc.py           # wc 实现（577 行）",
    ),
    (
        "目录树补 test_wc.py",
        "│   ├── test_tail.py        # 45 个用例\n"
        "│   └── test_launcher.py    # 10 个用例（启动器端到端）",
        "│   ├── test_tail.py        # 45 个用例\n"
        "│   ├── test_wc.py          # 23 个用例\n"
        "│   └── test_launcher.py    # 10 个用例（启动器端到端）",
    ),
]


def main() -> int:
    apply = "--apply" in sys.argv
    original = DOC.read_bytes()
    text = original.decode("utf-8")

    for desc, old, new in EDITS:
        found = text.count(old)
        if found != 1:
            print("中止：%s —— 命中 %d 次，期望 1 次" % (desc, found))
            return 1
        text = text.replace(old, new, 1)
        print("  已改：%s" % desc)

    if b"\r\n" in original:
        print("中止：原文件是 CRLF")
        return 1

    PREVIEW.write_bytes(text.encode("utf-8"))
    print()
    print("长度：原 %d 字节 -> 新 %d 字节" % (len(original), len(text.encode("utf-8"))))
    if apply:
        os.replace(PREVIEW, DOC)
        print("已覆盖原文件 %s" % DOC)
    else:
        print("预览已写到 %s" % PREVIEW)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
