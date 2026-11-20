"""造 du 教程用的目录联接夹具，落在 AI/数据/du_demo/junc/。

Windows 上 Python 的 os.symlink 要管理员权限（实测 WinError 1314），
但 cmd 的 mklink /J 建目录联接不需要，所以用后者。

联接的 stat 特征（实测）：S_ISLNK=False、S_ISDIR=True —— Python 把它当普通目录，
所以 du 会钻进去；GNU 把联接当符号链接，只报它自己占的那一块。

产出：AI/数据/du_demo/junc/to_tree（指向 AI/数据/du_demo/tree 的联接）
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "du_demo"
JUNC = DATA / "junc"
LINK = JUNC / "to_tree"
TARGET = DATA / "tree"


def main() -> None:
    if not TARGET.is_dir():
        print("夹具不存在，先跑 _t900_make_du_fixture.py")
        return 1

    JUNC.mkdir(parents=True, exist_ok=True)
    if LINK.exists():
        # 联接不是普通目录，删它要用 cmd 的 rmdir
        subprocess.run(["cmd", "/c", "rmdir", str(LINK)], capture_output=True)

    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(LINK), str(TARGET)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")

    if not LINK.exists():
        print("建联接失败: %s" % (
            (proc.stdout.strip() or proc.stderr.strip())[:200]))
        return 1

    lst = os.lstat(str(LINK))
    import stat as stat_mod
    print("已生成 AI/数据/du_demo/junc/to_tree（目录联接）")
    print("  指向: AI/数据/du_demo/tree")
    print("  S_ISLNK=%s  S_ISDIR=%s" % (
        stat_mod.S_ISLNK(lst.st_mode), stat_mod.S_ISDIR(lst.st_mode)))
    # mklink 自己的输出是 GBK 编码且带中文路径，转成 UTF-8 会花，
    # 所以不打印它（联接建成了就够说明问题）
    return 0


if __name__ == "__main__":
    sys.exit(main())
