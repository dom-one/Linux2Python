"""把本轮 mv 的实测差异写进 AI/教程进度.md 的「已知问题与未决项」段。

用法:
    python AI/脚本/_t1510_append_mv_findings.py

为什么单独一个脚本而不是手写:
- 进度文件的历史段落只能追加，重写会被下个 tick 读成「被改过」
- 这段 findings 很长（含表格），手写容易出错，且要保证换行风格不变
- 幂等：同一段标记只插一次

写法照抄既有约定：<!-- mv-findings:start --> 与 <!-- mv-findings:end -->
包起来，插在 <!-- cp-findings:end --> 之后（按轮次往后排）。
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DOC = ROOT / "AI" / "教程进度.md"

START = "<!-- mv-findings:start -->"
END = "<!-- mv-findings:end -->"
ANCHOR = "<!-- cp-findings:end -->"

BLOCK = """
<!-- mv-findings:start -->
### 2026-11-25 mv.py 与 GNU coreutils 8.32 的六处差异（本轮实测）

给 `w2l/commands/mv.py` 写教程时，补跑了第二轮差分：前两轮差分脚本
（`AI/脚本/_t510_diff_mv.py` 68 组 + `_t1312_diff_mv_flag_order.py` 10 组）
都是「跑得通」的用例，本轮新写 `AI/脚本/_t1501_diff_mv_gaps.py` 加了 52 组专打
前者没覆盖的角落（`-i` 的应答解析、选项的附着式与长选项写法、互斥选项的组合冲突、
备份位已存在是目录、目标带尾斜杠），查出 **13 处不一致**；
再用 `AI/脚本/_t1502_probe_mv_defects.py` 与 `_t1506_probe_mv_extra.py` 逐条坐实。

其中 **4 处是真实缺陷、1 处是 GNU 独有能力**。源码范围属开发任务，本轮按只读原则没动。

| # | 现象 | 根因 | 位置 |
|---|---|---|---|
| 1 | `-i` 的应答解析与 GNU 不一致（双向分叉） | GNU 的 `yesno()` 只看这一行的**第一个字符**是不是 y/Y；本实现是 `strip().lower()` 之后整串精确匹配 "y"/"yes" ⇒ "yeah"/"yes please" GNU 照搬本实现跳过，" y"/"\\ty" GNU 跳过本实现照搬 | `w2l/commands/mv.py` 第 288~293 行 `_confirm()`（`cp.py` 第 493~498 行同款；`rm.py` 第 424~437 行的写法是**对的**，可直接照抄） |
| 2 | 目标带尾斜杠时不认「目标必须是目录」 | `_resolve()` 用 `Path(operand)` 解析，pathlib 把末尾分隔符吃掉了，「尾斜杠 = 目标必须是目录」这个信号丢失 ⇒ `mv a.txt newdir/` 把 newdir 建成普通文件，GNU 报「No such file or directory」退 1 | `w2l/commands/mv.py` 第 303~308 行 `_resolve()`（**与 cp 那一轮查出的第 3 条同型缺陷**，cp 落成普通文件后 GNU 报「Not a directory」，mv 则是静默成功） |
| 3 | `--backup` 与 `--no-clobber` 互斥没有检查 | `plan()` 里没有互斥校验，GNU 在规划阶段就报「options --backup and --no-clobber are mutually exclusive」退 1，本实现静默执行（`-n` 生效，退出码 0） | `w2l/commands/mv.py` 第 127 行起的 `plan()`（`cp.py` 第 198~200 行**有**这项检查，mv.py 漏了） |
| 4 | `--no-clobber` 与 `--force` 互斥，本实现不是「后给的那个赢」 | `resolve_exclusive()` 只管 `interactive` 与 `no_clobber` 两个选项，`force` 不在其中 ⇒ `-n -f` 在 GNU 是 `-f` 赢（照搬），本实现是 `-n` 赢（静默跳过） | `w2l/commands/mv.py` 第 113~123 行 `_resolve_overwrite_policy()` |
| 5 | **备份目标已存在且是个目录时，本实现把它整个删了**（会丢数据） | `_backup()` 在改名之前先 `_remove_path()` 删掉已存在的备份位，而 `_remove_path()` 对目录走 `shutil.rmtree()` ⇒ 用户原有的备份目录连同内容被静默删除并用文件替换；GNU 报「cannot backup 'b.txt': Is a directory」退 1 且不动任何东西 | `w2l/commands/mv.py` 第 256~257 行 `_backup()`、第 382~386 行 `_remove_path()` |
| 6 | `--backup=numbered` / `=none` / `=simple` 不支持 | `-b/--backup` 是 `action="store_true"`（不接取值），argparse 报 `ignored explicit argument 'numbered'` 退 2；GNU 的 `--backup` 是可选参数长选项，`=numbered` 要靠解析前改写 argv 才支持 | `w2l/commands/mv.py` 第 64 行 `build_parser()`（`cp.py` 上一轮已为 `--preserve` 做过同样的 argv 改写，见 `AI/脚本/_t1302`） |

**第 5 条是本轮最严重的一条**：备份位通常是用户自己的文件（`b.txt~` 是上一次备份的产物），
GNU 遇到同名目录会拒绝，本实现会**静默删掉用户的一个目录**并用文件替换，用户连报错都看不到。

另有两处**不是缺陷但值得记**：

- **`-S` 单独给就隐含开备份**（第 106 行 `self.backup = args.backup or args.suffix is not None`），
  GNU 里 `-S` 只是改后缀、单独给不开备份。本实现是主动加的便利约定。
- **`-v` 输出的换行符是 LF**，与 GNU 一致。`w2l/cli.py` 第 32~36 行给标准输出调了
  `reconfigure(encoding="utf-8", errors="replace")` 但没动 `newline`；
  `cat.py`（第 163 行）与 `tail.py`（第 511 行）因为要输出文件原始字节才显式
  `reconfigure(newline="")`，`mv` 的输出是程序自己造的文本，不涉及原始字节。

实测脚本：`AI/脚本/_t1501_diff_mv_gaps.py`（52 组新用例，产出
`AI/数据/mv_diff2/diff_mv2.json`）、`_t1502_probe_mv_defects.py`（逐条摊开两边原文与落地树）、
`_t1503_make_mv_demo.py` + `_t1504_prep_mv_case.py`（教程夹具与每步的现场）、
`_t1505_capture_mv_tut.py`（33 个案例真跑录制）、`_t1506_probe_mv_extra.py`（尾斜杠与 CRLF）、
`_t1507_update_teach00.py` + `_t1508_update_progress_status.py`（索引与进度页更新）、
`_t1509_show_skipped_blocks.py`（列核对器跳过的块）。
逐条结论见 `teach/30` 的「实测出的与 GNU coreutils 8.32 的差异」一节。

<!-- mv-findings:end -->
"""


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    if START in text:
        print("mv-findings 段已在位，跳过")
        return 0
    if ANCHOR not in text:
        print(f"!! 找不到锚点 {ANCHOR!r}")
        return 1

    # 插在 cp-findings 段之后（按轮次往后排）
    text = text.replace(ANCHOR, ANCHOR + BLOCK, 1)

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
    if after.count(START) != 1 or after.count(END) != 1:
        print("!! 标记段数量不对")
        return 1
    print(f"mv-findings 段已插入（{len(BLOCK.encode('utf-8'))} 字节），换行风格不变 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
