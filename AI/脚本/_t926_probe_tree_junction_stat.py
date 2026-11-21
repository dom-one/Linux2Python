"""复核修 tree.py 要用的联接判定细节：跟随与不跟随时 st_dev/st_mode 的差别。

产出：AI/数据/tree_junction_stat.txt
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "tree_defect_demo"
OUT = ROOT / "AI" / "数据" / "tree_junction_stat.txt"

lines: list[str] = []


def emit(text: str = "") -> None:
    lines.append(text)


def main() -> None:
    base = DATA / "junction_demo"
    link = base / "link_to_sub"
    target = base / "sub"

    emit("=" * 72)
    emit("联接与目标目录的 stat 对比")
    emit("=" * 72)
    emit()

    for label, path in (("联接 link_to_sub", link), ("目标目录 sub", target)):
        emit("--- %s ---" % label)
        lst = os.stat(path, follow_symlinks=False)
        emit("  os.stat(follow_symlinks=False)：")
        emit("    st_mode    = %o" % lst.st_mode)
        emit("    S_ISLNK    = %s" % stat.S_ISLNK(lst.st_mode))
        emit("    S_ISDIR    = %s" % stat.S_ISDIR(lst.st_mode))
        emit("    st_dev     = %s" % lst.st_dev)
        emit("    st_ino     = %s" % lst.st_ino)
        emit("    reparse    = %s" % getattr(lst, "st_reparse_tag", None))
        try:
            st = os.stat(path)
        except OSError as exc:
            emit("  os.stat(跟随) 失败：%s" % exc)
        else:
            emit("  os.stat(跟随)：")
            emit("    st_mode    = %o" % st.st_mode)
            emit("    S_ISLNK    = %s" % stat.S_ISLNK(st.st_mode))
            emit("    S_ISDIR    = %s" % stat.S_ISDIR(st.st_mode))
            emit("    st_dev     = %s" % st.st_dev)
            emit("    st_ino     = %s" % st.st_ino)
        emit()

    emit("=" * 72)
    emit("联接的 readlink 目标形态")
    emit("=" * 72)
    emit()
    try:
        raw = os.readlink(link)
        emit("  os.readlink 原始值：%r" % raw)
        emit("  去掉 \\\\?\\ 前缀后：%r" % (raw[4:] if raw.startswith("\\\\?\\") else raw))
    except OSError as exc:
        emit("  readlink 失败：%s" % exc)
    emit()

    emit("=" * 72)
    emit("自引用联接：跟随后的 st_ino 与父目录相同吗")
    emit("=" * 72)
    emit()
    emit("  （用来确认防环判定该用 (st_dev, st_ino) 还是别的键）")
    emit("  目标目录 sub 的 st_ino = %s" % os.stat(target, follow_symlinks=False).st_ino)
    emit("  联接本身（不跟随）的 st_ino = %s" % os.stat(link, follow_symlinks=False).st_ino)
    emit()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("已写出 %s（%d 行）" % (OUT, len(lines)))


if __name__ == "__main__":
    main()
