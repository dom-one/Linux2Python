"""更新 AI/教程进度.md 的状态段与教程清单（只改头部，不动历史 tick 段落）。

用法:
    python AI/脚本/_t1508_update_progress_status.py

改的地方:
1. 头部四行（最后更新日期、本次会话、完成度、下一步）
2. 「## 1. 教程清单」表格末尾加一行（编号 31）

硬约束:
- **历史 tick 段落只能追加，不许重写**——本脚本只对头部与清单表做
  定点替换，每处都断言「替换后旧串不再出现、新串恰好出现一次」。
- 写盘必须 newline=""：Windows 上默认会把 \\n 翻译成 \\r\\n，
  整个文件从 LF 翻成 CRLF，git diff 变成整篇重写。
- 幂等：已改过的串跳过，连跑两遍 sha256 不变。
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DOC = ROOT / "AI" / "教程进度.md"

ROW_31 = "| 31 | `w2l/commands/mv.py` | `30-w2l-commands-mv.py-落点判定与覆盖策略.md` | 已完成 |"

NEXT_STEP = (
    "- 下一步：`w2l/commands/` 下还差 `rm.py`、`chmod.py` 两篇"
    "（`grep.py` 见 teach/07、`cat.py` 见 teach/21、`wc.py` 见 teach/22、"
    "`head.py` 见 teach/20、`tail.py` 见 teach/23、`find.py` 见 teach/24、"
    "`tree.py` 见 teach/25、`du.py` 见 teach/26、`sed.py` 见 teach/27、"
    "`awk_lite.py` 见 teach/28、`cp.py` 见 teach/29、`mv.py` 见 teach/30，"
    "`ls.py` 的内容被 teach/13 当例子覆盖过）；"
    "再往后是 `w2l/parallel.py`、`w2l/perms.py`、`w2l/encoding.py`、"
    "`w2l/flags.py` 四个还没成篇的核心模块，"
    "然后是 `bin/` 下的两份启动器、`cron.md`、`AI/AGENTS.md`、"
    "`AI/脚本/_t10_lock.py`、`AI/脚本/_t11_progress.py`"
)

# (旧串, 新串)
EDITS: list[tuple[str, str]] = [
    ("最后更新：2026-11-24", "最后更新：2026-11-25"),
    (
        "本次会话：cron tick（补充 w2l/commands/cp.py 教程，已完成 30 篇）",
        "本次会话：cron tick（补充 w2l/commands/mv.py 教程，已完成 31 篇）",
    ),
    ("- 完成度：30/30", "- 完成度：31/31"),
    (
        # 整行替换：旧串必须覆盖**整行**，不能只取前缀。
        # 只取前缀会把新串接在原行剩余部分后面（上次就翻车过一次）。
        "- 下一步：`w2l/commands/` 下还差 `mv.py`、`rm.py`、`chmod.py` 三篇"
        "（`grep.py` 见 teach/07、`cat.py` 见 teach/21、`wc.py` 见 teach/22、"
        "`head.py` 见 teach/20、`tail.py` 见 teach/23、`find.py` 见 teach/24、"
        "`tree.py` 见 teach/25、`du.py` 见 teach/26、`sed.py` 见 teach/27、"
        "`awk_lite.py` 见 teach/28、`cp.py` 见 teach/29，"
        "`ls.py` 的内容被 teach/13 当例子覆盖过）；"
        "再往后是 `w2l/parallel.py`、`w2l/perms.py` 两个还没成篇的核心模块，"
        "然后是 `bin/` 下的两份启动器、`cron.md`、`AI/AGENTS.md`、"
        "`AI/脚本/_t10_lock.py`、`AI/脚本/_t11_progress.py`",
        NEXT_STEP,
    ),
    (
        "| 30 | `w2l/commands/cp.py` | `29-w2l-commands-cp.py-目标落点与属性保留.md` | 已完成 |",
        "| 30 | `w2l/commands/cp.py` | `29-w2l-commands-cp.py-目标落点与属性保留.md` | 已完成 |\n"
        + ROW_31,
    ),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    before_bytes = len(text.encode("utf-8"))
    before_lines = text.count("\n")

    applied = 0
    skipped = 0
    for old, new in EDITS:
        if new in text:
            skipped += 1
            continue
        if old not in text:
            print(f"!! 找不到待替换的旧串: {old[:70]!r}")
            return 1
        text = text.replace(old, new, 1)
        applied += 1

    raw_before = DOC.read_bytes()
    crlf_before = raw_before.count(b"\r\n")
    with DOC.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)

    raw_after = DOC.read_bytes()
    if raw_after.count(b"\r\n") != crlf_before:
        print("!! 换行风格被改了，已回滚")
        DOC.write_bytes(raw_before)
        return 1

    after = DOC.read_text(encoding="utf-8")
    print(f"替换 {applied} 处，跳过（已在位）{skipped} 处")
    print(
        f"字节 {before_bytes} -> {len(after.encode('utf-8'))}，"
        f"行 {before_lines} -> {after.count(chr(10))}"
    )

    # 内容不变式：关键串都在，且清单行只出现一次
    checks = [
        "最后更新：2026-11-25",
        "已完成 31 篇",
        "- 完成度：31/31",
        "`mv.py` 见 teach/30",
        ROW_31,
    ]
    missing = [c for c in checks if c not in after]
    if missing:
        print("!! 缺这些串:", missing)
        return 1
    if after.count(ROW_31) != 1:
        print(f"!! 清单行出现 {after.count(ROW_31)} 次，应该恰好 1 次")
        return 1

    # 「下一步」整行只能有一份：上次只取前缀当 old，导致新串后面又接上了
    # 原行的剩余部分，整行被复制了一遍。所以这里查关键片段的出现次数。
    dup_probe = "`rm.py`、`chmod.py` 两篇"
    if after.count(dup_probe) != 1:
        print(f"!! 「下一步」行有重复，关键片段出现 {after.count(dup_probe)} 次")
        return 1
    if after.count("`w2l/parallel.py`、`w2l/perms.py`") != 1:
        print("!! 「下一步」行有重复（parallel/perms 片段出现多次）")
        return 1

    # 历史 tick 段落必须原封不动：行数增量只能来自本轮改的几处
    print(f"当前 sha256: {sha(DOC)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
