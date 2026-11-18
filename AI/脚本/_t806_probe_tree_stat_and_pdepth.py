"""探针六：两件事钉死。

一、DirEntry.stat() 在 Windows 上到底哪些字段是 0
    du.py 第 391~396 行已经写了注释说「st_dev 与 st_ino 全是 0」，
    tree.py 第 384 行还在用 item.stat()，这里逐字段对一遍，
    确认到底哪些字段受影响、哪些没受影响。

二、-P 命中目录时的展开范围
    README 说「某个目录命中 -P 时它下面的内容全部列出」，
    但 tree.py 里 _read_entries 用的是父层的 pattern_active，
    child_active 是读完 children 之后才算出来的。
    怀疑：命中目录的「直接子项」仍被模式过滤，只有「孙层」才整体展开。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = Path(os.path.dirname(os.path.dirname(HERE)))
DEMO = ROOT / "AI" / "数据" / "tree_demo"
DEEP = ROOT / "AI" / "数据" / "tree_deep"


def _run(argv: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, "main.py", *argv],
        cwd=str(ROOT),
        capture_output=True,
        timeout=60,
    )
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", errors="replace"),
        proc.stderr.decode("utf-8", errors="replace"),
    )


def probe_fields() -> None:
    print("=== 一、DirEntry.stat() vs os.stat(path) 逐字段对比 ===")
    with os.scandir(DEMO) as scanner:
        for item in scanner:
            if item.name != "a.txt":
                continue
            de = item.stat(follow_symlinks=False)
            direct = os.stat(item.path, follow_symlinks=False)
            for field in ("st_dev", "st_ino", "st_size", "st_mtime", "st_mode"):
                d = getattr(de, field)
                o = getattr(direct, field)
                flag = "  <<< 不一样" if d != o else ""
                print(f"  {field:<10} DirEntry={d!r:<24} os.stat={o!r}{flag}")
            break


def build_deep() -> None:
    """造一棵三层目录：hit/ 下面有 mid/，mid/ 下面有 leaf.txt 与 leaf2.txt。"""
    if DEEP.exists():
        return
    DEEP.mkdir(parents=True)
    (DEEP / "plain.txt").write_bytes(b"p\n")
    hit = DEEP / "hit"
    hit.mkdir()
    (hit / "direct.txt").write_bytes(b"d\n")
    mid = hit / "mid"
    mid.mkdir()
    (mid / "leaf.txt").write_bytes(b"l\n")
    (mid / "leaf2.txt").write_bytes(b"l2\n")


def probe_pattern_depth() -> None:
    print("\n=== 二、-P 命中目录时的展开范围 ===")
    build_deep()
    print("  夹具结构：")
    for base, dirs, names in os.walk(DEEP):
        dirs.sort()
        rel = Path(base).relative_to(DEEP)
        for name in sorted(names):
            print(f"    {rel / name}")
        for name in sorted(dirs):
            print(f"    {rel / name}/")

    for pattern in ("hit", "mid", "*.txt", "hit/mid"):
        code, out, err = _run(["tree", "-P", pattern, "AI/数据/tree_deep"])
        print(f"\n  tree -P '{pattern}'（退出码 {code}）：")
        for line in out.splitlines():
            print(f"    {line}")


if __name__ == "__main__":
    probe_fields()
    probe_pattern_depth()
