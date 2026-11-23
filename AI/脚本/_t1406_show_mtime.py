"""打印或比较文件/目录的最后修改时间（UTC）。

用法:
    python AI/脚本/_t1406_show_mtime.py <路径> [更多路径...]
    python AI/脚本/_t1406_show_mtime.py --cmp <路径A> <路径B>

给 teach/29 用：cp 的 -p / -a / --preserve=timestamps 到底有没有把源的
时间戳搬过来，只看「复制后两个文件的 mtime 是不是同一个」最直观。

普通模式打印 `<路径>  <UTC 时间>`。
--cmp 模式只打印「相同」或「不同」——复制时刻是「现在」，
把具体时间写进教程的预期输出会让每次核对都失败。
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path


def stamp_of(path: Path) -> dt.datetime | None:
    try:
        return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
    except OSError:
        return None


def show(path_text: str) -> int:
    path = Path(path_text)
    when = stamp_of(path)
    if when is None:
        print(f"{path_text}  <读不到>")
        return 1
    print(f"{path_text}  {when.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    return 0


def compare(left_text: str, right_text: str) -> int:
    left = stamp_of(Path(left_text))
    right = stamp_of(Path(right_text))
    if left is None or right is None:
        print("读不到时间戳")
        return 1
    print("相同" if left == right else "不同")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args:
        sys.stderr.write("用法: python AI/脚本/_t1406_show_mtime.py [--cmp] <路径> [...]\n")
        return 2
    if args[0] == "--cmp":
        if len(args) != 3:
            sys.stderr.write("--cmp 需要正好两个路径\n")
            return 2
        return compare(args[1], args[2])
    return max(show(item) for item in args)


if __name__ == "__main__":
    sys.exit(main())
