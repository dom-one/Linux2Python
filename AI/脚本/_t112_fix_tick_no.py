"""修 AI/教程进度.md 的 tick 号：#7 改回 #6，头部同步。

用法:
    python AI/脚本/_t112_fix_tick_no.py

问题:
    _t11_progress.py 的 next_tick 扫全文取「最大的 tick 号 + 1」。
    我在头部写了「本次会话：cron tick #6」，全文最大号就成了 6，
    追加出来的日志被编成 #7，中间空了一号（#6 从未出现过）。

    这不是文档描述问题，是进度日志的编号不连续——下个 tick 读这份文件
    时会以为 #6 漏记了。

修法:
    把日志里的 tick #7 改成 tick #6，头部的「tick #6」保持不变。
    改完全文最大号是 6，下个 tick 追加时算出的就是 #7，编号连续。

    注意：这属于修正刚写入的本次日志，不是改历史段落——
    历史段落（tick #1~#5）一个字节都不动。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROGRESS = ROOT / "AI" / "教程进度.md"
PREVIEW = ROOT / "AI" / "数据" / "t112_tick_no.preview"

OLD_HEAD = "#### tick #7（2026-11-09 04:33）— 补充 w2l/commands/cat.py 教程"
NEW_HEAD = "#### tick #6（2026-11-09 04:33）— 补充 w2l/commands/cat.py 教程"


def main() -> int:
    apply = "--apply" in sys.argv
    original = PROGRESS.read_bytes()
    text = original.decode("utf-8")

    found = text.count(OLD_HEAD)
    if found != 1:
        print("中止：待改标题命中 %d 次，期望 1 次" % found)
        return 1
    text = text.replace(OLD_HEAD, NEW_HEAD, 1)

    # 断言：历史段落 tick #1~#5 都没被动过
    for n in range(1, 6):
        marker = "#### tick #%d（" % n
        if marker not in text:
            print("中止：历史 tick #%d 丢了" % n)
            return 1
    print("  已确认：历史 tick #1~#5 都在")

    # 断言：现在全文最大号是 6，且 #6 只出现一次（日志）+ 一次（头部）
    import re
    nums = [int(m) for m in re.findall(r"tick\s*#(\d+)", text, re.I)]
    if max(nums) != 6:
        print("中止：改后全文最大 tick 号是 %d，期望 6" % max(nums))
        return 1
    print("  已确认：改后全文最大 tick 号是 6")

    if b"\r\n" in original:
        print("中止：原文件是 CRLF")
        return 1

    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    PREVIEW.write_bytes(text.encode("utf-8"))
    print()
    if apply:
        os.replace(PREVIEW, PROGRESS)
        print("已覆盖原文件 %s" % PROGRESS.name)
    else:
        print("预览已写到 %s" % PREVIEW)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
