"""钉死剩下三组 GNU find 语义（本轮修复的依据）：

1. `-exec ... +` 的占位符规则
   - `{}` 必须单独成一个参数（嵌入式报 "must appear by itself"）
   - 只能有一个 `{}`（两个报 "Only one instance of {}"）
   - `{}` 必须在最后（不在最后报 "missing argument to `-exec'"）——这��条待确认
   - 没有 `{}` 时 GNU 报错（"missing argument to `-exec'"）
2. `-a` 链里左边是动作时，右半边还评不评
   - `-print` / `-printf` / `-exec` / `-delete` 分别是什么行为
   （GNU 手册说「动作会截断与运算」，实测 `-printf L -a -printf R` 两个都出，
     所以要按实测来，不能按手册措辞来）
3. `-prune` 在 `-a` 链里的位置

★ 全部经 bash 拉起 GNU find（Windows 原生程序直接 spawn MSYS 程序时，
   MSYS 运行时会先改掉 argv 里的 {}，量到的不是 GNU 的行为）。

用法: python AI/脚本/_t819_probe_find_exec_semantics.py
产出: AI/数据/find_fix/exec_semantics.txt
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

PRINTF = "/usr/bin/printf"

CASES: list[tuple[str, list[str]]] = [
    # --- 1. -exec ... + 的占位符规则 ---
    ("plus-单独", ["-exec", PRINTF, "[%s]\\n", "{}", "+"]),
    ("plus-前面有别的参数", ["-exec", PRINTF, "[%s]\\n", "X", "{}", "+"]),
    ("plus-中间", ["-exec", PRINTF, "[%s]\\n", "X", "{}", "Y", "+"]),
    ("plus-开头", ["-exec", PRINTF, "[%s]\\n", "{}", "Y", "+"]),
    ("plus-两个占位符", ["-exec", PRINTF, "[%s]\\n", "{}", "{}", "+"]),
    ("plus-嵌入式", ["-exec", PRINTF, "[%s]\\n", "A{}B", "+"]),
    ("plus-没有占位符", ["-exec", PRINTF, "[%s]\\n", "NOPLACE", "+"]),
    # --- 2. -a 链里左边是动作 ---
    ("and-printf-printf", ["-printf", "L\\n", "-a", "-printf", "R\\n"]),
    ("and-print-print", ["-print", "-a", "-print"]),
    ("and-exec-printf", ["-exec", PRINTF, "X\\n", ";", "-a", "-printf", "Y\\n"]),
    ("and-printf-exec", ["-printf", "L\\n", "-a", "-exec", PRINTF, "R\\n", ";"]),
    ("and-exec-exec", ["-exec", PRINTF, "L\\n", ";", "-a", "-exec", PRINTF, "R\\n", ";"]),
    # --- 3. -o 链里左边是动作 ---
    ("or-printf-printf", ["-printf", "L\\n", "-o", "-printf", "R\\n"]),
    ("or-exec-printf", ["-exec", PRINTF, "L\\n", ";", "-o", "-printf", "R\\n"]),
    ("or-printf-exec", ["-printf", "L\\n", "-o", "-exec", PRINTF, "R\\n", ";"]),
    # --- 4. -prune 在链里的位置 ---
    ("prune-and-print", ["-type", "d", "-prune", "-a", "-print"]),
    ("prune-o-print", ["-type", "d", "-prune", "-o", "-print"]),
    ("prune-alone", ["-type", "d", "-prune"]),
    ("prune-and-name", ["-type", "d", "-prune", "-a", "-name", "*.txt"]),
]


def build_fixture(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.txt").write_bytes(b"alpha\n")
    (root / "b.md").write_bytes(b"# b\n")


def main() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    tree = BASE / "tree6"
    if tree.exists():
        shutil.rmtree(tree, ignore_errors=True)
    build_fixture(tree)
    run_dir = BASE / "run6"
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True)

    for old in BASE.glob("execsem_*"):
        old.unlink()

    lines: list[str] = [
        "# 由 _t819_probe_find_exec_semantics.py 生成，勿手改",
        "set -u",
        f"cd '{run_dir.as_posix()}'",
        f"TREE='{tree.as_posix()}'",
    ]
    for index, (_title, extra) in enumerate(CASES):
        quoted = " ".join("'" + part.replace("'", "'\\''") + "'" for part in extra)
        lines.append(
            f"/usr/bin/find \"$TREE\" {quoted} "
            f"> '{BASE.as_posix()}/execsem_{index:02d}.out' "
            f"2> '{BASE.as_posix()}/execsem_{index:02d}.err'; "
            f"echo $? > '{BASE.as_posix()}/execsem_{index:02d}.code'"
        )
    script = BASE / "exec_semantics.sh"
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")

    bash = shutil.which("bash") or r"E:\software\Git\Git\bin\bash.exe"
    proc = subprocess.run([bash, str(script)], capture_output=True)
    if proc.returncode != 0:
        print("bash 探针执行失败：")
        print(proc.stderr.decode("utf-8", "replace"))
        return 1

    report: list[str] = []
    for index, (title, extra) in enumerate(CASES):
        out = (BASE / f"execsem_{index:02d}.out").read_bytes()
        err = (BASE / f"execsem_{index:02d}.err").read_bytes()
        code = (BASE / f"execsem_{index:02d}.code").read_text(encoding="utf-8").strip()
        report.append("=" * 72)
        report.append(f"### {title}")
        report.append(f"$ find {' '.join(extra)}")
        report.append(f"exit={code}")
        report.append(f"stdout: {out.decode('utf-8', 'replace')!r}")
        report.append(f"stderr: {err.decode('utf-8', 'replace')!r}")

    (BASE / "exec_semantics.txt").write_text("\n".join(report), encoding="utf-8")
    print(f"用例 {len(CASES)} 条")
    print(f"exec 语义 -> {BASE / 'exec_semantics.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
