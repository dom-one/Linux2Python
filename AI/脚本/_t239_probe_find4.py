"""探针 4：干净基线。

关键：MSYS2 的 find.exe 会在进程启动时对参数做通配符展开（相对于进程 cwd）。
所以差分对照必须把 cwd 设成一个**空目录**，任何模式都不会被展开，find 拿到的就是字面量。

本探针还测：
- FNM_PERIOD：-name '*' 会不会匹配隐藏文件
- -mmin 的年龄口径（与 Python 算出的真实年龄对照）
- 遍历顺序是否与 Python os.scandir 一致
结果写到 _data_find4/probe4.txt。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "_data_find4"
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
    empty = root / "empty"
    empty.mkdir(exist_ok=True)


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


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    tree = OUT_DIR / "tree"
    build_tree(tree)
    empty_cwd = OUT_DIR / "run"
    empty_cwd.mkdir()

    # 用正斜杠的绝对路径，MSYS 的 find 会原样打印
    tree_abs = tree.as_posix()

    lines: list[str] = []
    lines.append(f"tree = {tree_abs}")
    lines.append(f"cwd = {empty_cwd.as_posix()}（空目录，模式不会被展开）")
    lines.append("")

    # ---- 遍历顺序对照 ----
    code, out, err = run_gnu(empty_cwd, [tree_abs])
    lines.append("### GNU find 遍历顺序")
    lines.append(out.rstrip("\n") if out else "(空)")
    lines.append("--- Python os.scandir 顺序 ---")
    lines.append(tree_abs)
    for item in os.scandir(tree):
        lines.append(f"{tree_abs}/{item.name}")
        if item.is_dir():
            for sub in os.scandir(item.path):
                lines.append(f"{item.path}/{sub.name}")
                if sub.is_dir():
                    for deep in os.scandir(sub.path):
                        lines.append(f"{sub.path}/{deep.name}")
    lines.append("")

    # ---- FNM_PERIOD ----
    for pattern in ("*", ".*", "*.txt", "?.txt", "h*"):
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-name", pattern])
        lines.append(f"### -name '{pattern}'  exit={code}")
        lines.append(out.rstrip("\n") if out else "(空)")
        if err:
            lines.append("STDERR: " + err.rstrip("\n"))
        lines.append("")

    # ---- -path ----
    for pattern in ("*", "*/sub/*", "*sub*", "*/empty"):
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-path", pattern])
        lines.append(f"### -path '{pattern}'  exit={code}")
        lines.append(out.rstrip("\n") if out else "(空)")
        if err:
            lines.append("STDERR: " + err.rstrip("\n"))
        lines.append("")

    # ---- -mmin 口径 ----
    now = time.time()
    code, out, err = run_gnu(empty_cwd, [tree_abs, "-mmin", "0"])
    lines.append(f"### -mmin 0  exit={code}")
    lines.append(out.rstrip("\n") if out else "(空)")
    code, out, err = run_gnu(empty_cwd, [tree_abs, "-mmin", "1"])
    lines.append(f"### -mmin 1  exit={code}")
    lines.append(out.rstrip("\n") if out else "(空)")
    lines.append("--- Python 算出的年龄（秒）---")
    for dirpath, dirnames, filenames in os.walk(tree):
        for name in [dirpath] + [os.path.join(dirpath, f) for f in filenames]:
            st = os.stat(name)
            lines.append(f"  age={now - st.st_mtime:8.2f}s  {name}")
    lines.append("")

    # ---- 其它谓词 ----
    other = [
        (["-type", "d"], "目录"),
        (["-type", "f"], "普通文件"),
        (["-type", "l"], "符号链接"),
        (["-size", "0"], "size 0"),
        (["-size", "1"], "size 1"),
        (["-size", "+0"], "size +0"),
        (["-size", "1c"], "size 1c"),
        (["-size", "+5c"], "size +5c"),
        (["-empty"], "empty"),
        (["-maxdepth", "1"], "maxdepth 1"),
        (["-mindepth", "1"], "mindepth 1"),
        (["-maxdepth", "2"], "maxdepth 2"),
        (["-mtime", "0"], "mtime 0"),
        (["-true"], "true"),
        (["-false"], "false"),
        (["-print0"], "print0"),
        (["-printf", "%p\\n"], "printf %p"),
        (["-exec", "echo", "{}", ";"], "exec ;"),
        (["-exec", "echo", "{}", "+"], "exec +"),
        (["-type", "d", "-prune"], "prune"),
        (["-type", "d", "-prune", "-o", "-print"], "prune -o print"),
        (["-regex", ".*\\.txt"], "regex"),
        (["-iname", "*.TXT"], "iname"),
        (["-name", "*.txt", "-o", "-name", "*.md"], "or 关系"),
        (["(", "-name", "*.txt", "-o", "-name", "*.md", ")"], "括号"),
        (["!", "-name", "*.txt"], "取反"),
        (["-name", "*.txt", "-print", "-o", "-name", "*.md", "-print"], "print 与 or 混排"),
    ]
    for extra, title in other:
        code, out, err = run_gnu(empty_cwd, [tree_abs, *extra])
        lines.append(f"### {title}: find {' '.join(extra)}  exit={code}")
        lines.append(out.replace("\0", "<NUL>").rstrip("\n") if out else "(空)")
        if err:
            lines.append("STDERR: " + err.rstrip("\n"))
        lines.append("")

    (OUT_DIR / "probe4.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"probe4 写入 {OUT_DIR / 'probe4.txt'}")


if __name__ == "__main__":
    main()
