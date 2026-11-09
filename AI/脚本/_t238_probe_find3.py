"""探针 3：确认两件事。

1. MSYS2 的 find.exe 是否在拿到参数之前就做了通配符展开（影响差分对照的可信度）。
2. GNU find 的 FNM_PERIOD 语义：* 是否匹配隐藏文件。
3. -mmin 的边界。

做法：在一个「顶层没有任何 .txt 文件」的目录里跑 find，
此时 `*.txt` 若被展开就会变成别的样子，若保持字面量则能正常匹配。
结果写到 _data_find3/probe3.txt。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "_data_find3"
GNU_FIND = shutil.which("find") or r"E:\software\Git\Git\usr\bin\find.exe"


def build_tree(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.txt").write_bytes(b"hello\n")
    (root / "B.txt").write_bytes(b"upper\n")
    (root / "c.md").write_bytes(b"# c\n")
    (root / ".hidden").write_bytes(b"x\n")
    (root / ".x.txt").write_bytes(b"hidden txt\n")
    sub = root / "sub"
    sub.mkdir(exist_ok=True)
    (sub / "c.txt").write_bytes(b"ccc\n")
    (sub / "d.py").write_bytes(b"print(1)\n")


def run_gnu(cwd: Path, argv: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        [GNU_FIND, *argv],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


CASES: list[tuple[str, list[str]]] = [
    ("顶层无 .txt 时 -name *.txt", ["probe/tree", "-name", "*.txt"]),
    ("顶层无 .txt 时 -name *.md", ["probe/tree", "-name", "*.md"]),
    ("顶层无 .txt 时 -name .*txt", ["probe/tree", "-name", ".*txt"]),
    ("顶层无 .txt 时 -name *", ["probe/tree", "-name", "*"]),
    ("顶层无 .txt 时 -name ?hidden", ["probe/tree", "-name", "?hidden"]),
    ("顶层无 .txt 时 -name a.txt", ["probe/tree", "-name", "a.txt"]),
    ("顶层无 .txt 时 -iname *.TXT", ["probe/tree", "-iname", "*.TXT"]),
    ("顶层无 .txt 时 -path */sub/*", ["probe/tree", "-path", "*/sub/*"]),
    ("顶层无 .txt 时 -path *", ["probe/tree", "-path", "*"]),
    ("顶层无 .txt 时 -regex .*\\.txt", ["probe/tree", "-regex", ".*\\.txt"]),
    ("顶层无 .txt 时 -exec echo {} ;", ["probe/tree", "-exec", "echo", "{}", ";"]),
    ("顶层无 .txt 时 -mmin 0", ["probe/tree", "-mmin", "0"]),
    ("顶层无 .txt 时 -mmin 1", ["probe/tree", "-mmin", "1"]),
    ("顶层无 .txt 时 -mtime 0", ["probe/tree", "-mtime", "0"]),
    ("顶层无 .txt 时 -empty", ["probe/tree", "-empty"]),
    ("顶层无 .txt 时 -size 0", ["probe/tree", "-size", "0"]),
    ("顶层无 .txt 时 -size 1", ["probe/tree", "-size", "1"]),
    ("顶层无 .txt 时 -printf %p", ["probe/tree", "-name", "*.txt", "-printf", "%p\\n"]),
    ("顶层无 .txt 时 -print0", ["probe/tree", "-name", "*.txt", "-print0"]),
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    probe = OUT_DIR / "probe"
    if probe.exists():
        shutil.rmtree(probe)
    probe.mkdir(parents=True)
    build_tree(probe / "tree")
    # 保证顶层没有任何 .txt / .md 文件
    for item in OUT_DIR.iterdir():
        if item.is_file() and item.suffix in (".txt", ".md"):
            item.unlink()

    lines: list[str] = []
    lines.append("--- 顶层目录内容（确认无 .txt/.md）---")
    for item in sorted(OUT_DIR.iterdir()):
        lines.append(f"  {item.name}")
    for title, argv in CASES:
        code, out, err = run_gnu(OUT_DIR, argv)
        lines.append("=" * 70)
        lines.append(f"### {title}")
        lines.append(f"$ find {' '.join(argv)}")
        lines.append(f"exit={code}")
        lines.append("--- stdout ---")
        lines.append(out.replace("\0", "<NUL>") if out else "(空)")
        lines.append("--- stderr ---")
        lines.append(err.replace("\0", "<NUL>") if err else "(空)")

    (OUT_DIR / "probe3.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"probe3 写入 {OUT_DIR / 'probe3.txt'}")


if __name__ == "__main__":
    main()
