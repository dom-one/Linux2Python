"""探针：摸清 GNU find 4.10 的行为，作为 find 指令实现的语义基线。

结果写到 _data_find/probe1.txt，避免 bash 工具的输出把空格吃掉。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "_data_find"
GNU_FIND = shutil.which("find") or r"E:\software\Git\Git\usr\bin\find.exe"


def build_tree(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.txt").write_bytes(b"hello\n")
    (root / "b.log").write_bytes(b"")
    (root / ".hidden").write_bytes(b"x\n")
    hid = root / ".hiddendir"
    hid.mkdir(exist_ok=True)
    (hid / "c.txt").write_bytes(b"deep\n")
    sub = root / "sub"
    sub.mkdir(exist_ok=True)
    (sub / "c.txt").write_bytes(b"ccc\n")
    (sub / "d.py").write_bytes(b"print(1)\n")
    nested = sub / "nested"
    nested.mkdir(exist_ok=True)
    (nested / "e.md").write_bytes(b"# t\n")
    link = root / "link.txt"
    if link.exists() or link.is_symlink():
        link.unlink()
    try:
        os.symlink(root / "a.txt", link)
    except OSError as exc:
        print(f"[symlink 创建失败: {exc}]", file=sys.stderr)


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
    ("默认输出 .", ["."]),
    ("默认输出 root", ["root"]),
    ("默认输出 root/ 带斜杠", ["root/"]),
    ("-name *.txt", ["root", "-name", "*.txt"]),
    ("-name *（是否含隐藏）", ["root", "-name", "*"]),
    ("-name .*", ["root", "-name", ".*"]),
    ("-path *sub*", ["root", "-path", "*sub*"]),
    ("-path ./*", ["root", "-path", "./*"]),
    ("-type d", ["root", "-type", "d"]),
    ("-type f", ["root", "-type", "f"]),
    ("-type l", ["root", "-type", "l"]),
    ("-type 非法", ["root", "-type", "x"]),
    ("-size 0", ["root", "-size", "0"]),
    ("-size 1", ["root", "-size", "1"]),
    ("-size +0", ["root", "-size", "+0"]),
    ("-size 1c", ["root", "-size", "1c"]),
    ("-size 6c", ["root", "-size", "6c"]),
    ("-size +5c", ["root", "-size", "+5c"]),
    ("-maxdepth 1", ["root", "-maxdepth", "1"]),
    ("-mindepth 1", ["root", "-mindepth", "1"]),
    ("-maxdepth 2", ["root", "-maxdepth", "2"]),
    ("-maxdepth 写在路径后", ["root", "-maxdepth", "2"]),
    ("-name 或关系", ["root", "-name", "*.txt", "-o", "-name", "*.md"]),
    ("! 取反", ["root", "!", "-name", "*.txt"]),
    ("括号分组", ["root", "(", "-name", "*.txt", "-o", "-name", "*.md", ")"]),
    ("括号分组 + -print", ["root", "(", "-name", "*.txt", "-o", "-name", "*.md", ")", "-print"]),
    ("显式 -print", ["root", "-name", "*.txt", "-print"]),
    ("-mtime 0", ["root", "-mtime", "0"]),
    ("-mtime +0", ["root", "-mtime", "+0"]),
    ("-mmin 0", ["root", "-mmin", "0"]),
    ("-empty", ["root", "-empty"]),
    ("-exec echo {} ;", ["root", "-exec", "echo", "{}", ";"]),
    ("-exec echo {} +", ["root", "-exec", "echo", "{}", "+"]),
    ("不存在路径", ["nope"]),
    ("-name 缺参数", ["root", "-name"]),
    ("未知谓词", ["root", "-badpred"]),
    ("-true", ["root", "-true"]),
    ("-false", ["root", "-false"]),
    ("-iname", ["root", "-iname", "*.TXT"]),
    ("-regex", ["root", "-regex", ".*\\.txt"]),
    ("-prune", ["root", "-type", "d", "-prune"]),
    ("-prune + -o", ["root", "-type", "d", "-prune", "-o", "-print"]),
    ("-delete 的匹配范围", ["root", "-name", "*.log", "-newer", "root/a.txt"]),
    ("-newer", ["root", "-newer", "root/a.txt"]),
    ("-print0", ["root", "-name", "*.txt", "-print0"]),
    ("-printf %p", ["root", "-name", "*.txt", "-printf", "%p\n"]),
    ("无路径默认", ["-name", "*.txt"]),
    ("-maxdepth 0", ["root", "-maxdepth", "0"]),
    ("多路径", ["root", "root/sub"]),
    ("-path 绝对路径风格", ["root", "-path", "root/*"]),
    ("-name 大写", ["root", "-name", "A.TXT"]),
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tree = OUT_DIR / "tree"
    if tree.exists():
        shutil.rmtree(tree)
    build_tree(tree)

    lines: list[str] = []
    for title, argv in CASES:
        cwd = OUT_DIR
        code, out, err = run_gnu(cwd, argv)
        lines.append("=" * 70)
        lines.append(f"### {title}")
        lines.append(f"$ find {' '.join(argv)}")
        lines.append(f"exit={code}")
        lines.append("--- stdout ---")
        lines.append(out.replace("\0", "<NUL>") if out else "(空)")
        lines.append("--- stderr ---")
        lines.append(err.replace("\0", "<NUL>") if err else "(空)")

    (OUT_DIR / "probe1.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"probe1 写入 {OUT_DIR / 'probe1.txt'}")


if __name__ == "__main__":
    main()
