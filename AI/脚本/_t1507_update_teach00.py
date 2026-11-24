"""把 teach/30 登记进 teach/00 的索引页（就地插一行，不重写整个文件）。

用法:
    python AI/脚本/_t1507_update_teach00.py

改四处:
1. 「教程拆成 29 篇」→ 30 篇（正文里两处计数）
2. 「01～29 的职责」→ 01～30
3. 依赖表末尾加一行（编号 30）
4. 两条阅读路线里各加一条 mv 的入口

幂等性: 插入前先查「新串」在不在, 已在就跳过。
写完复算一遍行数与关键串, 保证连跑两遍 sha256 不变。
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DOC = ROOT / "teach" / "00-项目总览与阅读顺序.md"

ROW_30 = (
    "| 30 | `w2l/commands/mv.py` 落点判定与覆盖策略 | 03、04、05、06、07、29 |"
)
ROUTE_A_30 = (
    "7. `30-w2l-commands-mv.py-落点判定与覆盖策略.md` — 看移动文件："
    "落点怎么算、`-n`/`-u`/`-i`/`-b` 的覆盖策略、GNU 的 mv 为什么不合并目录"
)
ROUTE_B_30 = (
    "`30-w2l-commands-mv.py-落点判定与覆盖策略.md` — 移动动作的落点怎么算、"
    "覆盖策略的判定顺序、互斥选项「后给的那个赢」的共享判据"
)

# (旧串, 新串, 是否必需)
EDITS: list[tuple[str, str, bool]] = [
    ("教程拆成 29 篇而不是一篇", "教程拆成 30 篇而不是一篇", True),
    ("给出 29 篇之间的依赖顺序表", "给出 30 篇之间的依赖顺序表", True),
    ("（那是 01～29 的职责）", "（那是 01～30 的职责）", True),
    (
        "7. `27-w2l-commands-sed.py-地址语义与正则翻译.md` — 看按行改文本：地址语义、BRE/ERE 方言差别、原地修改",
        ROUTE_A_30 + "\n8. `27-w2l-commands-sed.py-地址语义与正则翻译.md` — 看按行改文本：地址语义、BRE/ERE 方言差别、原地修改",
        True,
    ),
    (
        "8. `10-gitignore-版本控制边界.md` — 哪些文件不该提交",
        "9. `10-gitignore-版本控制边界.md` — 哪些文件不该提交",
        True,
    ),
    (
        "属性保留的集合运算\n",
        "属性保留的集合运算；" + ROUTE_B_30 + "\n",
        True,
    ),
    (
        "| 29 | `w2l/commands/cp.py` 目标落点与属性保留 | 03、04、05、06、07 |",
        "| 29 | `w2l/commands/cp.py` 目标落点与属性保留 | 03、04、05、06、07 |\n" + ROW_30,
        True,
    ),
    # 结构树里 mv 的行数与用例数是上一轮写死的旧值，本轮实测已经变了。
    # 行数按 wc -l 口径（文件末尾有换行，所以等于换行符个数）。
    (
        "│       ├── mv.py           # mv 实现（405 行）",
        "│       ├── mv.py           # mv 实现（386 行）",
        True,
    ),
    (
        "│   ├── test_mv.py          # 51 个用例",
        "│   ├── test_mv.py          # 53 个用例",
        True,
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
    applied_edits: list[tuple[str, str]] = []
    for old, new, required in EDITS:
        if new in text:
            skipped += 1
            continue
        if old not in text:
            if required:
                print(f"!! 找不到待替换的旧串: {old[:60]!r}")
                return 1
            continue
        text = text.replace(old, new, 1)
        applied += 1
        applied_edits.append((old, new))

    # 写盘必须显式 newline=""：Windows 上 Path.write_text 默认把 \n 翻译成
    # \r\n，会让整个文件从 LF 翻成 CRLF，git diff 变成每个文件整篇重写
    # （tick #18 在删函数时踩过这个坑）。写前先记下原文件的换行风格。
    raw_before = DOC.read_bytes()
    crlf_before = raw_before.count(b"\r\n")
    with DOC.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)

    # 复算：行数与字节数的变化要跟改了什么对得上
    raw_after = DOC.read_bytes()
    crlf_after = raw_after.count(b"\r\n")
    if crlf_before != crlf_after:
        print(
            f"!! 换行风格被改了: CRLF {crlf_before} -> {crlf_after}，已回滚"
        )
        DOC.write_bytes(raw_before)
        return 1
    after = DOC.read_text(encoding="utf-8")
    after_bytes = len(after.encode("utf-8"))
    after_lines = after.count("\n")
    print(f"替换 {applied} 处，跳过（已在位）{skipped} 处")
    print(f"字节 {before_bytes} -> {after_bytes}，行 {before_lines} -> {after_lines}")
    print(f"换行风格保持: CRLF {crlf_after} 处不变 ✓")

    # 内容不变式：关键串必须都在
    checks = [
        ROW_30,
        "教程拆成 30 篇而不是一篇",
        "给出 30 篇之间的依赖顺序表",
        "01～30 的职责",
        "30-w2l-commands-mv.py-落点判定与覆盖策略.md",
        "mv 实现（386 行）",
        "test_mv.py          # 53 个用例",
    ]
    missing = [c for c in checks if c not in after]
    if missing:
        print("!! 写完后缺这些串:", missing)
        return 1

    # 行数不变式：行数增量必须等于「本次实际替换带来的换行数增量」。
    # 只能看**本次实际替换**的那些对——EDITS 里的旧串常常是新串的子串
    # （比如依赖表那行被包在新串中间），不能靠「old not in after」来判。
    newline_delta = 0
    for old, new in applied_edits:
        newline_delta += new.count("\n") - old.count("\n")
    if after_lines - before_lines != newline_delta:
        print(
            f"!! 行数变化 {after_lines - before_lines} 与预期 {newline_delta} 对不上"
        )
        return 1
    print(f"行数增量 {after_lines - before_lines}（预期 {newline_delta}）✓")

    print(f"当前 sha256: {sha(DOC)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
