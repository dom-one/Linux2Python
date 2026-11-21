"""给本轮 tick 日志的「负面结果」补一条：tick 编号被算错。

背景：_t11_progress.py 的 next_tick 原来扫全文件的「tick #N」，
把教程日志正文里提到的开发任务 tick #15 也算进去了，
于是本轮被编成 #16（教程日志自己的标题只到 #11，应为 #12）。
已修 _t11_progress.py（只认「#### tick #N」标题行），
本脚本把本轮刚追加的标题从 #16 改成 #12，并补记这条教训。

用法：python AI/脚本/_t1024_add_tick_lesson.py
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TARGET = ROOT / "AI" / "教程进度.md"

OLD = (
    "git push 连着三次报「Failed to connect to github.com port 443」，第四次才推上去；"
    "本地提交没有回滚"
)
NEW = (
    "git push 连着三次报「Failed to connect to github.com port 443」，第四次才推上去；"
    "本地提交没有回滚。"
    "最后一条是本轮改动最大的坑：_t11_progress.py 的 next_tick 原来扫全文件的「tick #N」，"
    "把本文件正文里提到的开发任务 tick #15 也算进去了，"
    "而教程日志自己的标题只到 #11，于是本轮被编成了 #16（应为 #12）。"
    "已把 next_tick 改成只认「#### tick #N」标题行，并把本轮标题改正；"
    "下个 tick 若看到自己的编号跳号，先查 next_tick 的口径"
)


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if NEW in text:
        print("  [已] 负面结果已含 tick 编号这条")
    elif OLD in text:
        if text.count(OLD) != 1:
            raise SystemExit("旧串出现 %d 次，不唯一" % text.count(OLD))
        text = text.replace(OLD, NEW)
        with open(TARGET, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print("  [改] 负面结果补记 tick 编号这条")
    else:
        raise SystemExit("既找不到旧串也找不到新串")

    if "\ufffd" in text:
        raise SystemExit("进度文件里混进了坏字符 U+FFFD")
    print("[result] %d 字节，%d 行" % (len(text.encode("utf-8")), text.count("\n") + 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
