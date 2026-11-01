"""弄清 Windows 上 .exe 的权限位到底怎么合成，避免教程写错。

对比三件事：
1. os.lstat() 给的原始 st_mode
2. ls.py 的 _perm_bits() / _type_marker() 渲染出来的结果
3. 同一时刻 os.stat() 与 os.lstat() 是否一致
"""

from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from w2l.commands.ls import _perm_bits, _format_perms, _type_marker, _Entry  # noqa: E402


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="_t26_perm_"))
    plain = tmp / "plain.txt"
    plain.write_text("x\n", encoding="utf-8")
    exe = tmp / "tool.exe"
    exe.write_bytes(b"MZ\x90\x00")
    bat = tmp / "run.bat"
    bat.write_text("@echo off\n", encoding="ascii")
    sub = tmp / "sub"
    sub.mkdir()
    ro = tmp / "ro.txt"
    ro.write_text("x\n", encoding="utf-8")
    os.chmod(ro, 0o444)

    for path in (plain, exe, bat, sub, ro):
        st = os.lstat(path)
        entry = _Entry(path.name, st.st_mode, st.st_size, st.st_mtime)
        print("%-10s st_mode=%-8s oct=%-9s perm=%-11s marker=%r exec_bit=%s"
              % (path.name, st.st_mode, oct(st.st_mode),
                 _format_perms(entry), _type_marker(entry),
                 bool(st.st_mode & 0o111)))
        print("           _perm_bits=%r  S_ISREG=%s S_ISDIR=%s"
              % (_perm_bits(st.st_mode), stat.S_ISREG(st.st_mode), stat.S_ISDIR(st.st_mode)))

    # 再 stat 一次，确认前后一致（排除 chmod 的副作用）
    print()
    print("--- 第二次 lstat ---")
    for path in (plain, exe, bat, sub, ro):
        st = os.lstat(path)
        print("%-10s oct=%s" % (path.name, oct(st.st_mode)))

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
