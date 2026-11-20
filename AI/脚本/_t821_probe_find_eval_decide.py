"""决定性复测：GNU find 4.10 的 -a / -o 求值到底是不是「普通布尔短路」。

★ 为什么必须再测一次
上一轮两个探针对**同一条命令**给出了互相矛盾的结论：
  - AI/数据/find_fix/eval_table.txt 的「测试-o-动作」(`-name *.txt -o -printf R\\n`) 报 1 个 R
  - AI/数据/find_fix/gnu_truth.txt 的「eval-o-左测试右动作」（同一条命令）报 2 个 R
两者必有一个是错的。GNU 的求值模型直接决定 _And/_Or 怎么改，不能靠猜。

★ 观测手段
用 `-printf` 带 %p（带路径的标记），这样每条输出都能对上是哪个条目打的，
不再靠「数个数」猜。只数个数分不清「哪个条目被打印」。

★ 两种模型，本轮要分出胜负
  模型 A（普通布尔短路）：-a 左假才跳右；-o 左真才跳右
  模型 B（动作截断）：动作恒为真，-a 的左半边是动作就不算右半边
两条命令专门区分这两个模型：
  - `-printf L\\n -a -printf R\\n`：模型 A 出 L R，模型 B 只出 L
  - `-printf L\\n -o -printf R\\n`：模型 A 只出 L（-o 左真短路），模型 B 出 L R
  - `-print -o -print`：模型 A 每条一遍，模型 B 每条两遍
  - `-print -a -print`：模型 A 每条两遍，模型 B 每条一遍
再带 -prune 测「动作 + 副作用」的情况。

★ GNU 那一侧必须经 bash 拉起
Python 的 subprocess 直接 spawn MSYS 的 find.exe 时，MSYS 运行时会在 argv 到达
find 之前改写它（`{}` 被吃掉）。详见 _t816_probe_find_gnu_truth.py 的说明。

用法: python AI/脚本/_t821_probe_find_eval_decide.py
产出: AI/数据/find_fix/eval_decide.txt
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
BASE = AI_DIR / "数据" / "find_fix"
ROOT = AI_DIR.parent

# (标题, 表达式参数)
CASES: list[tuple[str, list[str]]] = [
    # --- 区分模型 A（普通布尔短路）与模型 B（动作截断）---
    ("A1-动作a动作", ["-printf", "L\\n", "-a", "-printf", "R\\n"]),
    ("A2-动作o动作", ["-printf", "L\\n", "-o", "-printf", "R\\n"]),
    ("A3-printoprint", ["-print", "-o", "-print"]),
    ("A4-printaprint", ["-print", "-a", "-print"]),
    # --- 带 %p 的同款，定位是哪个条目被打印 ---
    ("B1-测试o动作", ["-name", "*.txt", "-o", "-printf", "R:%p\\n"]),
    ("B2-测试a动作", ["-name", "*.txt", "-a", "-printf", "R:%p\\n"]),
    ("B3-测试o测试", ["-name", "*.txt", "-o", "-name", "*.md", "-printf", "P:%p\\n"]),
    ("B4-动作o测试", ["-printf", "L:%p\\n", "-o", "-name", "*.txt"]),
    ("B5-动作a测试", ["-printf", "L:%p\\n", "-a", "-name", "*.txt"]),
    # --- -prune 与短路的相互作用 ---
    ("C1-pruneoprint", ["-type", "d", "-prune", "-o", "-print"]),
    ("C2-pruneoprint-p", ["-type", "d", "-prune", "-o", "-printf", "P:%p\\n"]),
    ("C3-pruneandprint", ["-type", "d", "-prune", "-a", "-printf", "P:%p\\n"]),
    ("C4-pruneonly", ["-type", "d", "-prune"]),
    ("C5-prune-o-name", ["-type", "d", "-prune", "-o", "-name", "*.txt"]),
    # --- 隐式 -print 与短路的相互作用 ---
    ("D1-测试o测试-无动作", ["-name", "*.txt", "-o", "-name", "*.md"]),
    ("D2-测试o动作-无动作", ["-name", "*.txt", "-o", "-name", "*.zzz"]),
]


def build_fixture(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.txt").write_bytes(b"alpha\n")
    (root / "b.md").write_bytes(b"# b\n")
    sub = root / "sub"
    sub.mkdir(exist_ok=True)
    (sub / "c.txt").write_bytes(b"gamma\n")


def run_gnu(tree: Path, extra: list[str]) -> tuple[int, str, str]:
    """经 bash 拉起 GNU find，cwd 放在夹具里、操作数用 .，输出是相对路径。"""
    quoted = " ".join("'" + part.replace("'", "'\\''") + "'" for part in extra)
    script = BASE / "_t821_gnu_case.sh"
    script.write_text(
        "cd '" + tree.as_posix() + "'\n"
        "/usr/bin/find . " + quoted + " 2> '" + (BASE / "_t821_case.err").as_posix() + "'\n",
        encoding="utf-8",
    )
    bash = shutil.which("bash") or r"E:\software\Git\Git\bin\bash.exe"
    proc = subprocess.run([bash, str(script)], capture_output=True)
    err_path = BASE / "_t821_case.err"
    err = err_path.read_bytes().decode("utf-8", "replace") if err_path.exists() else ""
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), err


def run_mine(tree: Path, extra: list[str]) -> tuple[int, str, str]:
    """跑本项目的 find（原生 Python，不经 MSYS）。"""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "find", ".", *extra],
        cwd=tree,
        capture_output=True,
    )
    out = proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n")
    err = proc.stderr.decode("utf-8", "replace").replace("\r\n", "\n")
    return proc.returncode, out, err


def main() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    tree = BASE / "tree8"
    if tree.exists():
        shutil.rmtree(tree, ignore_errors=True)
    build_fixture(tree)

    report: list[str] = [
        "# 由 _t821_probe_find_eval_decide.py 生成，勿手改",
        f"# 夹具: {tree.as_posix()}（a.txt / b.md / sub/c.txt）",
        "",
    ]
    mismatch = 0
    for title, extra in CASES:
        g_code, g_out, g_err = run_gnu(tree, extra)
        m_code, m_out, m_err = run_mine(tree, extra)
        same = g_out == m_out
        if not same:
            mismatch += 1
        report.append("=" * 72)
        report.append(f"### {title}")
        report.append(f"$ find . {' '.join(extra)}")
        report.append(f"GNU   exit={g_code} stdout={g_out!r}")
        report.append(f"本项目 exit={m_code} stdout={m_out!r}")
        report.append(f"一致: {same}")
        if g_err.strip():
            report.append(f"GNU   stderr={g_err!r}")
        if m_err.strip():
            report.append(f"本项目 stderr={m_err!r}")

    report.append("=" * 72)
    report.append(f"用例 {len(CASES)} 条，输出不一致 {mismatch} 条")
    (BASE / "eval_decide.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"用例 {len(CASES)} 条，输出不一致 {mismatch} 条")
    print(f"结果 -> {BASE / 'eval_decide.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
