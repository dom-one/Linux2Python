"""探针二：Windows 目录联接（junction）在 tree 里被当成普通目录，
那么「联接指回自己的祖先」会不会造成无限递归？

背景：tree.py 用 stat.S_ISLNK 判符号链接，而 Windows 的目录联接在
lstat 里 S_ISLNK=False、S_ISDIR=True（探针一已实测），
所以联接会被当普通目录无条件展开。

做法：在目录里建一个指向自己的联接，然后跑 tree，
用超时确认它是不是无限往下递归。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = Path(ROOT) / "AI" / "数据" / "tree_junction"


def _make_junction(link: Path, target: Path) -> bool:
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        timeout=30,
    )
    return proc.returncode == 0


def _run(argv: list[str], cwd: str, timeout: int) -> tuple[int, str, str, bool]:
    """返回 (退出码, stdout, stderr, 是否超时)。"""
    try:
        proc = subprocess.run(
            [sys.executable, "main.py", *argv],
            cwd=cwd,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return -1, "", "", True
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", errors="replace"),
        proc.stderr.decode("utf-8", errors="replace"),
        False,
    )


def main() -> None:
    base = DATA / "selfref"
    if base.exists():
        # 先把联接摘掉再删目录，否则删不干净
        subprocess.run(["cmd", "/c", "rmdir", str(base / "loop")], capture_output=True)
        subprocess.run(["cmd", "/c", "rmdir", str(base)], capture_output=True)
    base.mkdir(parents=True)
    (base / "leaf.txt").write_bytes(b"x\n")

    print("=== 建一个指向自己的联接 base/loop -> base ===")
    ok = _make_junction(base / "loop", base)
    print(f"  mklink /J 成功：{ok}")

    print("\n=== 跑 tree（超时 15 秒） ===")
    start = time.time()
    code, out, err, timed_out = _run(["tree", str(base)], cwd=ROOT, timeout=15)
    elapsed = time.time() - start
    print(f"  耗时 {elapsed:.1f} 秒  退出码 {code}  超时：{timed_out}")
    print(f"  stdout 行数：{len(out.splitlines())}")
    print(f"  stdout 末尾 12 行：")
    for line in out.splitlines()[-12:]:
        print(f"    {line}")
    if err.strip():
        print(f"  stderr：{err.strip()[:400]}")
    if timed_out:
        print("  >>> 结论：tree 在联接上无限递归，超时被掐掉")
    else:
        print("  >>> 结论：tree 正常结束")

    print("\n=== 深度有多少层？ ===")
    if out:
        deepest = max((len(line) for line in out.splitlines()), default=0)
        print(f"  最长的一行 {deepest} 字符")


if __name__ == "__main__":
    main()
