"""查清 GNU find 的 {} 展开到底是怎么做的（探针）。

基线探针 _t814 观察到几个反直觉的结果，必须先分清「GNU find 的语义」与「MSYS 运行时的副作用」：

- `-exec echo A{}B ;` 在 GNU 那边输出的是 `AB`（花括号没了、路径也没进去）
- `-exec echo {}X{} ;` 输出 `X`
- `-exec echo A{}B +` 报 "missing argument to `-exec'"
- `-exec echo NOPLACEHOLDER +` 也报 "missing argument to `-exec'"
- `-exec echo X {} Y {} +` 报 "Only one instance of {} is supported with -exec ... +"

「花括号被吃掉」这件事有两种可能：
① GNU find 只认「整个参数就是 {}」这种占位符，A{}B 是原样传的（那 echo 应该打印 A{}B）；
② GNU find 认嵌入式 {} 但替换成了空串；
③ 是 MSYS 运行时在动手脚（它会对参数做路径改写）。

办法：让子进程把收到的 argv 原样打出来。两个子进程各测一遍：
- `printf '[%s]\\n'` 是 MSYS 自带的（/usr/bin/printf.exe）
- `python -c ...` 是 Windows 原生程序（sys.executable），MSYS 运行时改写路径时最容易被看破

另外用 -printf 观测 `-a` / `-o` 的求值顺序：
- `-printf 'L\n' -a -printf 'R\n'`：GNU 左边是动作且为真，右半边还评不评？
- `-printf 'L\n' -o -printf 'R\n'`：GNU 左边是动作且为真，右半边还评不评？

用法: python AI/脚本/_t815_probe_find_exec_argv.py
产出: AI/数据/find_fix/exec_argv.txt、eval_order.txt
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
ROOT = AI_DIR.parent
BASE = AI_DIR / "数据" / "find_fix"
GNU_FIND = shutil.which("find") or r"E:\software\Git\Git\usr\bin\find.exe"

PY_DUMP = "import sys;[print(repr(a)) for a in sys.argv[1:]]"


def build_fixture(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.txt").write_bytes(b"alpha\n")
    (root / "b.md").write_bytes(b"# b\n")


def run_gnu(cwd: Path, argv: list[str]) -> tuple[int, bytes, bytes]:
    proc = subprocess.run([GNU_FIND, *argv], cwd=str(cwd), capture_output=True)
    return proc.returncode, proc.stdout, proc.stderr


def section(lines: list[str], title: str, code: int, out: bytes, err: bytes) -> None:
    lines.append("=" * 72)
    lines.append(f"### {title}")
    lines.append(f"exit={code}")
    lines.append(f"stdout: {out.decode('utf-8', 'replace')!r}")
    lines.append(f"stderr: {err.decode('utf-8', 'replace')!r}")


def main() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    tree = BASE / "tree2"
    if tree.exists():
        shutil.rmtree(tree, ignore_errors=True)
    build_fixture(tree)
    empty_cwd = BASE / "run2"
    empty_cwd.mkdir(exist_ok=True)
    tree_abs = tree.as_posix()
    py = sys.executable

    argv_lines: list[str] = []

    # 1. MSYS 的 printf 看 GNU 到底传了什么
    for title, extra in [
        ("printf 单独 {}", ["-exec", "printf", "[%s]\n", "{}", ";"]),
        ("printf 嵌入式 A{}B", ["-exec", "printf", "[%s]\n", "A{}B", ";"]),
        ("printf 嵌入式 {}X{}", ["-exec", "printf", "[%s]\n", "{}X{}", ";"]),
        ("printf 两处 {} {}", ["-exec", "printf", "[%s]\n", "{}", "{}", ";"]),
        ("printf 前缀 后缀 X{}Y", ["-exec", "printf", "[%s]\n", "X{}Y", ";"]),
    ]:
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-name", "*.txt", *extra])
        section(argv_lines, title, code, out, err)

    # 2. Windows 原生 python 看同一个问题（绕开 MSYS 的 printf）
    for title, extra in [
        ("py 单独 {}", ["-exec", py, "-c", PY_DUMP, "{}", ";"]),
        ("py 嵌入式 A{}B", ["-exec", py, "-c", PY_DUMP, "A{}B", ";"]),
        ("py 嵌入式 {}X{}", ["-exec", py, "-c", PY_DUMP, "{}X{}", ";"]),
        ("py 两处 {} {}", ["-exec", py, "-c", PY_DUMP, "{}", "{}", ";"]),
    ]:
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-name", "*.txt", *extra])
        section(argv_lines, title, code, out, err)

    # 3. 单独确认 MSYS 的 printf 本身会不会吃掉花括号
    proc = subprocess.run(["printf", "[%s]\n", "A{}B"], capture_output=True)
    argv_lines.append("=" * 72)
    argv_lines.append("### 直接跑 printf（不经 find）")
    argv_lines.append(f"stdout: {proc.stdout!r}")

    (BASE / "exec_argv.txt").write_text("\n".join(argv_lines), encoding="utf-8")

    # 4. 用 -printf 观测 -a / -o 的求值顺序
    eval_lines: list[str] = []
    for title, extra in [
        ("a: 左动作右动作", ["-printf", "L\\n", "-a", "-printf", "R\\n"]),
        ("o: 左动作右动作", ["-printf", "L\\n", "-o", "-printf", "R\\n"]),
        ("a: 左测试右动作", ["-name", "*.txt", "-a", "-printf", "R\\n"]),
        ("o: 左测试右动作", ["-name", "*.txt", "-o", "-printf", "R\\n"]),
        ("o: 左动作右测试", ["-printf", "L\\n", "-o", "-name", "*.txt"]),
        ("o: 左动作右动作右动作", ["-printf", "L\\n", "-o", "-printf", "R\\n", "-o", "-printf", "S\\n"]),
    ]:
        code, out, err = run_gnu(empty_cwd, [tree_abs, *extra])
        section(eval_lines, title, code, out, err)

    (BASE / "eval_order.txt").write_text("\n".join(eval_lines), encoding="utf-8")
    print(f"argv 探针 -> {BASE / 'exec_argv.txt'}")
    print(f"求值顺序探针 -> {BASE / 'eval_order.txt'}")


if __name__ == "__main__":
    main()
