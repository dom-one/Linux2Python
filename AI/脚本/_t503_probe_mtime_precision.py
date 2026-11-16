"""探针三：核对 GNU（MSYS）侧与本机 Python 侧的 mtime 精度差异。

怀疑：MSYS 的 stat() 只保留秒级精度，所以 GNU mv -u 在两个「同一秒内创建」
的文件之间判不出新旧。第一轮探针里 -u 的表现正是这样（明明 b.txt 更晚创建，
却没被搬走），这里实测确认一下。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GNU_STAT = shutil.which("stat")
if GNU_STAT is None:
    raise SystemExit("本机找不到 GNU stat")


def main() -> int:
    sandbox = Path(tempfile.mkdtemp(prefix="mtime_"))
    first = sandbox / "first.txt"
    second = sandbox / "second.txt"
    first.write_bytes(b"1")
    second.write_bytes(b"2")

    print("Python 侧:")
    print("  first  st_mtime =", os.stat(first).st_mtime)
    print("  second st_mtime =", os.stat(second).st_mtime)
    print("  second st_mtime_ns =", os.stat(second).st_mtime_ns)
    print("  差值（秒） =", os.stat(second).st_mtime - os.stat(first).st_mtime)

    print("MSYS stat 侧:")
    for name in ("first.txt", "second.txt"):
        out = subprocess.run(
            [GNU_STAT, "-c", "%n  mtime=%Y  mtime_ns=%.9Y  size=%s", name],
            cwd=str(sandbox),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        print("  ", out.stdout.decode("utf-8", "replace").strip())

    print("MSYS stat 侧（%y 全精度）:")
    for name in ("first.txt", "second.txt"):
        out = subprocess.run(
            [GNU_STAT, "-c", "%n  %y", name],
            cwd=str(sandbox),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        print("  ", out.stdout.decode("utf-8", "replace").strip())

    # 再测一个「隔了 2 秒」的文件对，看 GNU mv -u 会不会动
    old = sandbox / "old.txt"
    new = sandbox / "new.txt"
    old.write_bytes(b"old")
    os.utime(old, (1_000_000_000, 1_000_000_000))
    new.write_bytes(b"new")
    os.utime(new, (1_000_002_000, 1_000_002_000))
    proc = subprocess.run(
        [shutil.which("mv"), "-u", "new.txt", "old.txt"],
        cwd=str(sandbox),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    print("GNU mv -u（相差 2 秒）:", proc.returncode, proc.stderr.decode("utf-8", "replace"))
    print("  old.txt 还在?", (sandbox / "old.txt").exists())
    print("  new.txt 还在?", (sandbox / "new.txt").exists())

    shutil.rmtree(sandbox, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
