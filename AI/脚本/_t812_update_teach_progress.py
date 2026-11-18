"""更新 AI/教程进度.md 的「当前状态」「教程清单」「已知问题」三处。

历史 tick 日志只能追加，这三处是每个 tick 都要改的现状区。

幂等要点（踩过的坑）：
- 插入点必须在「先删旧块」逻辑之内，否则重跑会重复插入
- 删除用 re.sub 不带 count，把全部旧块删干净再插一份
- 计数类数字要排除本脚本自身

用法:
    python AI/脚本/_t812_update_teach_progress.py
"""

from __future__ import annotations

import os
import re
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = Path(os.path.dirname(os.path.dirname(HERE)))
TARGET = ROOT / "AI" / "教程进度.md"

MARK_START = "<!-- tree-findings:start -->"
MARK_END = "<!-- tree-findings:end -->"

FINDINGS = """<!-- tree-findings:start -->
### 2026-11-19 tree.py 与项目文档的三处不一致（本轮实测）

给 `w2l/commands/tree.py` 写教程时实跑查出的。**本机没有 GNU tree**（Git Bash 里
`tree` 不是可执行命令，只有 Windows 自带的 `C:\\Windows\\System32\\tree.com`，
那是另一个工具），所以做不了字节级差分对照，断言按上游源码规则写死
（见 `tests/test_tree.py` 的文件头）。下面三处的证据是**项目自己的文档内部自相矛盾**，
不依赖 GNU tree：

| 现象 | 文档怎么说 | 实际是什么 | 根因位置 |
|---|---|---|---|
| `-x` 把整棵树都过滤掉，只剩根目录一行 | README 第 433 行：「`-x` 实际是不跨盘符……所以 `-x` 能挡住跨盘的子目录」 | 全部条目都被跳过，输出 `0 directories, 0 files` | `w2l/commands/tree.py` 第 384 行用 `item.stat()`，第 397 行拿 `st_dev` 比对 |
| `-P` 命中目录时少展开一层 | README 第 418 行：「某个目录命中 `-P` 时它下面的内容全部列出」；源码第 221 行注释同 | 命中目录的**直接子文件**仍被筛掉，只有孙层往下才整体展开 | `w2l/commands/tree.py` 第 218~224 行：`child_active` 在读完 children 之后才算 |
| 目录联接（junction）不被认成符号链接 | 源码第 154、387 行用 `stat.S_ISLNK` 判链接 | Windows 的联接 `S_ISLNK=False`、`S_ISDIR=True`，被当普通目录无条件展开，`-l` 对它无效 | `w2l/commands/tree.py` 全篇；`-l` 只在 `entry.is_link` 为真时才改变行为 |

第一处的根因值得单独记：**Windows 上 `os.scandir()` 出来的 `DirEntry.stat()` 的
`st_dev` 与 `st_ino` 恒为 0，而 `os.stat(path)` 给的是真的卷标识与 inode**
（实测同一个文件：`DirEntry.stat()` 的 st_dev=0，`os.stat()` 的 st_dev=18303321406201763453；
st_size / st_mtime / st_mode 两边一致）。**这个坑项目里已经踩过并修好了**——
`w2l/commands/du.py` 第 391~396 行写着注释「不能用 item.stat()：Windows 上它给的是
目录枚举的缓存结果，st_dev 与 st_ino 全是 0，硬链接去重与 -x 都会失效」，
改用 `os.stat(item.path, follow_symlinks=follow)`。tree.py 没跟着改，所以 `-x` 在 tree 里是坏的。

第三处的后果实测：目录里同时有联接与它的目标时内容被列两遍；
**自引用的联接会一路递归到 64 层**，直到 Windows 的路径长度上限把 `os.scandir` 挡下来
（报「系统无法辨识文件名」，tree 以退出码 2 结束，统计行报成 `65 directories, 64 files`）。

另有 README 第 429 行的权限位说明已过期：那一行还写着「目录是 `drwxrwxrwx`、
普通文件是 `-rw-rw-rw-`」，那是 `w2l/perms.py` 落地之前的旧口径，
实际输出是 `drwxr-xr-x` 与 `-rw-r--r--`（chmod 指令那一轮把 tree.py 的权限列
改成复用 `w2l/perms.py` 之后）。

以上四处都属源码与 README 范围（开发任务），本轮按只读原则没动。

实测脚本：`AI/脚本/_t802_probe_tree_edges.py`（联接与 st_dev）、
`_t803_probe_tree_junction.py`（自引用联接的递归）、`_t805_probe_tree_onefs.py`
（DirEntry.stat 与 os.stat 的逐字段对比）、`_t806_probe_tree_stat_and_pdepth.py`
（`-P` 的展开深度）、`_t807_probe_tree_misc.py`（操作数形态等）。
逐条结论见 `teach/25` 的「实测出的三处与项目文档不一致」一节。

<!-- tree-findings:end -->
"""


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")

    # 1. 头部两行
    text = re.sub(r"^最后更新：.*$", "最后更新：2026-11-19", text, count=1, flags=re.M)
    text = re.sub(
        r"^本次会话：.*$",
        "本次会话：cron tick（补充 w2l/commands/tree.py 教程，已完成 26 篇）",
        text,
        count=1,
        flags=re.M,
    )

    # 2. 当前状态的两行
    text = re.sub(r"^- 完成度：.*$", "- 完成度：26/26", text, count=1, flags=re.M)
    text = re.sub(
        r"^- 下一步：`w2l/commands/` 下还差 .*$",
        "- 下一步：`w2l/commands/` 下还差 `du.py`、`sed.py`、`awk_lite.py`、`cp.py`、`mv.py`、`rm.py`、`chmod.py` 七篇"
        "（`grep.py` 见 teach/07、`cat.py` 见 teach/21、`wc.py` 见 teach/22、`head.py` 见 teach/20、"
        "`tail.py` 见 teach/23、`find.py` 见 teach/24、`tree.py` 见 teach/25，`ls.py` 的内容被 teach/13 当例子覆盖过）；"
        "再往后是 `bin/` 下的两份启动器、`cron.md`、`AI/AGENTS.md`、`AI/脚本/_t10_lock.py`、`AI/脚本/_t11_progress.py`",
        text,
        count=1,
        flags=re.M,
    )

    # 3. 教程清单加一行（插在 find.py 那行后面）
    # 先把旧的第 26 行删掉（重跑时它已经在了），再插新的
    text = re.sub(r"^\| 26 \|.*$\n", "", text, flags=re.M)
    row = "| 26 | `w2l/commands/tree.py` | `25-w2l-commands-tree.py-树形输出与画线规则.md` | 已完成 |\n"
    anchor = "| 25 | `w2l/commands/find.py` | `24-w2l-commands-find.py-表达式语法与遍历语义.md` | 已完成 |\n"
    if anchor not in text:
        raise SystemExit("清单里找不到 find.py 那一行")
    text = text.replace(anchor, anchor + row, 1)

    # 4. 已知问题区插一段。
    #    删除与插入必须严格对称，否则每次重跑都会多出一个空行（字节数漂移）：
    #    删除时把「块 + 前后空行」整段吃掉换成两个换行，插入时也固定补两个换行。
    text = re.sub(
        r"\n*<!-- tree-findings:start -->.*?<!-- tree-findings:end -->\n*",
        "\n\n",
        text,
        flags=re.S,
    )
    anchor2 = "## 4. tick 日志"
    if anchor2 not in text:
        raise SystemExit("进度文件里找不到「## 4. tick 日志」")
    block = FINDINGS.strip("\n")
    text = text.replace(anchor2, block + "\n\n" + anchor2, 1)

    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"已更新 {TARGET}（{TARGET.stat().st_size} 字节）")


if __name__ == "__main__":
    main()
