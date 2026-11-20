"""钉死 GNU find 的 -a / -o 求值真值表（这是本轮修复的核心依据）。

背景：教程任务查出本实现 find.py 的 _Or 少了短路分支，`-print -o -print` 会把每条打印两遍
而 GNU 只一遍。但 _And 里还有一条「左半边是动作就短路」的规则，
它到底在 GNU 里成不成立，必须单独钉死——不然改了 _Or 反而把 _And 弄错。

观测手段：用 -printf 当「有输出的动作」，每个条目会打印出标记，
据此看出左右两半各自有没有被执行、执行的顺序。

要钉死的组合：
  动作 -a 动作      → 右半边还评不评？
  动作 -o 动作      → 右半边还评不评？
  动作 -a 测试
  动作 -o 测试
  测试 -o 动作
  动作 -o 动作 -o 动作
  -print -o -print  （两个都是真动作，最容易暴露差异）
  -print -a -print

★ 全部经 bash 拉起 GNU find：Windows 原生程序直接 spawn MSYS 程序时，
MSYS 运行时会在 argv 到达 find 之前就把 {} 改掉（详见 _t816 的说明），
那样量到的是运行时的行为、不是 GNU find 的行为。

用法: python AI/脚本/_t817_probe_find_eval_table.py
产出: AI/数据/find_fix/eval_table.txt
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

CASES: list[tuple[str, list[str]]] = [
    ("动作-a-动作", ["-printf", "L\\n", "-a", "-printf", "R\\n"]),
    ("动作-o-动作", ["-printf", "L\\n", "-o", "-printf", "R\\n"]),
    ("动作-a-测试", ["-printf", "L\\n", "-a", "-name", "*.txt"]),
    ("动作-o-测试", ["-printf", "L\\n", "-o", "-name", "*.txt"]),
    ("测试-o-动作", ["-name", "*.txt", "-o", "-printf", "R\\n"]),
    ("动作-o-动作-o-动作", ["-printf", "L\\n", "-o", "-printf", "R\\n", "-o", "-printf", "S\\n"]),
    ("动作-a-动作-a-动作", ["-printf", "L\\n", "-a", "-printf", "R\\n", "-a", "-printf", "S\\n"]),
    ("print-o-print", ["-print", "-o", "-print"]),
    ("print-a-print", ["-print", "-a", "-print"]),
    ("测试-a-动作", ["-name", "*.txt", "-a", "-printf", "R\\n"]),
    ("测试-a-动作-a-动作", ["-name", "*.txt", "-a", "-printf", "R\\n", "-a", "-printf", "S\\n"]),
    ("测试-o-测试", ["-name", "*.txt", "-o", "-name", "*.md"]),
    ("动作-o-测试-o-动作", ["-printf", "L\\n", "-o", "-name", "*.txt", "-o", "-printf", "S\\n"]),
]


def build_fixture(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.txt").write_bytes(b"alpha\n")
    (root / "b.md").write_bytes(b"# b\n")


def main() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    tree = BASE / "tree4"
    if tree.exists():
        shutil.rmtree(tree, ignore_errors=True)
    build_fixture(tree)
    run_dir = BASE / "run4"
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True)

    for old in BASE.glob("evaltable_*"):
        old.unlink()

    lines: list[str] = [
        "# 由 _t817_probe_find_eval_table.py 生成，勿手改",
        "set -u",
        f"cd '{run_dir.as_posix()}'",
        f"TREE='{tree.as_posix()}'",
    ]
    for index, (_title, extra) in enumerate(CASES):
        quoted = " ".join("'" + part.replace("'", "'\\''") + "'" for part in extra)
        lines.append(
            f"/usr/bin/find \"$TREE\" {quoted} "
            f"> '{BASE.as_posix()}/evaltable_{index:02d}.out' "
            f"2> '{BASE.as_posix()}/evaltable_{index:02d}.err'; "
            f"echo $? > '{BASE.as_posix()}/evaltable_{index:02d}.code'"
        )
    script = BASE / "eval_table.sh"
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")

    bash = shutil.which("bash") or r"E:\software\Git\Git\bin\bash.exe"
    proc = subprocess.run([bash, str(script)], capture_output=True)
    if proc.returncode != 0:
        print("bash 探针执行失败：")
        print(proc.stderr.decode("utf-8", "replace"))
        return 1

    report: list[str] = []
    for index, (title, extra) in enumerate(CASES):
        out = (BASE / f"evaltable_{index:02d}.out").read_bytes()
        err = (BASE / f"evaltable_{index:02d}.err").read_bytes()
        code = (BASE / f"evaltable_{index:02d}.code").read_text(encoding="utf-8").strip()
        report.append("=" * 72)
        report.append(f"### {title}")
        report.append(f"$ find {' '.join(extra)}")
        report.append(f"exit={code}")
        report.append(f"stdout: {out.decode('utf-8', 'replace')!r}")
        report.append(f"stderr: {err.decode('utf-8', 'replace')!r}")

    (BASE / "eval_table.txt").write_text("\n".join(report), encoding="utf-8")
    print(f"用例 {len(CASES)} 条")
    print(f"真值表 -> {BASE / 'eval_table.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
