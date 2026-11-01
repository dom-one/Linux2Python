"""核对 ls -l 的权限位与时间列格式，为写教程取真实依据。

只读为主：仅在 AI/数据/ 下建临时文件，不碰仓库源码与 teach/。
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "AI" / "数据"


def run(argv: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "ls", *argv],
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="_t25_ls_", dir=str(DATA)))

    plain = tmp / "plain.txt"
    plain.write_text("x\n", encoding="utf-8")

    readonly = tmp / "readonly.txt"
    readonly.write_text("x\n", encoding="utf-8")
    os.chmod(readonly, 0o444)

    exe = tmp / "tool.exe"
    exe.write_bytes(b"MZ\x90\x00")

    sub = tmp / "sub"
    sub.mkdir()

    old = tmp / "old.txt"
    old.write_text("x\n", encoding="utf-8")
    old_time = time.time() - 400 * 24 * 60 * 60
    os.utime(old, (old_time, old_time))

    print("=== ls -l 各种类型 ===")
    code, out, err = run(["-l", str(tmp)])
    print("退出码: %d" % code)
    print(out)
    print("stderr: %r" % err)

    print("=== ls -lh（看大小缩写与对齐）===")
    big = tmp / "big.bin"
    big.write_bytes(b"\x00" * 5000)
    code, out, err = run(["-lh", str(tmp)])
    print("退出码: %d" % code)
    print(out)

    print("=== os.stat 原始权限位 ===")
    for path in (plain, readonly, exe, sub):
        st = os.lstat(path)
        print("%-12s mode=%s oct=%s exec_bit=%s"
              % (path.name, st.st_mode, oct(st.st_mode), bool(st.st_mode & 0o111)))

    # 清理
    for path in sorted(tmp.rglob("*"), reverse=True):
        if path.is_dir():
            os.rmdir(path)
        else:
            os.chmod(path, 0o666)
            path.unlink()
    os.rmdir(tmp)
    print("临时目录已清理: %s" % tmp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
