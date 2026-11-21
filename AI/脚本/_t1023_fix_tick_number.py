"""把本轮追加的 tick 标题从 #16 改成 #12，并自检坏字符。

为什么：AI/脚本/_t11_progress.py 的 next_tick 原来扫全文件的「tick #N」，
把正文里提到的开发任务 tick #15 也算进去了，教程日志自己的标题只到 #11，
于是新一轮被编成了 #16（应为 #12）。

修法分两处：
1. _t11_progress.py 改成只认「#### tick #N」标题行（已改）。
2. 本脚本把刚追加的这一条标题改正——这一条是本轮刚写的，还没提交，
   改正它不算改写历史。

用法：python AI/脚本/_t1023_fix_tick_number.py
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TARGET = ROOT / "AI" / "教程进度.md"
PROGRESS_TOOL = HERE / "_t11_progress.py"

OLD = "#### tick #16（2026-11-22 04:54）— w2l/commands/sed.py 教程"
NEW = "#### tick #12（2026-11-22 04:54）— w2l/commands/sed.py 教程"


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if NEW in text:
        print("  [已] tick 标题已是 #12")
    elif OLD in text:
        if text.count(OLD) != 1:
            raise SystemExit("旧标题出现 %d 次，不唯一" % text.count(OLD))
        text = text.replace(OLD, NEW)
        with open(TARGET, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print("  [改] tick 标题 #16 → #12")
    else:
        raise SystemExit("既找不到旧标题也找不到新标题")

    if "\ufffd" in text:
        raise SystemExit("进度文件里混进了坏字符 U+FFFD")

    # 工具脚本本身也要查一遍坏字符（本轮改过它）
    tool = PROGRESS_TOOL.read_text(encoding="utf-8")
    if "\ufffd" in tool:
        raise SystemExit("_t11_progress.py 里混进了坏字符 U+FFFD")

    # 自检：改完之后 next_tick 应算出 13（下一轮该是 #13）
    import importlib.util
    spec = importlib.util.spec_from_file_location("t11", str(PROGRESS_TOOL))
    t11 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(t11)
    nxt = t11.next_tick(str(TARGET))
    print("  [自检] next_tick 现算 = %d（应为 13）" % nxt)
    if nxt != 13:
        raise SystemExit("next_tick 算出来是 %d，不是 13" % nxt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
