"""更新 AI/教程进度.md 的状态行与教程清单表。

用法:
    python AI/脚本/_t109_progress_state.py

为什么用脚本:
    进度文件的「历史段落只能追加」——tick 日志那一节绝不能改。
    但「0. 当前状态」和「1. 教程清单」这两处是现状快照，每个 tick
    都该跟着更新。这里只改这两处，tick 日志由 _t11_progress.py 追加。

改什么:
    1. 头部：最后更新日期、本次会话说明
    2. 当前状态：完成度 21/21 -> 22/22，下一步指向 tail.py 与 wc.py
    3. 教程清单：新增第 22 行（cat.py，已完成）与第 23 行（wc.py，待写）

为什么 wc.py 要进清单:
    开发任务在 2026-11-09 03:55 落地了 wc 指令（w2l/commands/wc.py
    577 行、tests/test_wc.py 23 个用例），清单表之前没有它。
    教程任务的清单覆盖项目里的源文件，wc.py 属于待写项。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROGRESS = ROOT / "AI" / "教程进度.md"
PREVIEW = ROOT / "AI" / "数据" / "t109_progress_state.preview"

EDITS = [
    (
        "头部状态行",
        "最后更新：2026-11-06\n"
        "本次会话：cron tick #5（补充 w2l/commands/head.py 教程，已完成 21 篇）",
        "最后更新：2026-11-09\n"
        "本次会话：cron tick #6（补充 w2l/commands/cat.py 教程，已完成 22 篇）",
    ),
    (
        "当前状态块",
        "- 当前阶段：补 `w2l/commands/` 下新指令的逐文件教程\n"
        "- 完成度：21/21\n"
        "- 下一步：`w2l/commands/` 下还差 `cat.py`、`tail.py` 两篇"
        "（`grep.py` 见 teach/07，`ls.py` 的内容被 teach/13 当例子覆盖过）；"
        "再往后是 `bin/` 下的两份启动器、`cron.md`、`AI/AGENTS.md`、"
        "`AI/脚本/_t10_lock.py`、`AI/脚本/_t11_progress.py`",
        "- 当前阶段：补 `w2l/commands/` 下新指令的逐文件教程\n"
        "- 完成度：22/22\n"
        "- 下一步：`w2l/commands/` 下还差 `tail.py`、`wc.py` 两篇"
        "（`grep.py` 见 teach/07、`cat.py` 见 teach/21，"
        "`ls.py` 的内容被 teach/13 当例子覆盖过）；"
        "再往后是 `bin/` 下的两份启动器、`cron.md`、`AI/AGENTS.md`、"
        "`AI/脚本/_t10_lock.py`、`AI/脚本/_t11_progress.py`",
    ),
    (
        "教程清单新增 cat.py 与 wc.py 两行",
        "| 21 | `w2l/commands/head.py` | "
        "`20-w2l-commands-head.py-计数解析与参数改写.md` | 已完成 |",
        "| 21 | `w2l/commands/head.py` | "
        "`20-w2l-commands-head.py-计数解析与参数改写.md` | 已完成 |\n"
        "| 22 | `w2l/commands/cat.py` | "
        "`21-w2l-commands-cat.py-编码判定与显示记号.md` | 已完成 |\n"
        "| 23 | `w2l/commands/wc.py` | 待写 | 待写 |",
    ),
]


def main() -> int:
    apply = "--apply" in sys.argv
    original = PROGRESS.read_bytes()
    text = original.decode("utf-8")
    before = original.decode("utf-8")

    for desc, old, new in EDITS:
        found = text.count(old)
        if found != 1:
            print("中止：%s —— 命中 %d 次，期望 1 次" % (desc, found))
            return 1
        text = text.replace(old, new, 1)
        print("  已改：%s" % desc)

    # 断言：tick 日志那一节一个字节都没动
    marker = "## 4. tick 日志"
    if marker not in text or marker not in before:
        print("中止：找不到 tick 日志锚点")
        return 1
    if text[text.index(marker):] != before[before.index(marker):]:
        print("中止：tick 日志段落被改动了")
        return 1
    print("  已确认：tick 日志段落未改动")

    if b"\r\n" in original:
        print("中止：原文件是 CRLF")
        return 1

    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    PREVIEW.write_bytes(text.encode("utf-8"))
    print()
    print("长度：原 %d 字节 -> 新 %d 字节" % (len(original), len(text.encode("utf-8"))))
    if apply:
        os.replace(PREVIEW, PROGRESS)
        print("已覆盖原文件 %s" % PROGRESS.name)
    else:
        print("预览已写到 %s" % PREVIEW)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
