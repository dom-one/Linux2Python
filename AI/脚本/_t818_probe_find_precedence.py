"""钉死 GNU find 的 -a / -o 优先级（是不是同优先级、从左往右）。

为什么必须单独测：本实现把 -a 的优先级放在 -o 之上（POSIX 风格），
而 GNU findutils 的手册说两者**同优先级、从左往右**。两者在
「A -o B -a C」这种写法上会分叉：

- 同优先级左结合：((A -o B) -a C)   → A 为真时 C 仍会被算
- POSIX 优先级：    A -o (B -a C)   → A 为真时 C 被短路掉

判据：用 -printf 当可观测动作，左半边恒真时看右半边有没有被执行。

★ 全部经 bash 拉起 GNU find（Windows 原生程序直接 spawn MSYS 程序时，
   MSYS 运行时会先改掉 argv 里的 {}，量到的不是 GNU 的行为）。

用法: python AI/脚本/_t818_probe_find_precedence.py
产出: AI/数据/find_fix/precedence.txt
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
    # A 恒真（动作），看 B、C 有没有被算
    ("同优先级左结合-预期LR S", ["-printf", "L\\n", "-o", "-name", "*.txt", "-a", "-printf", "S\\n"]),
    # 括号版：明确写出 POSIX 优先级的结果
    ("括号-A或(B且C)", ["(", "-printf", "L\\n", "-o", "(", "-name", "*.txt", "-a", "-printf", "S\\n", ")", ")"]),
    # 反过来：左半边恒假，看右半边
    ("左假-预期右侧执行", ["-name", "*.nomatch", "-o", "-name", "*.txt", "-a", "-printf", "S\\n"]),
    # 纯 -a 链的结合性
    ("a链-三段", ["-name", "*.txt", "-a", "-name", "a*", "-a", "-printf", "S\\n"]),
    # -exec + 里 {} 的位置：GNU 允许 {} 单独成参数出现在中间吗
    ("exec-plus-中间位置", ["-exec", "/usr/bin/printf", "[%s]\\n", "X", "{}", "Y", "+"]),
    ("exec-plus-末尾位置", ["-exec", "/usr/bin/printf", "[%s]\\n", "X", "Y", "{}", "+"]),
]


def build_fixture(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.txt").write_bytes(b"alpha\n")
    (root / "b.md").write_bytes(b"# b\n")


def main() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    tree = BASE / "tree5"
    if tree.exists():
        shutil.rmtree(tree, ignore_errors=True)
    build_fixture(tree)
    run_dir = BASE / "run5"
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True)

    for old in BASE.glob("prec_*"):
        old.unlink()

    lines: list[str] = [
        "# 由 _t818_probe_find_precedence.py 生成，勿手改",
        "set -u",
        f"cd '{run_dir.as_posix()}'",
        f"TREE='{tree.as_posix()}'",
    ]
    for index, (_title, extra) in enumerate(CASES):
        quoted = " ".join("'" + part.replace("'", "'\\''") + "'" for part in extra)
        lines.append(
            f"/usr/bin/find \"$TREE\" {quoted} "
            f"> '{BASE.as_posix()}/prec_{index:02d}.out' "
            f"2> '{BASE.as_posix()}/prec_{index:02d}.err'; "
            f"echo $? > '{BASE.as_posix()}/prec_{index:02d}.code'"
        )
    script = BASE / "precedence.sh"
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")

    bash = shutil.which("bash") or r"E:\software\Git\Git\bin\bash.exe"
    proc = subprocess.run([bash, str(script)], capture_output=True)
    if proc.returncode != 0:
        print("bash 探针执行失败：")
        print(proc.stderr.decode("utf-8", "replace"))
        return 1

    report: list[str] = []
    for index, (title, extra) in enumerate(CASES):
        out = (BASE / f"prec_{index:02d}.out").read_bytes()
        err = (BASE / f"prec_{index:02d}.err").read_bytes()
        code = (BASE / f"prec_{index:02d}.code").read_text(encoding="utf-8").strip()
        report.append("=" * 72)
        report.append(f"### {title}")
        report.append(f"$ find {' '.join(extra)}")
        report.append(f"exit={code}")
        report.append(f"stdout: {out.decode('utf-8', 'replace')!r}")
        report.append(f"stderr: {err.decode('utf-8', 'replace')!r}")

    (BASE / "precedence.txt").write_text("\n".join(report), encoding="utf-8")
    print(f"用例 {len(CASES)} 条")
    print(f"优先级 -> {BASE / 'precedence.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
