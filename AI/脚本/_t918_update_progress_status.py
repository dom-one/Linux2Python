"""更新 AI/教程进度.md 的「当前状态」与「教程清单」两节。

只改这两处，tick 日志由 _t11_progress.py 追加（历史不重写）。
写盘后回读断言，确保没把别的段落弄坏。

用法:
    python AI/脚本/_t918_update_progress_status.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PROGRESS = ROOT / "AI" / "教程进度.md"


def main() -> int:
    text = PROGRESS.read_text(encoding="utf-8")
    original = text

    # 1) 头部状态
    text = text.replace(
        "最后更新：2026-11-19\n"
        "本次会话：cron tick（补充 w2l/commands/tree.py 教程，已完成 26 篇）",
        "最后更新：2026-11-21\n"
        "本次会话：cron tick（补充 w2l/commands/du.py 教程，已完成 27 篇）")

    # 2) 完成度
    text = text.replace("- 完成度：26/26", "- 完成度：27/27")

    # 3) 下一步：du.py 已写完，剩下 sed/awk_lite/cp/mv/rm/chmod
    old_next = ("- 下一步：`w2l/commands/` 下还差 `du.py`、`sed.py`、`awk_lite.py`、"
                "`cp.py`、`mv.py`、`rm.py`、`chmod.py` 七篇（`grep.py` 见 teach/07、"
                "`cat.py` 见 teach/21、`wc.py` 见 teach/22、`head.py` 见 teach/20、"
                "`tail.py` 见 teach/23、`find.py` 见 teach/24、`tree.py` 见 teach/25，"
                "`ls.py` 的内容被 teach/13 当例子覆盖过）；再往后是 `bin/` 下的两份启动器、"
                "`cron.md`、`AI/AGENTS.md`、`AI/脚本/_t10_lock.py`、`AI/脚本/_t11_progress.py`")
    new_next = ("- 下一步：`w2l/commands/` 下还差 `sed.py`、`awk_lite.py`、`cp.py`、"
                "`mv.py`、`rm.py`、`chmod.py` 六篇（`grep.py` 见 teach/07、"
                "`cat.py` 见 teach/21、`wc.py` 见 teach/22、`head.py` 见 teach/20、"
                "`tail.py` 见 teach/23、`find.py` 见 teach/24、`tree.py` 见 teach/25、"
                "`du.py` 见 teach/26，`ls.py` 的内容被 teach/13 当例子覆盖过）；"
                "再往后是 `bin/` 下的两份启动器、`cron.md`、`AI/AGENTS.md`、"
                "`AI/脚本/_t10_lock.py`、`AI/脚本/_t11_progress.py`")
    if old_next in text:
        text = text.replace(old_next, new_next)

    # 4) 清单加第 27 行（清单的编号列是 1..26，新行接在最后是 27）
    row27 = "| 27 | `w2l/commands/du.py` | `26-w2l-commands-du.py-统计口径与去重规则.md` | 已完成 |"
    if row27 not in text:
        anchor = "| 26 | `w2l/commands/tree.py` | `25-w2l-commands-tree.py-树形输出与画线规则.md` | 已完成 |"
        assert anchor in text, "找不到清单最后一行"
        text = text.replace(anchor, anchor + "\n" + row27)

    if text == original:
        print("进度文件的状态段没有需要改的地方")
        return 0

    # 自检
    assert "\ufffd" not in text, "进度文件里有 U+FFFD"
    assert row27 in text, "清单第 27 行没插进去"
    assert text.count("| 27 |") == 1, "清单第 27 行重复了"
    # tick 日志段不能被动过（只能追加）
    assert "#### tick #10" in text, "tick 日志段不见了"

    with open(PROGRESS, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    reread = PROGRESS.read_text(encoding="utf-8")
    assert reread == text, "回读与写入不一致"
    assert b"\r\n" not in PROGRESS.read_bytes(), "文件里混进了 CRLF"

    print("已更新 AI/教程进度.md 的状态段与清单")
    print("  字节数 %d -> %d" % (
        len(original.encode("utf-8")), len(text.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
