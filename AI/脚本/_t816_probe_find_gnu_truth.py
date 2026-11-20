"""查清 GNU find 的 {} 展开与 -a/-o 求值规则（真基线）。

★ 方法论陷阱（这轮踩到的最重要的一处）
基线探针 _t814 是用 **Python 的 subprocess** 直接拉起 MSYS 的 find.exe，
结果嵌入式占位符全被吃掉：`-exec echo A{}B` 输出 `AB`（花括号没了、路径也没进去）。
但同一台机器上用 bash 直接跑：

    find ../tree2 -name '*.txt' -exec printf '[%s]\\n' 'A{}B' ';'
    → [A../tree2/a.txtB]

即 GNU find 是**就地替换** `{}`，前面的 A 后面的 B 都该保留。
差异出在「Windows 原生程序（Python）拉起 MSYS 程序」这条路径上：
MSYS 运行时会对来自原生父进程的 argv 做通配符/花括号展开（项目老笔记里记过
「MSYS2 的 find.exe 会在进程启动时对参数做通配符展开」，同一个机制的另一面），
`{}` 在到达 find 之前就已经被改掉了。

⇒ 差分对照**必须经 bash 拉起 GNU find**，否则量到的是 MSYS 运行时的行为，
不是 GNU find 的行为。本脚本就是把 GNU 那一侧改成 bash 驱动，并逐案落盘
（bash 工具的输出会把连续空格吃掉，结果必须写进文件再读）。

用法: python AI/脚本/_t816_probe_find_gnu_truth.py
产出: AI/数据/find_fix/gnucase_*.out / .err、gnucases.txt、gnu_truth.txt
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

# (标题, 表达式参数列表)
CASES: list[tuple[str, list[str]]] = [
    # --- {} 的展开方式 ---
    ("brace-单独占位符-分号", ["-exec", "printf", "[%s]\\n", "{}", ";"]),
    ("brace-嵌入式-前后缀-A路径B", ["-exec", "printf", "[%s]\\n", "A{}B", ";"]),
    ("brace-嵌入式-两处", ["-exec", "printf", "[%s]\\n", "{}A{}", ";"]),
    ("brace-嵌入式-加号", ["-exec", "printf", "[%s]\\n", "A{}B", "+"]),
    ("brace-无占位符-分号", ["-exec", "printf", "[%s]\\n", "NOPLACE", ";"]),
    ("brace-无占位符-加号", ["-exec", "printf", "[%s]\\n", "NOPLACE", "+"]),
    ("brace-单独占位符-加号", ["-exec", "printf", "[%s]\\n", "{}", "+"]),
    ("brace-两处占位符-分号", ["-exec", "printf", "[%s]\\n", "X", "{}", "Y", "{}", ";"]),
    ("brace-两处占位符-加号", ["-exec", "printf", "[%s]\\n", "X", "{}", "Y", "{}", "+"]),
    ("brace-占位符加前后缀-加号", ["-exec", "printf", "[%s]\\n", "X{}Y", "+"]),
    # --- -a / -o 的求值顺序（用 -printf 当可观测动作）---
    ("eval-a-左动作右动作", ["-printf", "L\\n", "-a", "-printf", "R\\n"]),
    ("eval-o-左动作右动作", ["-printf", "L\\n", "-o", "-printf", "R\\n"]),
    ("eval-o-左动作右动作右动作", ["-printf", "L\\n", "-o", "-printf", "R\\n", "-o", "-printf", "S\\n"]),
    ("eval-o-左测试右动作", ["-name", "*.txt", "-o", "-printf", "R\\n"]),
    ("eval-o-左动作右测试", ["-printf", "L\\n", "-o", "-name", "*.txt"]),
    ("eval-a-左动作右测试", ["-printf", "L\\n", "-a", "-name", "*.txt"]),
    ("eval-o-动作链", ["-name", "*.txt", "-print", "-o", "-name", "*.md", "-print"]),
    ("eval-o-两个裸动作", ["-print", "-o", "-print"]),
    ("eval-o-prune-or-print", ["-type", "d", "-prune", "-o", "-print"]),
    ("eval-o-prune-or-name", ["-type", "d", "-prune", "-o", "-name", "*.txt"]),
]


def build_fixture(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.txt").write_bytes(b"alpha\n")
    (root / "b.md").write_bytes(b"# b\n")


def main() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    tree = BASE / "tree3"
    if tree.exists():
        shutil.rmtree(tree, ignore_errors=True)
    build_fixture(tree)
    run_dir = BASE / "run3"
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True)

    # 清掉上一轮的旧结果
    for old in BASE.glob("gnucase_*"):
        old.unlink()

    # 生成 bash 脚本：GNU 那一侧全部经 bash 拉起，避开 MSYS 对 argv 的改写
    lines: list[str] = [
        "# 由 _t816_probe_find_gnu_truth.py 生成，勿手改",
        "set -u",
        f"cd '{run_dir.as_posix()}'",
        f"TREE='{tree.as_posix()}'",
    ]
    for index, (_title, extra) in enumerate(CASES):
        quoted = " ".join("'" + part.replace("'", "'\\''") + "'" for part in extra)
        lines.append(
            f"/usr/bin/find \"$TREE\" {quoted} "
            f"> '{BASE.as_posix()}/gnucase_{index:02d}.out' "
            f"2> '{BASE.as_posix()}/gnucase_{index:02d}.err'; "
            f"echo $? > '{BASE.as_posix()}/gnucase_{index:02d}.code'"
        )
    script = BASE / "gnu_probe.sh"
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")

    bash = shutil.which("bash") or r"E:\software\Git\Git\bin\bash.exe"
    proc = subprocess.run([bash, str(script)], capture_output=True)
    if proc.returncode != 0:
        print("bash 探针执行失败：")
        print(proc.stderr.decode("utf-8", "replace"))
        return 1

    report: list[str] = []
    for index, (title, extra) in enumerate(CASES):
        out_path = BASE / f"gnucase_{index:02d}.out"
        err_path = BASE / f"gnucase_{index:02d}.err"
        code_path = BASE / f"gnucase_{index:02d}.code"
        out = out_path.read_bytes() if out_path.exists() else b""
        err = err_path.read_bytes() if err_path.exists() else b""
        code = code_path.read_text(encoding="utf-8").strip() if code_path.exists() else "?"
        report.append("=" * 72)
        report.append(f"### {title}")
        report.append(f"$ find {' '.join(extra)}")
        report.append(f"exit={code}")
        report.append(f"stdout: {out.decode('utf-8', 'replace')!r}")
        report.append(f"stderr: {err.decode('utf-8', 'replace')!r}")

    (BASE / "gnu_truth.txt").write_text("\n".join(report), encoding="utf-8")
    (BASE / "gnucases.txt").write_text(
        "\n".join(f"{i:02d}\t{title}" for i, (title, _) in enumerate(CASES)),
        encoding="utf-8",
    )
    print(f"用例 {len(CASES)} 条")
    print(f"真基线 -> {BASE / 'gnu_truth.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
