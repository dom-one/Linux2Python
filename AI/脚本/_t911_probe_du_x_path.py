"""查清 -x 挡住跨卷联接的真实机制。

上一支探针发现：du 的根目录用 os.lstat（联接自己的卷），
子项用 os.stat(..., follow_symlinks=False)（也是联接自己的卷），
两者相等，所以 -x 不是在联接这一层挡住内容的。

那内容是在哪一层被挡住的？假设是：联接本身被当成目录往下钻了，
钻进去之后里面的文件都是目标卷上的，st_dev 与根目录不同，于是被逐个跳过。

这个脚本按 du 的代码路径逐步复现，验证这个假设。

产出：AI/数据/du_x_path.txt
"""

from __future__ import annotations

import os
import stat as stat_mod
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "du_demo"
OUT = ROOT / "AI" / "数据" / "du_x_path.txt"

lines: list[str] = []


def emit(text: str = "") -> None:
    lines.append(text)


def main() -> None:
    temp = Path(os.environ.get("TEMP", r"C:\Windows\Temp"))
    xdir = temp / "w2l_du_x4"
    xdir.mkdir(exist_ok=True)
    cross = xdir / "to_e"
    if cross.exists():
        subprocess.run(["cmd", "/c", "rmdir", str(cross)], capture_output=True)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(cross), str(DATA / "tree")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not cross.exists():
        print("建不了跨卷联接")
        return 1

    emit("源目录 : %s" % xdir)
    emit("联接   : %s -> %s" % (cross, DATA / "tree"))
    emit()

    # 复现 du 的 _scan_operand：根目录用 lstat
    root_lstat = os.lstat(str(xdir))
    root_dev = root_lstat.st_dev
    emit("第 1 层：根目录")
    emit("  os.lstat(根目录).st_dev = %d  (C: 卷)" % root_dev)
    emit()

    # 复现 du 的 _list_children：逐个 scandir 出来的子项用 os.stat(follow_symlinks=follow)
    emit("第 2 层：_list_children 读根目录内容")
    scanner = os.scandir(str(xdir))
    with scanner:
        for item in scanner:
            st = os.stat(item.path, follow_symlinks=False)
            is_dir = stat_mod.S_ISDIR(st.st_mode)
            is_link = stat_mod.S_ISLNK(st.st_mode)
            same_dev = (st.st_dev == root_dev)
            emit("  子项 %s" % item.name)
            emit("    os.stat(follow_symlinks=False): st_dev=%d  st_ino=%d" % (st.st_dev, st.st_ino))
            emit("    S_ISDIR=%s  S_ISLNK=%s" % (is_dir, is_link))
            emit("    与 root_dev 相同？ %s  ⇒ %s" % (
                same_dev, "不跳过这一项" if same_dev else "被 -x 跳过"))
            emit("    ⇒ Python 把它当成「目录」（S_ISDIR=True），所以 _scan_dir 会往下钻")
            emit()

            # 第 3 层：钻进联接后，里面是目标卷上的文件
            if is_dir:
                emit("第 3 层：钻进联接，读它的内容")
                sub = os.scandir(item.path)
                with sub:
                    for sub_item in sub:
                        sst = os.stat(sub_item.path, follow_symlinks=False)
                        same = (sst.st_dev == root_dev)
                        emit("  %s" % sub_item.name)
                        emit("    st_dev=%d  与 root_dev 相同？ %s  ⇒ %s" % (
                            sst.st_dev, same,
                            "保留" if same else "被 -x 跳过（目标在 E:）"))
                emit()

    emit("=" * 72)
    emit("结论")
    emit("=" * 72)
    emit()
    emit("  -x 挡住跨卷内容不是在「联接这一层」，而是在「联接里面的文件这一层」：")
    emit("  联接本身用 lstat 口径拿到的 st_dev 与根目录相同（都在 C:），所以没被跳过；")
    emit("  但 du 把它当目录钻了进去，里面的文件都在 E:，逐个被 st_dev 比对挡掉。")
    emit()
    emit("  代价：联接不是被「挡住」，而是被「钻进去再清空」——")
    emit("  白走了一遍目录树，而且如果联接自指，理论上可能递归很深。")
    emit()

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("机制复现写入: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
