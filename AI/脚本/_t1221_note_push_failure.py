#!/usr/bin/env python
"""把本轮的推送失败写进 tick 日志，并同步状态段的「下一步」。

按 AI/AGENTS.md 的约定：推送失败不回滚本地提交，把报错原文写进 tick 日志，
下个 tick 开工前先补推一次。

用法: python AI/脚本/_t1221_note_push_failure.py
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGRESS = HERE.parent / "阅读进度.md"

ERROR = (
    "fatal: unable to access 'https://github.com/dom-one/Linux2Python/': "
    "Failed to connect to github.com port 443 after 21065 ms: "
    "Could not connect to server"
)

NOTE = (
    "\n- **推送状态**：本轮两笔提交（5a073e1 feat(encoding): 抽出共享编码判定模块并提速打分、"
    "f6678ad chore(ai): 补记编码判定提速 tick 的进度日志与探针脚本）已提交在本地，但推送失败："
    "`%s`（隔 15 秒重试一次，报错同样，第二次是 21088 ms）。"
    "按约定不回滚本地提交，下个 tick 开工前先补推一次。\n" % ERROR
)

OLD_NEXT = (
    "或接着把并行搜索铺到 find/du/tree；本轮提交 5a073e1 feat(encoding): 抽出共享编码判定模块并提速打分"
)
NEW_NEXT = (
    "或接着把并行搜索铺到 find/du/tree；本轮提交 5a073e1 feat(encoding): 抽出共享编码判定模块并提速打分，"
    "但推送失败（github.com:443 连不上），下个 tick 开工前先补推"
)


def main() -> int:
    text = PROGRESS.read_text(encoding="utf-8")
    if "推送状态" in text.split("#### tick #18")[-1]:
        print("[跳过] tick #18 已写过推送状态")
    else:
        text = text.rstrip("\n") + "\n" + NOTE
        print("已追加推送失败记录")

    count = text.count(OLD_NEXT)
    if count == 1:
        text = text.replace(OLD_NEXT, NEW_NEXT)
        print("已更新状态段的「下一步」")
    elif count == 0:
        print("[跳过] 状态段的「下一步」已是最新")
    else:
        print(f"[中止] 「下一步」旧文本出现 {count} 次")
        return 2

    PROGRESS.write_text(text, encoding="utf-8", newline="\n")
    print(f"已写入 {PROGRESS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
