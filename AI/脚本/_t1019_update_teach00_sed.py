"""更新 teach/00-项目总览与阅读顺序.md：加第 27 篇（sed.py）并订正过期数字。

为什么写脚本而不是直接改：
teach/00 里有 27 处「只有文字佐证」的数字（各实现的行数、各测试文件的用例数），
本轮新增了一篇教程，这些数字都要跟着动。手工改容易漏，改脚本能保证
「每一处替换都命中、每处替换都有断言」，而且幂等（连跑两遍结果一样）。

改了什么：
1. 篇数 27 → 28
2. 结构树里 find.py / tree.py 的行数、test_find.py / test_tree.py 的用例数（过期）
3. 两条阅读路线加 sed.py
4. 依赖表加第 27 行

用法：python AI/脚本/_t1019_update_teach00_sed.py
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TARGET = ROOT / "teach" / "00-项目总览与阅读顺序.md"

# (说明, 旧串, 新串)
REPLACEMENTS: list[tuple[str, str, str]] = [
    ("篇数（正文）",
     "教程拆成 27 篇而不是一篇",
     "教程拆成 28 篇而不是一篇"),
    ("篇数（依赖表说明）",
     "给出 27 篇之间的依赖顺序表",
     "给出 28 篇之间的依赖顺序表"),
    ("各篇职责范围",
     "（那是 01～26 的职责）",
     "（那是 01～27 的职责）"),
    ("结构树 find.py 行数",
     "│       ├── find.py         # find 实现（905 行）",
     "│       ├── find.py         # find 实现（1002 行）"),
    ("结构树 tree.py 行数",
     "│       ├── tree.py         # tree 实现（575 行）",
     "│       ├── tree.py         # tree 实现（673 行）"),
    ("结构树 test_find.py 用例数",
     "│   ├── test_find.py        # 37 个用例",
     "│   ├── test_find.py        # 52 个用例"),
    ("结构树 test_tree.py 用例数",
     "│   ├── test_tree.py        # 34 个用例",
     "│   ├── test_tree.py        # 45 个用例"),
    ("路线 A 加 sed",
     "6. `10-gitignore-版本控制边界.md` — 哪些文件不该提交",
     "6. `27-w2l-commands-sed.py-地址语义与正则翻译.md` — 看按行改文本：地址语义、"
     "BRE/ERE 方言差别、原地修改\n7. `10-gitignore-版本控制边界.md` — 哪些文件不该提交"),
    ("路线 B 加 sed",
     "`26-w2l-commands-du.py-统计口径与去重规则.md` — 统计口径"
     "（表观大小 vs 磁盘占用）与 inode 去重的实现",
     "`26-w2l-commands-du.py-统计口径与去重规则.md` — 统计口径"
     "（表观大小 vs 磁盘占用）与 inode 去重的实现；"
     "`27-w2l-commands-sed.py-地址语义与正则翻译.md` — 地址为什么是有状态的判定、"
     "BRE 怎么翻译成正则、原地修改怎么原子替换"),
    ("依赖表加第 27 行",
     "| 26 | `w2l/commands/du.py` 统计口径与去重规则 | 03、04、05、06、07 |",
     "| 26 | `w2l/commands/du.py` 统计口径与去重规则 | 03、04、05、06、07 |\n"
     "| 27 | `w2l/commands/sed.py` 地址语义与正则翻译 | 03、04、05、06、07、21 |"),
]


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    changed = 0
    for label, old, new in REPLACEMENTS:
        # 顺序很重要：先看新串在不在。
        # 有些旧串是新串的子串（如「依赖表加第 27 行」那段），
        # 先判旧串会每次都再插一行，幂等性就破了。
        if new in text:
            print("  [已] %s" % label)
        elif old in text:
            if text.count(old) != 1:
                raise SystemExit("[%s] 旧串出现 %d 次，不唯一" % (label, text.count(old)))
            text = text.replace(old, new)
            changed += 1
            print("  [改] %s" % label)
        else:
            raise SystemExit("[%s] 既找不到旧串也找不到新串" % label)

    if "\ufffd" in text:
        raise SystemExit("正文里混进了坏字符 U+FFFD")

    with open(TARGET, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("[result] 已写入 %s（改动 %d 处）" % (TARGET, changed))
    print("[result] %d 字节，%d 行" % (len(text.encode("utf-8")), text.count("\n") + 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
