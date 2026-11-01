"""验证 os.lstat 与 os.scandir 的 DirEntry.stat() 在 Windows 上是否给同一份 st_mode。

怀疑：ls.py 用 os.scandir 读目录，DirEntry.stat() 的 st_mode 与 os.lstat() 不一样，
导致 .exe 的执行位在 ls -l / ls -F 里表现不一致。
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from w2l.commands.ls import _format_perms, _type_marker, _Entry  # noqa: E402


def render(mode: int, name: str) -> str:
    entry = _Entry(name, mode, 0, 0.0)
    return "perm=%-11s marker=%r" % (_format_perms(entry), _type_marker(entry))


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="_t27_stat_"))
    names = ["plain.txt", "tool.exe", "run.bat", "run.cmd", "tool.com"]
    for name in names:
        (tmp / name).write_bytes(b"x" * 3)
    (tmp / "sub").mkdir()

    print("%-12s | %-42s | %-42s" % ("name", "os.lstat()", "scandir DirEntry.stat()"))
    print("-" * 110)

    scandir_map = {}
    with os.scandir(tmp) as scanner:
        for item in scanner:
            scandir_map[item.name] = item.stat(follow_symlinks=False).st_mode

    for name in sorted(os.listdir(tmp)):
        lmode = os.lstat(tmp / name).st_mode
        dmode = scandir_map[name]
        same = "同" if lmode == dmode else "★不同"
        print("%-12s | %-42s | %-42s %s"
              % (name, "%s %s" % (oct(lmode), render(lmode, name)),
                 "%s %s" % (oct(dmode), render(dmode, name)), same))

    for path in sorted(tmp.rglob("*"), reverse=True):
        if path.is_dir():
            os.rmdir(path)
        else:
            os.chmod(path, 0o666)
            path.unlink()
    os.rmdir(tmp)
    print("临时目录已清理")
    return 0


if __name__ == "__main__":
    sys.exit(main())
