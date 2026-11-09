"""find 指令的差分对照脚本：拿本实现与 GNU find 4.10 逐条比对。

关键：MSYS2 的 find.exe 会在进程启动时对参数做通配符展开（相对进程 cwd）。
所以两边都在**空目录**下运行，模式不会被展开，GNU find 拿到的就是字面量。

比对内容：标准输出逐字节 + 退出码。
结果写到 _data_find_diff/diff.txt。
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
OUT_DIR = HERE / "_data_find_diff"
GNU_FIND = shutil.which("find") or r"E:\software\Git\Git\usr\bin\find.exe"

sys.path.insert(0, str(HERE.parents[1]))
from w2l.commands.find import build_parser, find  # noqa: E402
from w2l.context import RunContext  # noqa: E402


def build_tree(root: Path) -> dict[str, float]:
    """造一棵测试树，并给出关键文件的年龄（秒）。"""
    now = time.time()
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.txt").write_bytes(b"hello\n")
    (root / "B.txt").write_bytes(b"upper\n")
    (root / "c.md").write_bytes(b"# c\n")
    (root / "empty.log").write_bytes(b"")
    (root / ".hidden").write_bytes(b"x\n")
    (root / ".x.txt").write_bytes(b"hidden txt\n")
    sub = root / "sub"
    sub.mkdir(exist_ok=True)
    (sub / "c.txt").write_bytes(b"ccc\n")
    (sub / "d.py").write_bytes(b"print(1)\n")
    nested = sub / "nested"
    nested.mkdir(exist_ok=True)
    (nested / "e.md").write_bytes(b"# t\n")
    (nested / "big.bin").write_bytes(b"z" * 3000)
    hollow = root / "hollow"
    hollow.mkdir(exist_ok=True)

    ages: dict[str, float] = {}
    for name, age in (("old.txt", 90000), ("mid.txt", 3600), ("recent.txt", 90)):
        path = root / name
        path.write_bytes(b"x\n")
        stamp = now - age
        os.utime(path, (stamp, stamp))
        ages[name] = age
    return ages


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


def run_mine(cwd: Path, argv: list[str]) -> tuple[int, str, str]:
    """跑本实现的 find。

    必须以子进程方式跑：-exec 起的子命令直接继承进程的标准输出，
    在进程内调用处理器的话，那部分输出不会进 ctx.stdout，比对就缺了。
    """
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "find", *argv],
        cwd=str(cwd),
        capture_output=True,
    )
    out = proc.stdout.decode("utf-8", "replace")
    err = proc.stderr.decode("utf-8", "replace")
    # Windows 的 cmd 输出 CRLF，MSYS 的 echo 输出 LF，比对前统一成 LF
    return proc.returncode, out.replace("\r\n", "\n"), err.replace("\r\n", "\n")


CASES: list[tuple[str, list[str]]] = [
    ("无表达式", []),
    ("-name *.txt", ["-name", "*.txt"]),
    ("-name *.TXT（大小写敏感）", ["-name", "*.TXT"]),
    ("-iname *.txt", ["-iname", "*.txt"]),
    ("-name *（含隐藏文件）", ["-name", "*"]),
    ("-type f", ["-type", "f"]),
    ("-type d", ["-type", "d"]),
    ("-type l", ["-type", "l"]),
    ("-size 0", ["-size", "0"]),
    ("-size 1", ["-size", "1"]),
    ("-size +0", ["-size", "+0"]),
    ("-size 1c", ["-size", "1c"]),
    ("-size +5c", ["-size", "+5c"]),
    ("-size 3k", ["-size", "3k"]),
    ("-size +2k", ["-size", "+2k"]),
    ("-empty", ["-empty"]),
    ("-maxdepth 1", ["-maxdepth", "1"]),
    ("-maxdepth 2", ["-maxdepth", "2"]),
    ("-maxdepth 0", ["-maxdepth", "0"]),
    ("-mindepth 1", ["-mindepth", "1"]),
    ("-mindepth 2", ["-mindepth", "2"]),
    ("-mtime 0", ["-mtime", "0"]),
    ("-mtime +0", ["-mtime", "+0"]),
    ("-mtime 1", ["-mtime", "1"]),
    ("-mmin 0", ["-mmin", "0"]),
    ("-mmin 1", ["-mmin", "1"]),
    ("-mmin 2", ["-mmin", "2"]),
    ("-mmin +1", ["-mmin", "+1"]),
    ("-mmin -1", ["-mmin", "-1"]),
    ("-or 关系", ["-name", "*.txt", "-o", "-name", "*.md"]),
    ("括号分组", ["(", "-name", "*.txt", "-o", "-name", "*.md", ")"]),
    ("括号分组 + -print", ["(", "-name", "*.txt", "-o", "-name", "*.md", ")", "-print"]),
    ("取反 !", ["!", "-name", "*.txt"]),
    ("取反 -not", ["-not", "-name", "*.txt"]),
    ("-print 与 or 混排", ["-name", "*.txt", "-print", "-o", "-name", "*.md", "-print"]),
    ("-true", ["-true"]),
    ("-false", ["-false"]),
    ("-prune", ["-type", "d", "-prune"]),
    ("-prune -o -print", ["-type", "d", "-prune", "-o", "-print"]),
    ("-path */sub/*", ["-path", "*/sub/*"]),
    ("-path *sub*", ["-path", "*sub*"]),
    ("-regex", ["-regex", ".*\\.txt"]),
    ("-print0", ["-print0"]),
    ("-printf %p", ["-printf", "%p\\n"]),
    ("-printf %f %s %y", ["-printf", "%f %s %y\\n"]),
    ("-exec echo {} ;", ["-exec", "echo", "{}", ";"]),
    ("-exec echo {} +", ["-exec", "echo", "{}", "+"]),
    ("-exec 多参数", ["-name", "*.txt", "-exec", "echo", "X", "{}", ";"]),
    ("-a 显式", ["-name", "*.txt", "-a", "-type", "f"]),
    ("-and 显式", ["-name", "*.txt", "-and", "-size", "+0"]),
    ("-o 与 ! 组合", ["-name", "*.txt", "-o", "!", "-name", "*.md"]),
    ("-newer", ["-newer", "TREE/a.txt"]),
    ("-depth", ["-depth"]),
    ("-depth + -type d", ["-depth", "-type", "d"]),
]


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    tree = OUT_DIR / "tree"
    build_tree(tree)
    empty_cwd = OUT_DIR / "run"
    empty_cwd.mkdir()
    tree_abs = tree.as_posix()

    lines: list[str] = []
    passed = failed = 0
    failures: list[str] = []

    for title, extra in CASES:
        argv = [tree_abs, *[part.replace("TREE", tree_abs) for part in extra]]
        gnu_code, gnu_out, gnu_err = run_gnu(empty_cwd, argv)
        my_code, my_out, my_err = run_mine(empty_cwd, argv)

        out_same = gnu_out == my_out
        # 退出码口径不同：GNU 无结果也返回 0，本项目返回 1
        code_same = gnu_code == my_code or (gnu_code == 0 and my_code == 1)

        if out_same and code_same:
            passed += 1
            lines.append(f"[一致] {title}")
            continue

        failed += 1
        failures.append(title)
        lines.append("=" * 70)
        lines.append(f"[不一致] {title}")
        lines.append(f"$ find {' '.join(extra)}")
        lines.append(f"GNU  exit={gnu_code}  行数={len(gnu_out.splitlines())}")
        lines.append(f"本实现 exit={my_code}  行数={len(my_out.splitlines())}")
        gnu_lines = gnu_out.splitlines()
        my_lines = my_out.splitlines()
        only_gnu = [line for line in gnu_lines if line not in my_lines]
        only_mine = [line for line in my_lines if line not in gnu_lines]
        lines.append(f"只有 GNU 有的（前 10 行）: {only_gnu[:10]}")
        lines.append(f"只有本实现有的（前 10 行）: {only_mine[:10]}")
        if gnu_out.splitlines() != my_out.splitlines() and not only_gnu and not only_mine:
            lines.append("行集合相同，顺序不同")
            lines.append(f"GNU  前 6 行: {gnu_lines[:6]}")
            lines.append(f"本实现前 6 行: {my_lines[:6]}")
        if my_err:
            lines.append(f"本实现 stderr: {my_err.strip()[:200]}")
        lines.append("")

    lines.insert(0, f"一致 {passed} 条，不一致 {failed} 条")
    lines.insert(1, "")
    (OUT_DIR / "diff.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"一致 {passed} 条，不一致 {failed} 条")
    if failures:
        print("不一致的用例: " + "; ".join(failures))
    print(f"明细写入 {OUT_DIR / 'diff.txt'}")


if __name__ == "__main__":
    main()
