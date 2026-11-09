"""探针 2：摸清 GNU find 4.10 的行为，作为 find 指令实现的语义基线。

修正探针 1 的目录名错误（用的 tree 而不是 root），并补上：
- FNM_PERIOD（隐藏文件是否被 * 匹配）
- 遍历顺序（是否排序）
- 隐式 -print 的绑定范围
结果写到 _data_find/probe2.txt。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "_data_find"
GNU_FIND = shutil.which("find") or r"E:\software\Git\Git\usr\bin\find.exe"


def build_tree(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.txt").write_bytes(b"hello\n")
    (root / "b.log").write_bytes(b"")
    (root / ".hidden").write_bytes(b"x\n")
    (root / ".x.txt").write_bytes(b"hidden txt\n")
    (root / "B.txt").write_bytes(b"upper\n")
    (root / "c.md").write_bytes(b"# c\n")
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
    # 造一个修改时间不同的文件，供 -newer / -mtime 用
    old = root / "old.txt"
    old.write_bytes(b"old\n")
    past = time.time() - 40 * 24 * 3600
    os.utime(old, (past, past))
    old2 = root / "old2.txt"
    old2.write_bytes(b"old2\n")
    past2 = time.time() - 3 * 24 * 3600
    os.utime(old2, (past2, past2))


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
    ("默认输出 tree", ["tree"]),
    ("默认输出 tree/ 带斜杠", ["tree/"]),
    ("-name *.txt", ["tree", "-name", "*.txt"]),
    ("-name *（隐藏文件是否命中）", ["tree", "-name", "*"]),
    ("-name .*", ["tree", "-name", ".*"]),
    ("-name .*txt", ["tree", "-name", ".*txt"]),
    ("-iname *.TXT", ["tree", "-iname", "*.TXT"]),
    ("-path *sub*", ["tree", "-path", "*sub*"]),
    ("-path ./*", ["tree", "-path", "./*"]),
    ("-path tree/*", ["tree", "-path", "tree/*"]),
    ("-path *hiddendir*", ["tree", "-path", "*hiddendir*"]),
    ("-type d", ["tree", "-type", "d"]),
    ("-type f", ["tree", "-type", "f"]),
    ("-type l", ["tree", "-type", "l"]),
    ("-type 非法", ["tree", "-type", "x"]),
    ("-size 0", ["tree", "-size", "0"]),
    ("-size 1", ["tree", "-size", "1"]),
    ("-size +0", ["tree", "-size", "+0"]),
    ("-size 1c", ["tree", "-size", "1c"]),
    ("-size 6c", ["tree", "-size", "6c"]),
    ("-size +5c", ["tree", "-size", "+5c"]),
    ("-size 100b", ["tree", "-size", "100b"]),
    ("-maxdepth 1", ["tree", "-maxdepth", "1"]),
    ("-mindepth 1", ["tree", "-mindepth", "1"]),
    ("-maxdepth 2", ["tree", "-maxdepth", "2"]),
    ("-maxdepth 写在路径后", ["tree", "-maxdepth", "2"]),
    ("-maxdepth 0", ["tree", "-maxdepth", "0"]),
    ("-mindepth 2", ["tree", "-mindepth", "2"]),
    ("或关系（隐式 print 绑定）", ["tree", "-name", "*.txt", "-o", "-name", "*.md"]),
    ("或关系 + 显式括号", ["tree", "(", "-name", "*.txt", "-o", "-name", "*.md", ")"]),
    ("括号 + 显式 print", ["tree", "(", "-name", "*.txt", "-o", "-name", "*.md", ")", "-print"]),
    ("显式 -print", ["tree", "-name", "*.txt", "-print"]),
    ("-print 与 or 混排", ["tree", "-name", "*.md", "-print", "-o", "-name", "*.txt", "-print"]),
    ("-mtime 0", ["tree", "-mtime", "0"]),
    ("-mtime +0", ["tree", "-mtime", "+0"]),
    ("-mtime 3", ["tree", "-mtime", "3"]),
    ("-mmin 0", ["tree", "-mmin", "0"]),
    ("-empty", ["tree", "-empty"]),
    ("-exec echo {} ;", ["tree", "-exec", "echo", "{}", ";"]),
    ("-exec echo {} +", ["tree", "-exec", "echo", "{}", "+"]),
    ("-exec 多个参数", ["tree", "-name", "*.txt", "-exec", "echo", "X", "{}", ";"]),
    ("不存在路径", ["nope"]),
    ("-name 缺参数", ["tree", "-name"]),
    ("未知谓词", ["tree", "-badpred"]),
    ("-true", ["tree", "-true"]),
    ("-false", ["tree", "-false"]),
    ("-regex", ["tree", "-regex", ".*\\.txt"]),
    ("-regex 不带 .*", ["tree", "-regex", ".*\\.txt$"]),
    ("-prune", ["tree", "-type", "d", "-prune"]),
    ("-prune + -o -print", ["tree", "-type", "d", "-prune", "-o", "-print"]),
    ("-newer", ["tree", "-newer", "tree/a.txt"]),
    ("-print0", ["tree", "-name", "*.txt", "-print0"]),
    ("-printf %p", ["tree", "-name", "*.txt", "-printf", "%p\n"]),
    ("无路径默认", ["-name", "*.txt"]),
    ("多路径", ["tree", "tree/sub"]),
    ("多路径 + 表达式", ["tree", "tree/sub", "-name", "*.txt"]),
    ("路径给绝对路径", ["-name", "*.txt"]),
    ("-not", ["tree", "-not", "-name", "*.txt"]),
    ("-and", ["tree", "-name", "*.txt", "-and", "-name", "c*"]),
    ("-or", ["tree", "-name", "*.md", "-or", "-name", "*.py"]),
    ("! 紧跟 -o", ["tree", "-name", "*.txt", "-o", "!", "-name", "c.txt"]),
    ("多余右括号", ["tree", ")"]),
    ("左括号未闭合", ["tree", "(", "-name", "*.txt"]),
    ("路径在表达式之后", ["tree", "-name", "*.txt", "tree"]),
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

    (OUT_DIR / "probe2.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"probe2 写入 {OUT_DIR / 'probe2.txt'}")


if __name__ == "__main__":
    main()
