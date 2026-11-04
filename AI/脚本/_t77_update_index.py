"""更新 teach/00-项目总览与阅读顺序.md 的索引表。

只做「就地插入表格行」和被这次插入连带影响的计数修正，
不重写整个文件。

改三处：
1. 依赖表末尾插入 19 行
2. 「19 篇」相关的计数改成 20 篇（本文件数变了）
3. 路线 B 的 w2l 核心模块链条里补上 19（entry.py 是核心模块，读者要读）

写法上先把结果写进 .preview，跑完断言再 os.replace 覆盖原文件，
避免下标偏移或围栏配对算错把文件写坏。

跑法：
    python AI/脚本/_t77_update_index.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TARGET = os.path.join(ROOT, "teach", "00-项目总览与阅读顺序.md")
PREVIEW = TARGET + ".preview"


def main() -> None:
    with open(TARGET, "r", encoding="utf-8", newline="") as fh:
        original = fh.read()

    text = original

    # --- 1. 依赖表末尾插入 19 行 -------------------------------------
    anchor = "| 18 | `w2l/__init__.py` 包标记与版本号 | 02、09 |\n"
    if anchor not in text:
        raise SystemExit("找不到依赖表 18 行锚点，文件结构可能变了")
    if "| 19 |" in text:
        raise SystemExit("依赖表里已经有 19 行了，别重复插入")

    new_row = "| 19 | `w2l/entry.py` 入口名跟随调用方式 | 02、09 |\n"
    text = text.replace(anchor, anchor + new_row, 1)

    # --- 2. 件数 19 -> 20 -------------------------------------------
    count_edits = [
        ("教程拆成 19 篇而不是一篇", "教程拆成 20 篇而不是一篇"),
        ("给出 19 篇之间的依赖顺序表", "给出 20 篇之间的依赖顺序表"),
        ("讲某个文件的实现细节（那是 01～18 的职责）",
         "讲某个文件的实现细节（那是 01～19 的职责）"),
    ]
    for old, new in count_edits:
        if old not in text:
            raise SystemExit("找不到计数片段：%s" % old)
        text = text.replace(old, new, 1)

    # --- 3. 路线 B 的核心模块链条补 19 -------------------------------
    route_old = ("4. `04-w2l-context.py-运行上下文.md` → "
                 "`05-w2l-errors.py-异常与退出码.md` → "
                 "`06-w2l-commands-指令自动发现.md`")
    route_new = ("4. `04-w2l-context.py-运行上下文.md` → "
                 "`05-w2l-errors.py-异常与退出码.md` → "
                 "`06-w2l-commands-指令自动发现.md` → "
                 "`19-w2l-entry.py-入口名跟随调用方式.md`")
    if route_old not in text:
        raise SystemExit("找不到路线 B 的链条片段")
    text = text.replace(route_old, route_new, 1)

    # --- 断言：改完之后该有的都有 ------------------------------------
    assert text != original, "内容没有任何变化"
    assert "| 19 | `w2l/entry.py` 入口名跟随调用方式 | 02、09 |" in text
    assert "| 18 | `w2l/__init__.py` 包标记与版本号 | 02、09 |" in text
    assert "教程拆成 20 篇而不是一篇" in text
    assert "给出 20 篇之间的依赖顺序表" in text
    assert "01～19 的职责" in text
    assert "`19-w2l-entry.py-入口名跟随调用方式.md`" in text
    assert "教程拆成 19 篇" not in text
    assert "给出 19 篇" not in text
    assert "01～18 的职责" not in text

    # 四个固定小节还得在
    for heading in ("## 为什么这么创建", "## 这个文件是做什么",
                    "## 有什么用", "## 怎么用（过程教程）"):
        assert heading in text, "小节标题丢了：%s" % heading

    # 表格行数不变差（依赖表应为 20 行：00..19）
    dep_rows = [ln for ln in text.splitlines()
                if ln.startswith("| ") and "w2l/" in ln or
                (ln.startswith("| ") and "命令" in ln)]
    assert len(text.splitlines()) == len(original.splitlines()) + 1, \
        "总行数应该只多 1 行（依赖表插一行）"

    with open(PREVIEW, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)

    # 预览文件再读回来核对一遍，确认编码和内容都对
    with open(PREVIEW, "r", encoding="utf-8", newline="") as fh:
        check = fh.read()
    assert check == text, "预览文件和写入内容不一致"

    os.replace(PREVIEW, TARGET)
    print("已更新 %s" % TARGET)
    print("  依赖表新增 19 行，件数 19->20，路线 B 补 19")
    print("  预览行数 %d -> 最终行数 %d" % (len(original.splitlines()),
                                            len(text.splitlines())))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
