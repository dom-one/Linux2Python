"""把开发任务的进度文件从 find 推进到 tree。

做三件事：
1. 把本 tick 的日志段号从第 8 号改回第 7 号（上游 find 那轮的号被用过又撤回，
   序列要保持连续；正文里引用「第 7 号」这几个字不匹配 tick 号的正则，不会再抬计数）
2. 更新文件头的当前状态、命令队列、已完成表
3. 往「已知问题」里补 tree 的行为条目，并把计数器的坑重写一遍

只改 AI/阅读进度.md，tick 日志段本身是本 tick 刚追加的，改的是它的段号。
用法：python AI/脚本/_t123_update_progress_tree.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROGRESS = ROOT / "AI" / "阅读进度.md"


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"替换目标命中 {count} 次（应为 1 次）：{old[:40]!r}")
    return text.replace(old, new)


def main() -> int:
    raw = PROGRESS.read_bytes()
    if b"\r\n" in raw:
        raise SystemExit("进度文件里出现了 CRLF，先确认行尾风格再改")
    text = raw.decode("utf-8")

    # 1. 本 tick 的段号：第 8 号 → 第 7 号
    text = replace_once(
        text,
        "#### tick #8（2026-11-11 02:15）— 实现 tree 指令",
        "#### tick #7（2026-11-11 02:15）— 实现 tree 指令",
    )

    # 2. 文件头与当前状态
    text = replace_once(text, "最后更新：2026-11-10", "最后更新：2026-11-11")
    text = replace_once(
        text,
        "本次会话：cron tick #6（实现 find 指令）",
        "本次会话：cron tick #7（实现 tree 指令）",
    )
    text = replace_once(text, "- 当前阶段：命令队列第 7 项", "- 当前阶段：命令队列第 8 项")
    text = replace_once(
        text,
        "- 完成度：grep、ls、cat、head、tail、wc、find 已实现；命令队列 7/10",
        "- 完成度：grep、ls、cat、head、tail、wc、find、tree 已实现；命令队列 8/10",
    )
    text = replace_once(text, "- 下一步：实现 `tree` 指令", "- 下一步：实现 `du` 指令")

    # 3. 命令队列表
    text = replace_once(
        text,
        "| 7 | tree | 树形展示目录 | 待做 |",
        "| 7 | tree | 树形展示目录 | 已完成 |",
    )

    # 4. 已完成表
    text = replace_once(
        text,
        "| find | 2026-11-10 | `w2l/commands/find.py` |",
        "| find | 2026-11-10 | `w2l/commands/find.py` |\n| tree | 2026-11-11 | `w2l/commands/tree.py` |",
    )

    # 5. 计数器那条坑重写
    text = replace_once(
        text,
        "- 进度文件顶部的「本次会话：cron tick #N」那一行会影响 `_t11_progress.py` 算 tick 号（它取文件里最大的 tick 号 +1）：先改标题再追加日志会多跳一号。本轮就是这样写成了 tick #7，已改回 #6。**下个 tick 要先追加日志、再改标题**。",
        "- 进度文件顶部的「本次会话：cron tick #N」那一行会影响 `_t11_progress.py` 算 tick 号（它取**整个文件**里最大的 tick 号 +1，不只扫日志段）：先改标题再追加日志会多跳一号，而且正文里引用某个号也会被算进去（find 那轮写成了第 7 号又改回第 6 号，本轮正文里那句引用又把本轮算成了第 8 号，已改回第 7 号，序列才连续）。**下个 tick 要先追加日志、再改标题**，追加完再核对段号。",
    )

    # 6. tree 的行为条目，追加到已知问题末尾（find 那条之后）
    tree_notes = "\n".join(
        [
            "- `tree` 的画线规则：连接符由「是不是最后一个兄弟」决定（最后一个用 `└── `，其余用 `├── `），祖先层后面还有兄弟才画竖线，否则留空；UTF-8 版竖线后面跟的是不换行空格（U+00A0）再加一个普通空格，整列 4 列宽，ASCII 版是竖线加两个空格。",
            "- `tree` 的统计行用 GNU 的单复数写法（`1 directory` / `2 directories`），且根目录为空时连根目录自己都不计入目录数（空目录是 `0 directories, 0 files`）。",
            "- `tree` 的 `-L N` 在上游源码里是 `Level = N-1`，所以 `-L 1` 只列根目录的直接子项且不展开子目录。",
            "- `tree` 的 `-h` 隐含 `-s`（上游源码注释写着 Assume they also want -s）；`-t` 是旧的在前，与 `ls -t` 相反。",
            "- `tree` 的默认排序是目录与文件混在一起按名字排，`--dirsfirst` 才分开放；GNU 用 `strcoll`（区域设置相关，UTF-8 区域设置下大小写不敏感），本实现按码位序，与本项目 `ls` 一致。",
            "- `tree` 的 `-P` 只筛文件、目录照旧列出；某个目录命中 `-P` 时，它下面的内容全部列出（模式在该子树里失效）。",
            "- `tree` 的通配符：`*` 不跨 `/`，`**` 跨 `/`，`|` 分隔多个候选，模式尾部带 `/` 表示只匹配目录。",
            "- `tree` 的 `-x` 在 Windows 上按盘符判定：`st_dev` 是卷标识（C 盘与 E 盘实测不同），所以它实际是不跨盘符。",
            "- `tree` 的操作数是文件时报「不是目录」并返回 2（GNU 是打 `  [error opening dir]` 再照常统计），沿用本项目「用法或运行错误返回 2」的约定。",
            "- `tree` 的符号链接没法验证：Windows 上创建符号链接要管理员权限（本机报 WinError 1314），`-l` 的行为未实测。",
        ]
    )
    marker = "找到的 `find` 语义"
    if marker not in text:
        # 已知问题段的最后一条是 find 的剩余待决，按行首定位它的结尾
        anchor = "- `find` 的 `-printf` 只支持 `%T@` 不支持 `%T`：GNU findutils 4.10 的 MSYS 构建遇到单独的 `%T` 会报 `memory exhausted` 崩掉。\n"
        text = replace_once(text, anchor, anchor + tree_notes + "\n")
    else:
        raise SystemExit("已知问题段的锚点变了，先看看再改")

    PROGRESS.write_bytes(text.encode("utf-8"))
    print(f"已更新 {PROGRESS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
