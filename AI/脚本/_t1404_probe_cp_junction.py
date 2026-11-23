"""查 Windows 目录联接（junction）在 cp 两边的处理细节。

三个问题：
1. 普通联接（src/link -> src/real）被拷过去之后，两边落地的是什么？
2. 自引用联接（src/loop -> src）被拷过去时，本实现钻进去多少层才停？
3. GNU cp 8.32 为什么没钻进去？

用法:
    python AI/脚本/_t1404_probe_cp_junction.py
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "cp_probe2"
MAIN = ROOT / "main.py"
GNU_CP = shutil.which("cp")
REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def make_junction(link: Path, target: Path) -> bool:
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc.returncode == 0


def describe(path: Path) -> str:
    """一个条目的类型标签。"""
    if path.is_symlink():
        return "LINK"
    try:
        attrs = os.lstat(path).st_file_attributes
    except (OSError, AttributeError):
        attrs = 0
    if attrs & REPARSE:
        return "JUNC"
    return "DIR" if path.is_dir() else "FILE"


def tree(root: Path, limit: int = 40) -> list[str]:
    """只列前 limit 层，用相对路径排序。"""
    out: list[str] = []
    for current, dirs, files in os.walk(root):
        rel = Path(current).relative_to(root).as_posix()
        depth = 0 if rel == "." else len(Path(rel).parts)
        if depth >= limit:
            dirs[:] = []
        for name in dirs:
            out.append(f"{Path(current, name).relative_to(root).as_posix()}  [{describe(Path(current, name))}]")
        for name in files:
            out.append(f"{Path(current, name).relative_to(root).as_posix()}  [FILE]")
    return sorted(out)


def build_loop(root: Path) -> None:
    src = root / "src"
    src.mkdir(parents=True)
    (src / "file.txt").write_bytes(b"loop content\r\n")
    if not make_junction(src / "loop", src):
        raise RuntimeError("mklink /J 失败")


def build_plain_junction(root: Path) -> None:
    src = root / "src"
    (src / "real").mkdir(parents=True)
    (src / "real" / "file.txt").write_bytes(b"real content\r\n")
    if not make_junction(src / "link", src / "real"):
        raise RuntimeError("mklink /J 失败")


def run(argv: list[str], cwd: Path, python: bool) -> tuple[int, str, str]:
    cmd = [sys.executable, str(MAIN), "cp", *argv] if python else [GNU_CP, *argv]
    proc = subprocess.run(
        cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120
    )
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", "replace"),
        proc.stderr.decode("utf-8", "replace"),
    )


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    sandbox = Path(tempfile.mkdtemp(prefix="cpjunc_", dir=str(DATA)))
    print(f"沙箱: {sandbox}\n")

    for label, builder in (("普通联接", build_plain_junction), ("自引用联接", build_loop)):
        print("=" * 70)
        print(f"### {label}")
        for side, python in (("GNU", False), ("本实现", True)):
            base = sandbox / f"{label}-{side}"
            base.mkdir()
            gnu_dir = base / "w"
            gnu_dir.mkdir()
            builder(gnu_dir)
            rc, out, err = run(["-r", "src", "destdir"], gnu_dir, python)
            entries = tree(gnu_dir)
            deepest = max((len(Path(e.split("  ")[0]).parts) for e in entries), default=0)
            print(f"--- {side} --- rc={rc} 条目数={len(entries)} 最深={deepest} 层")
            for line in entries[:14]:
                print("   ", line)
            if len(entries) > 14:
                print(f"    ...（还有 {len(entries) - 14} 条）")
            if err.strip():
                tail = err.strip().splitlines()[-1]
                print(f"    stderr 末行: {tail[:200]}")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
