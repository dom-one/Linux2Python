"""复核修 tree.py 要用的两件事：目录联接的判定手段、MSYS 侧的显示惯例。

产出：AI/数据/tree_link_probe.txt
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "tree_defect_demo"
OUT = ROOT / "AI" / "数据" / "tree_link_probe.txt"

lines: list[str] = []


def emit(text: str = "") -> None:
    lines.append(text)


def main() -> None:
    base = DATA / "junction_demo"
    link = base / "link_to_sub"
    target = base / "sub"
    plain = base / "plain_dir"

    emit("=" * 72)
    emit("一、目录联接的判定手段")
    emit("=" * 72)
    emit()
    emit("Python 版本：%s" % subprocess.run(
        ["python", "-V"], capture_output=True, text=True).stdout.strip())

    for label, path in (("目录联接 link_to_sub", link), ("普通目录 sub", target)):
        emit("--- %s ---" % label)
        if not path.exists():
            emit("  路径不存在，跳过")
            emit()
            continue
        st = os.lstat(path)
        emit("  st_mode              = %o" % st.st_mode)
        emit("  S_ISLNK              = %s" % stat.S_ISLNK(st.st_mode))
        emit("  S_ISDIR              = %s" % stat.S_ISDIR(st.st_mode))
        emit("  st_file_attributes   = %s" % getattr(st, "st_file_attributes", "（无此属性）"))
        reparse = getattr(st, "st_reparse_tag", None)
        emit("  st_reparse_tag       = %s" % (reparse if reparse is not None else "（无此属性）"))
        tag = getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", None)
        emit("  stat.IO_REPARSE_TAG_MOUNT_POINT = %s" % tag)
        if reparse is not None and tag is not None:
            emit("  是目录联接（reparse_tag 相等）：%s" % (reparse == tag))
        try:
            emit("  os.readlink()        = %r" % os.readlink(path))
        except OSError as exc:
            emit("  os.readlink()        失败：%s" % exc)
        emit()

    emit("--- 普通目录上 os.readlink 是否会误判 ---")
    if plain.is_dir():
        plain.mkdir(exist_ok=True)
    try:
        os.readlink(plain)
        emit("  普通目录 readlink 竟然成功了（不该）")
    except OSError as exc:
        emit("  普通目录 readlink 失败（符合预期）：%s" % exc.strerror)
    emit()

    emit("=" * 72)
    emit("二、MSYS 侧的显示惯例（Git Bash 的 ls -l）")
    emit("=" * 72)
    emit()
    proc = subprocess.run(
        ["ls", "-l", str(base)], capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    for line in proc.stdout.splitlines():
        emit("  | %s" % line)
    emit()

    emit("--- MSYS 的 readlink 输出 ---")
    proc = subprocess.run(
        ["readlink", str(link)], capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    emit("  readlink 退出码 %s" % proc.returncode)
    emit("  readlink 输出   %r" % proc.stdout.strip())
    emit()

    emit("=" * 72)
    emit("三、-x 的判定：跨卷时 st_dev 是否真的不同")
    emit("=" * 72)
    emit()
    emit("  E 盘（工作区）st_dev = %s" % Path("E:/").lstat().st_dev)
    try:
        emit("  C 盘 st_dev           = %s" % Path("C:/").lstat().st_dev)
    except OSError as exc:
        emit("  C 盘读不到：%s" % exc)
    emit()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("已写出 %s（%d 行）" % (OUT, len(lines)))


if __name__ == "__main__":
    main()
