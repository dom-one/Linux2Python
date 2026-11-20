"""find 表达式语义的基线探针：把 GNU find 4.10 与本实现在同一组表达式上的输出各存一份。

背景：教程任务（tick #9）在对拍中查出本实现 find 的三处偏差，根因都在「表达式求值」
与「-exec 占位符展开」这一层：

1. _expand_placeholder 把整个参数替换掉了：`-exec echo A{}B` 只输出路径，A 和 B 丢了；
   一个参数里多个 {} 也只替换第一个。
2. _Or.evaluate 少了「左半边是裸动作就短路」这个分支（_And 有、_Or 没有），
   `-print -o -name` 会被命中项打印两遍而 GNU 只一遍。
3. 管道里输出是 CRLF（find.py 没像 cat.py / tail.py 那样调 reconfigure(newline="")），
   多出来的 \\r 会让 grep -x 和 $(...) 比较对不上。

本脚本只做「记录事实」，不做判断：同一组表达式分别喂给 GNU find 与本实现，
原始字节各存一份，后面用 _t815_diff_find_expr.py 做逐字节比对。

注意（老坑）：MSYS2 的 find.exe 会在进程启动时对参数做通配符展开（相对进程 cwd），
所以两边都在**空目录**下运行，模式不会被悄悄换掉。

用法: python AI/脚本/_t814_probe_find_expr_baseline.py
产出: AI/数据/find_fix/gnu.txt、mine.txt、cases.txt
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
ROOT = AI_DIR.parent
BASE = AI_DIR / "数据" / "find_fix"
GNU_FIND = shutil.which("find") or r"E:\software\Git\Git\usr\bin\find.exe"


def build_fixture(root: Path) -> None:
    """造一棵固定的小树。

    目录项的创建顺序决定 readdir 顺序，两边看到的是同一棵���，不用 sort。
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.txt").write_bytes(b"alpha\n")
    (root / "b.txt").write_bytes(b"beta\n")
    (root / "c.md").write_bytes(b"# c\n")
    (root / "d.md").write_bytes(b"# d\n")
    (root / "empty.log").write_bytes(b"")
    sub = root / "sub"
    sub.mkdir(exist_ok=True)
    (sub / "e.txt").write_bytes(b"epsilon\n")
    (sub / "f.md").write_bytes(b"# f\n")
    nested = sub / "nested"
    nested.mkdir(exist_ok=True)
    (nested / "g.txt").write_bytes(b"gamma\n")


# 表达式用例：(标题, 表达式参数列表)
# 覆盖三类问题：_Or 的短路语义、-exec 的 {} 展开、动作与隐式 -print 的关系
CASES: list[tuple[str, list[str]]] = [
    ("基线-无表达式", []),
    ("基线-name", ["-name", "*.txt"]),
    ("Or-裸动作在左-print-or-name", ["-print", "-o", "-name", "*.md"]),
    ("Or-裸动作在左-name-or-print", ["-name", "*.md", "-o", "-print"]),
    ("Or-两个动作-print-or-print", ["-print", "-o", "-print"]),
    ("Or-左动作右动作-print-name-print", ["-name", "*.txt", "-print", "-o", "-name", "*.md", "-print"]),
    ("Or-true-or-false", ["-true", "-o", "-false"]),
    ("Or-false-or-true", ["-false", "-o", "-true"]),
    ("Prune-裸-prune", ["-type", "d", "-prune"]),
    ("Prune-prune-or-print", ["-type", "d", "-prune", "-o", "-print"]),
    ("Prune-prune-or-name", ["-type", "d", "-prune", "-o", "-name", "*.txt"]),
    ("Exec-echo-A{}B-分号", ["-exec", "echo", "A{}B", ";"]),
    ("Exec-echo-A{}B-加号", ["-exec", "echo", "A{}B", "+"]),
    ("Exec-echo-{}X{}-分号", ["-exec", "echo", "{}X{}", ";"]),
    ("Exec-echo-{}X{}-加号", ["-exec", "echo", "{}X{}", "+"]),
    ("Exec-echo-{}A{}-分号", ["-exec", "echo", "{}A{}", ";"]),
    ("Exec-echo-两处-分号", ["-exec", "echo", "X", "{}", "Y", "{}", ";"]),
    ("Exec-echo-两处-加号", ["-exec", "echo", "X", "{}", "Y", "{}", "+"]),
    ("Exec-echo-无占位符-分号", ["-exec", "echo", "NOPLACEHOLDER", ";"]),
    ("Exec-echo-无占位符-加号", ["-exec", "echo", "NOPLACEHOLDER", "+"]),
]


def run_gnu(cwd: Path, argv: list[str]) -> tuple[int, bytes, bytes]:
    proc = subprocess.run(
        [GNU_FIND, *argv],
        cwd=str(cwd),
        capture_output=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_mine(cwd: Path, argv: list[str]) -> tuple[int, bytes, bytes]:
    """跑本实现的 find。

    必须以子进程方式跑：-exec 起的子命令直接继承进程的标准输出，
    在进程内调用处理器的话，那部分输出不会进 ctx.stdout，比对就缺了。
    """
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "find", *argv],
        cwd=str(cwd),
        capture_output=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def dump(lines: list[str], title: str, code: int, out: bytes, err: bytes) -> None:
    lines.append("=" * 72)
    lines.append(f"### {title}")
    lines.append(f"exit={code}")
    lines.append(f"stdout({len(out)} bytes): {out!r}")
    lines.append(f"stderr({len(err)} bytes): {err!r}")


def main() -> None:
    if BASE.exists():
        shutil.rmtree(BASE, ignore_errors=True)
    BASE.mkdir(parents=True)
    tree = BASE / "tree"
    build_fixture(tree)
    empty_cwd = BASE / "run"
    empty_cwd.mkdir()
    tree_abs = tree.as_posix()

    gnu_lines: list[str] = []
    mine_lines: list[str] = []
    case_lines: list[str] = []

    for title, extra in CASES:
        argv = [tree_abs, *extra]
        case_lines.append(f"{title}\tfind {' '.join(extra)}".rstrip())

        g_code, g_out, g_err = run_gnu(empty_cwd, argv)
        dump(gnu_lines, title, g_code, g_out, g_err)

        m_code, m_out, m_err = run_mine(empty_cwd, argv)
        dump(mine_lines, title, m_code, m_out, m_err)

    (BASE / "gnu.txt").write_text("\n".join(gnu_lines), encoding="utf-8")
    (BASE / "mine.txt").write_text("\n".join(mine_lines), encoding="utf-8")
    (BASE / "cases.txt").write_text("\n".join(case_lines), encoding="utf-8")
    print(f"用例 {len(CASES)} 条")
    print(f"GNU  基线 -> {BASE / 'gnu.txt'}")
    print(f"本实现基线 -> {BASE / 'mine.txt'}")


if __name__ == "__main__":
    main()
