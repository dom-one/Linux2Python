"""补 teach/00 索引页「可用指令」清单里缺的 wc 一行。

用法:
    python AI/脚本/_t111_fix_teach00_wc.py

背景:
    开发任务 2026-11-09 03:55 落地 wc 指令后，`python main.py` 的帮助
    输出多了一行 wc。teach/00 是本轮已触及的索引页（补了目录树），
    它自己的预期输出块也得跟着对上，否则读者按索引页第 1 步跑就
    看到不一致。

只改这一处。teach/01、teach/09、teach/13、teach/18 里同样的过期清单
属于跨篇的 F 类问题，留给下个 tick 统一修，本轮不越界。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "teach" / "00-项目总览与阅读顺序.md"
PREVIEW = ROOT / "AI" / "数据" / "t111_teach00_wc.preview"

OLD = (
    "  tail  打印文件末尾部分（GNU tail 风格子集）\n"
    "\n"
    "查看具体用法: python main.py <指令> --help"
)

NEW = (
    "  tail  打印文件末尾部分（GNU tail 风格子集）\n"
    "  wc    统计行数、词数、字符数、字节数（GNU wc 风格子集）\n"
    "\n"
    "查看具体用法: python main.py <指令> --help"
)


def main() -> int:
    apply = "--apply" in sys.argv
    original = DOC.read_bytes()
    text = original.decode("utf-8")

    found = text.count(OLD)
    if found != 1:
        print("中止：待改段命中 %d 次，期望 1 次" % found)
        return 1
    text = text.replace(OLD, NEW, 1)

    if b"\r\n" in original:
        print("中止：原文件是 CRLF")
        return 1

    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    PREVIEW.write_bytes(text.encode("utf-8"))
    print()
    print("长度：原 %d 字节 -> 新 %d 字节" % (len(original), len(text.encode("utf-8"))))
    if apply:
        os.replace(PREVIEW, DOC)
        print("已覆盖原文件 %s" % DOC.name)
    else:
        print("预览已写到 %s" % PREVIEW)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
