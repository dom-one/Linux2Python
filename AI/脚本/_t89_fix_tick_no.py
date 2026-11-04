"""把误编号的 tick #5 改回 tick #4。

背景：AI/脚本/_t11_progress.py 的 next_tick() 扫全文找 `tick #N` 取最大值。
本轮我在状态段写了「本次会话：cron tick #4」，标题里也写了「（tick #4）」，
两处都命中这个正则，于是计数器以为已经到 #4，追加日志时编成了 #5。

实际上本篇是第 4 次 tick（上一篇是 #3），所以日志编号要改回 #4。

改完之后全文最大的 tick 号是 4，下个 tick 的 next_tick() 会算成 5，正确。

进度文件是追加型，但这条是本轮刚写错的一次性修正，改动范围就一行标题。

跑法：
    python AI/脚本/_t89_fix_tick_no.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TARGET = os.path.join(ROOT, "AI", "教程进度.md")
PREVIEW = TARGET + ".preview"

OLD = "#### tick #5（2026-11-05 04:49）— 补充 w2l/entry.py 教程"
NEW = "#### tick #4（2026-11-05 04:49）— 补充 w2l/entry.py 教程"


def main() -> None:
    with open(TARGET, "r", encoding="utf-8", newline="") as fh:
        original = fh.read()

    if OLD not in original:
        raise SystemExit("找不到误编号的 tick #5 标题")
    if original.count(OLD) != 1:
        raise SystemExit("tick #5 标题出现多次")

    text = original.replace(OLD, NEW, 1)

    # 断言：四个 tick 编号是 1/2/3/4，且顺序正确
    import re
    numbers = [int(m) for m in re.findall(r"#### tick #(\d+)", text)]
    assert numbers == [1, 2, 3, 4], "tick 编号不对：%s" % numbers
    # 状态段和标题里的编号也要跟日志一致
    assert "本次会话：cron tick #4（补充 w2l/entry.py 教程，已完成 20 篇）" in text
    assert "### 2026-11-05 全量复核（tick #4）" in text
    # 日志正文五项都在
    for key in ("**选本理由**", "**产出**", "**关键收获**", "**负面结果**"):
        assert key in text, "缺字段：%s" % key

    with open(PREVIEW, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    with open(PREVIEW, "r", encoding="utf-8", newline="") as fh:
        check = fh.read()
    assert check == text, "预览文件和写入内容不一致"

    os.replace(PREVIEW, TARGET)
    print("已更新 %s" % TARGET)
    print("  tick #5 -> tick #4，全文编号 1/2/3/4 连续")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
