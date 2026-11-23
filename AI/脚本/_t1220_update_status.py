#!/usr/bin/env python
"""更新 AI/阅读进度.md 顶部的「当前状态」段（每轮滚动更新，历史段只追加不改）。

用法: python AI/脚本/_t1220_update_status.py
只做三处定点替换：最后更新日期、本次会话行、0. 当前状态 的四条。
替换前先检查旧文本确实存在且只出现一次，避免误伤正文里的同名字样。
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGRESS = HERE.parent / "阅读进度.md"

REPLACEMENTS = [
    (
        "最后更新：2026-11-23\n本次会话：cron tick #17（grep 支持 -j/--jobs 分片并行搜索）",
        "最后更新：2026-11-24\n本次会话：cron tick #18（编码判定提速：抽出共享模块 w2l/encoding.py）",
    ),
    (
        "- 当前阶段：固定队列已走完（10/10），README「后续演进路线」阶段二也走完了（4/4）；"
        "tick #17 进入阶段三（工程化），做完四项里的第一项「并行搜索」（只做了 grep，find/du/tree 还没做）",
        "- 当前阶段：固定队列已走完（10/10），README「后续演进路线」阶段二也走完了（4/4）；"
        "阶段三（工程化）进行中——tick #17 做完四项里的第一项「并行搜索」（只做了 grep，find/du/tree 还没做），"
        "tick #18 做完「编码判定提速」：判定逻辑抽成共享模块 w2l/encoding.py，七个指令共用一份，"
        "打分从逐字符 Python 循环改成 str.translate + str.count 分桶计数",
    ),
    (
        "- 完成度：grep、ls、cat、head、tail、wc、find、tree、du、sed、awk-lite、cp、mv、rm、chmod 已实现；"
        "grep 已接入 `-j/--jobs` 分片并行",
        "- 完成度：grep、ls、cat、head、tail、wc、find、tree、du、sed、awk-lite、cp、mv、rm、chmod 已实现；"
        "grep 已接入 `-j/--jobs` 分片并行；编码判定已收成共享模块 w2l/encoding.py（cat/head/tail/wc/sed/awk-lite/grep 共用）",
    ),
    (
        "- 下一步：阶段三剩下三项里挑一个（.w2lrc 配置 / --json 结构化输出 / Windows 特性适配），"
        "或接着把并行搜索铺到 find/du/tree；若走性能优先，先做 grep 编码判定提速"
        "（每文件四候选编码乘 8KB 逐字符打分，这是 grep 串行比 GNU grep 慢 1.7~2.7 倍的根因）；"
        "本轮两笔提交都已推上去了",
        "- 下一步：阶段三剩下三项里挑一个（.w2lrc 配置 / --json 结构化输出 / Windows 特性适配），"
        "或接着把并行搜索铺到 find/du/tree；本轮提交 5a073e1 feat(encoding): 抽出共享编码判定模块并提速打分",
    ),
    (
        "- 遗留项：cp 的 `-n` / `-i` 顺序与 GNU 对齐（GNU 是后给的赢，本项目 README 写的是 `-n` 压过 `-i`），"
        "tick #12 起挂了四轮；tests/test_find.py::test_find_newer 的时间戳 flake 还在（本机 mtime 精度约 15.6ms）；"
        "AI/产物/ 下有一批 2026-11-11 的 wc 教程遗留产物没进 .gitignore，每轮 git status 都有它",
        "- 遗留项：cp 的 `-n` / `-i` 顺序与 GNU 对齐（GNU 是后给的赢，本项目 README 写的是 `-n` 压过 `-i`），"
        "tick #12 起挂了五轮；tests/test_find.py::test_find_newer 的时间戳 flake 还在（本机 mtime 精度约 15.6ms）；"
        "AI/产物/ 下有一批 2026-11-11 的 wc 教程遗留产物没进 .gitignore，每轮 git status 都有它；"
        "teach/ 里引用各指令编码函数行号的文档（07/12/21/22/23/27/28）行号已过期，教程任务下个 tick 自查",
    ),
]


def main() -> int:
    text = PROGRESS.read_text(encoding="utf-8")
    original = text
    for old, new in REPLACEMENTS:
        count = text.count(old)
        if count != 1:
            print(f"[中止] 旧文本出现 {count} 次（应为 1 次）：{old[:40]}…")
            return 2
        text = text.replace(old, new)
    if text == original:
        print("[中止] 没有改动")
        return 2
    PROGRESS.write_text(text, encoding="utf-8", newline="\n")
    print(f"已更新 {PROGRESS}，字符数 {len(original)} -> {len(text)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
