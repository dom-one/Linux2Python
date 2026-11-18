"""探针五（修正）：-x 为什么把整棵树都过滤掉了？

现象：tree -x <目录> 输出只有根目录一行，统计是 0 directories, 0 files。

上一版探针用 Path.stat() 量，目录与文件的 st_dev 完全一样，
所以过滤条件 st.st_dev != state.root_dev 不该命中。
但 tree 里读子项用的是 os.scandir() 出来的 DirEntry.stat(follow_symlinks=False)，
这条路径在 Windows 上和 Path.stat() 走的不是同一个 API，st_dev 可能不一样。

做法：同一个目录里，对每个条目分别量 Path.stat() 与 DirEntry.stat() 的 st_dev，
并把 tree 的 root_dev（根目录 lstat 的 st_dev）一起打出来对比。
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = Path(os.path.dirname(os.path.dirname(HERE)))
DEMO = ROOT / "AI" / "数据" / "tree_demo"


def show(path: Path) -> None:
    try:
        st = path.stat()
    except OSError as exc:
        print(f"  {path}  stat 失败：{exc}")
        return
    kind = "目录" if stat.S_ISDIR(st.st_mode) else "文件"
    print(f"  {str(path):<52} {kind}  Path.stat st_dev={st.st_dev}")


def main() -> None:
    print("=== 1. Path.stat() 量到的 st_dev ===")
    show(DEMO)
    show(DEMO / "sub")
    show(DEMO / "a.txt")
    show(ROOT / "w2l")
    show(ROOT / "w2l" / "cli.py")

    print("\n=== 2. os.scandir() 的 DirEntry.stat(follow_symlinks=False) 量到的 st_dev ===")
    root_dev = DEMO.lstat().st_dev
    print(f"  根目录 lstat st_dev = {root_dev}（tree 拿这个当 state.root_dev）")
    with os.scandir(DEMO) as scanner:
        for item in scanner:
            st = item.stat(follow_symlinks=False)
            kind = "目录" if stat.S_ISDIR(st.st_mode) else "文件"
            same = st.st_dev == root_dev
            print(
                f"  {item.name:<16} {kind}  DirEntry st_dev={st.st_dev}"
                f"  与 root_dev 相同：{same}"
            )

    print("\n=== 3. 子目录里再看一层（scandir 递归） ===")
    with os.scandir(DEMO / "sub") as scanner:
        for item in scanner:
            st = item.stat(follow_symlinks=False)
            print(f"  sub/{item.name:<12}  DirEntry st_dev={st.st_dev}")

    print("\n=== 4. 对比 Path.stat 与 DirEntry.stat 在同一个文件上的差别 ===")
    target = DEMO / "a.txt"
    print(f"  Path.stat         : {target.stat().st_dev}")
    with os.scandir(DEMO) as scanner:
        for item in scanner:
            if item.name == "a.txt":
                print(f"  DirEntry.stat     : {item.stat(follow_symlinks=False).st_dev}")
                print(f"  DirEntry.stat(fl=True): {item.stat(follow_symlinks=True).st_dev}")

    print("\n=== 5. 别的卷 ===")
    for path in (Path(r"C:\Windows"), Path(r"C:\Windows\notepad.exe")):
        try:
            print(f"  {path}  st_dev={path.stat().st_dev}")
        except OSError as exc:
            print(f"  {path}  stat 失败：{exc}")


if __name__ == "__main__":
    main()
