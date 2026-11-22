#!/usr/bin/env python
"""更新 AI/教程进度.md 第 0 节的「下一步」清单。

用法：
    python AI/脚本/_t1309_update_awk_next.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PROGRESS = ROOT / "AI" / "教程进度.md"

OLD = (
    "- 下一步：`w2l/commands/` 下还差 `awk_lite.py`、`cp.py`、`mv.py`、`rm.py`、`chmod.py` 五篇"
    "（`grep.py` 见 teach/07、`cat.py` 见 teach/21、`wc.py` 见 teach/22、`head.py` 见 teach/20、"
    "`tail.py` 见 teach/23、`find.py` 见 teach/24、`tree.py` 见 teach/25、`du.py` 见 teach/26、"
    "`sed.py` 见 teach/27，`ls.py` 的内容被 teach/13 当例子覆盖过）；"
    "再往后是 `bin/` 下的两份启动器、`cron.md`、`AI/AGENTS.md`、`AI/脚本/_t10_lock.py`、"
    "`AI/脚本/_t11_progress.py`"
)

NEW = (
    "- 下一步：`w2l/commands/` 下还差 `cp.py`、`mv.py`、`rm.py`、`chmod.py` 四篇"
    "（`grep.py` 见 teach/07、`cat.py` 见 teach/21、`wc.py` 见 teach/22、`head.py` 见 teach/20、"
    "`tail.py` 见 teach/23、`find.py` 见 teach/24、`tree.py` 见 teach/25、`du.py` 见 teach/26、"
    "`sed.py` 见 teach/27、`awk_lite.py` 见 teach/28，`ls.py` 的内容被 teach/13 当例子覆盖过）；"
    "再往后是 `w2l/parallel.py`、`w2l/perms.py` 两个还没成篇的核心模块，"
    "然后是 `bin/` 下的两份启动器、`cron.md`、`AI/AGENTS.md`、`AI/脚本/_t10_lock.py`、"
    "`AI/脚本/_t11_progress.py`"
)


def main() -> int:
    text = PROGRESS.read_text(encoding="utf-8")
    count = text.count(OLD)
    if count != 1:
        print(f"锚点命中 {count} 次（应为 1），退出")
        return 1
    PROGRESS.write_text(text.replace(OLD, NEW), encoding="utf-8")
    print("已更新「下一步」")
    return 0


if __name__ == "__main__":
    sys.exit(main())
