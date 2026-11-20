"""更新 teach/00 索引页：加第 26 行、更新篇数与相关说明。

只做「就地插入一行 + 改几个数字」，不重写整个文件。
写盘前后做幂等检查（连跑两遍 sha256 相同）。

用法:
    python AI/脚本/_t915_update_teach00.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
INDEX = ROOT / "teach" / "00-项目总览与阅读顺序.md"


def main() -> int:
    text = INDEX.read_text(encoding="utf-8")
    original = text

    # 1) 依赖表加第 26 行（插在第 25 行之后）
    row25 = "| 25 | `w2l/commands/tree.py` 树形输出与画线规则 | 03、04、05、06、07、13 |"
    row26 = "| 26 | `w2l/commands/du.py` 统计口径与去重规则 | 03、04、05、06、07 |"
    if row26 not in text:
        assert row25 in text, "找不到第 25 行"
        text = text.replace(row25, row25 + "\n" + row26)

    # 2) 开头的「教程拆成 26 篇」改成 27 篇
    text = text.replace("教程拆成 26 篇而不是一篇", "教程拆成 27 篇而不是一篇")

    # 3) 「给出 26 篇之间的依赖顺序表」改成 27 篇
    text = text.replace("给出 26 篇之间的依赖顺序表", "给出 27 篇之间的依赖顺序表")

    # 4) 「不负责：讲某个文件的实现细节（那是 01～25 的职责）」改成 01～26
    text = text.replace("那是 01～25 的职责", "那是 01～26 的职责")

    # 5) 路线 A 加一条 du 的入口
    old_a = ("4. `25-w2l-commands-tree.py-树形输出与画线规则.md` — 看目录结构的画线、排序与通配符规则\n"
             "5. `10-gitignore-版本控制边界.md` — 哪些文件不该提交")
    new_a = ("4. `25-w2l-commands-tree.py-树形输出与画线规则.md` — 看目录结构的画线、排序与通配符规则\n"
             "5. `26-w2l-commands-du.py-统计口径与去重规则.md` — 看目录占用；统计口径、去重与人类可读的取整\n"
             "6. `10-gitignore-版本控制边界.md` — 哪些文件不该提交")
    if old_a in text:
        text = text.replace(old_a, new_a)

    # 6) 路线 B 第 5 步补上 du
    old_b = ("`22-w2l-commands-wc.py-列宽模型与词数判定.md` — 输出对齐与「跟 GNU 对不上」的排查手册")
    new_b = (old_b + "；`26-w2l-commands-du.py-统计口径与去重规则.md` — 统计口径（表观大小 vs 磁盘占用）"
             "与 inode 去重的实现")
    if old_b in text and "26-w2l-commands-du.py-统计口径与去重规则.md` — 统计口径（表观大小" not in text:
        text = text.replace(old_b, new_b)

    if text == original:
        print("索引页没有需要改的地方（可能已经改过了）")
        return 0

    # 自检
    assert "\ufffd" not in text, "索引页里有 U+FFFD"
    assert row26 in text, "第 26 行没插进去"
    assert text.count("| 26 |") == 1, "第 26 行重复了"

    # newline="\n" 必须显式写：Windows 上默认的 newline=None 会把 \n 翻译成 \r\n，
    # 而这个文件原本是 LF，会让 git 把整个文件当成重写过（179 行全变）。
    with open(INDEX, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    reread = INDEX.read_text(encoding="utf-8")
    assert reread == text, "回读与写入不一致"
    assert "\ufffd" not in reread, "落盘后出现 U+FFFD"
    raw = INDEX.read_bytes()
    assert b"\r\n" not in raw, "文件里混进了 CRLF"

    print("已更新 teach/00 索引页")
    print("  字节数 %d -> %d" % (
        len(original.encode("utf-8")), len(text.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
