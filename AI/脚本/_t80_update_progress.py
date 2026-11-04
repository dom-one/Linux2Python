"""更新 AI/教程进度.md 的清单表与状态段。

只动「## 0. 当前状态」和「## 1. 教程清单」两处：
1. 清单表加一行 20（w2l/entry.py 的教程），状态标已完成
2. 当前状态的完成度 19/19 -> 20/20，会话说明和下一步同步

「## 3. 已知问题与未决项」和「## 4. tick 日志」是历史段落，只追加不改写，
本脚本一个字节都不碰。

按规矩先写 .preview，断言过了再 os.replace 覆盖。

跑法：
    python AI/脚本/_t80_update_progress.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TARGET = os.path.join(ROOT, "AI", "教程进度.md")
PREVIEW = TARGET + ".preview"


def main() -> None:
    with open(TARGET, "r", encoding="utf-8", newline="") as fh:
        original = fh.read()

    text = original

    # --- 1. 状态段 ----------------------------------------------------
    old_head = """最后更新：2026-10-30
本次会话：cron tick #3（补充 w2l/__init__.py 教程，已完成 19 篇）

## 0. 当前状态

- 当前阶段：补齐根目录配置文件与守则文件的教程
- 完成度：19/19
- 下一步：按需补充新指令的教程，随开发任务产出的指令同步增加；`cron.md`、`AI/AGENTS.md` 等剩余零散文件可按需单独成篇
"""
    new_head = """最后更新：2026-11-05
本次会话：cron tick #4（补充 w2l/entry.py 教程，已完成 20 篇）

## 0. 当前状态

- 当前阶段：补齐 `w2l/` 核心模块与启动器相关的教程
- 完成度：20/20
- 下一步：`w2l/` 下六个模块已全部成篇；剩余可按需单独成篇的有 `bin/` 下的两份启动器、`cron.md`、`AI/AGENTS.md`、`AI/脚本/_t10_lock.py`、`AI/脚本/_t11_progress.py`；新指令的教程随开发任务产出的指令同步增加
"""
    if old_head not in text:
        raise SystemExit("找不到状态段")
    text = text.replace(old_head, new_head, 1)

    # --- 2. 清单表加一行 ----------------------------------------------
    old_row = "| 19 | `w2l/__init__.py` | `18-w2l-__init__.py-包标记与版本号.md` | 已完成 |\n"
    new_row = old_row + "| 20 | `w2l/entry.py` | `19-w2l-entry.py-入口名跟随调用方式.md` | 已完成 |\n"
    if old_row not in text:
        raise SystemExit("找不到清单表 19 行")
    if "| 20 |" in text:
        raise SystemExit("清单表里已经有 20 行了")
    text = text.replace(old_row, new_row, 1)

    # --- 断言 ----------------------------------------------------------
    assert "- 完成度：20/20" in text
    assert "- 完成度：19/19" not in text
    assert "| 20 | `w2l/entry.py` | `19-w2l-entry.py-入口名跟随调用方式.md` | 已完成 |" in text
    # 历史段落一个字节都不能动
    for marker in ("## 3. 已知问题与未决项", "## 4. tick 日志",
                   "#### tick #1（2026-10-28 22:18）",
                   "#### tick #2（2026-10-29 09:17）",
                   "#### tick #3（2026-10-30 12:27）"):
        assert marker in text, "历史段落被弄丢了：%s" % marker
    assert text.count("#### tick #") == 3, "tick 段落数量变了"

    with open(PREVIEW, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    with open(PREVIEW, "r", encoding="utf-8", newline="") as fh:
        check = fh.read()
    assert check == text, "预览文件和写入内容不一致"

    os.replace(PREVIEW, TARGET)
    print("已更新 %s" % TARGET)
    print("  清单表加第 20 行，完成度 19/19 -> 20/20")
    print("  历史段落（已知问题 + 3 段 tick 日志）未改动")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
