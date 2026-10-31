"""探测本机 os.stat 的实际行为，为 ls 指令的 -l 长格式确定字段来源。

Windows 没有 POSIX 的属主/属组/链接数语义，st_mode 的权限位是 Python 合成出来的，
取值跟真实文件权限对不上。这里把目录、普通文件、只读文件、可执行后缀文件的
mode / nlink / uid / gid / size 全部打出来，避免在实现里硬套 POSIX 假设。

用法：python AI/脚本/_t16_probe_ls.py
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path


def probe(path: Path) -> None:
    st = path.lstat()
    print(
        f"{path.name:<12}",
        f"mode={oct(st.st_mode)}",
        f"perm={oct(stat.S_IMODE(st.st_mode))}",
        f"nlink={st.st_nlink}",
        f"uid={st.st_uid}",
        f"gid={st.st_gid}",
        f"size={st.st_size}",
        f"blocks={getattr(st, 'st_blocks', 'n/a')}",
        f"is_dir={stat.S_ISDIR(st.st_mode)}",
        f"is_link={stat.S_ISLNK(st.st_mode)}",
    )


def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="w2l_probe_"))
    print(f"temp dir: {root}")
    print(f"os.name = {os.name}")

    plain = root / "plain.txt"
    plain.write_text("hello\n", encoding="utf-8")

    readonly = root / "readonly.txt"
    readonly.write_text("locked\n", encoding="utf-8")
    os.chmod(readonly, stat.S_IREAD)

    sub = root / "sub"
    sub.mkdir()

    exe = root / "tool.exe"
    exe.write_text("stub\n", encoding="utf-8")

    for target in (root, plain, readonly, sub, exe):
        probe(target)

    hidden = root / ".hidden"
    hidden.write_text("x", encoding="utf-8")
    print("scandir names:", sorted(e.name for e in os.scandir(root)))
    print("X_OK on .exe:", os.access(exe, os.X_OK))
    print("X_OK on .txt:", os.access(plain, os.X_OK))
    print("localtime sample:", __import__("time").strftime("%b %d %H:%M"))


if __name__ == "__main__":
    main()
