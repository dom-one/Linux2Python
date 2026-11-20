"""钉死 GNU find 的 -a / -o 优先级与「动作是否截断运算链」。

上一轮探针（_t817/_t819）已经给出一个反直觉的结果：`-printf L -a -printf R`
两个都出（说明 -a 链里左半边是动作时右半边**仍然**被算），
而 `-printf L -o -name *.txt -a -printf S` 只出 L（说明 -o 一旦为真就整条短路）。

这两条合起来只对应一种模型：**-a 的优先级高于 -o**，且 -a/-o 都是普通的
布尔短路（动作恒为真）。但这个结论跟「GNU 的 -a/-o 同优先级左结合」的说法冲突，
必须再用一个**不含动作**的判据把两种模型分开：

模型 P（-a 更紧）：  A -o (B -a C)
模型 Q（同优先级左结合）：(A -o B) -a C

用例 `-name '*.md' -o -name '*.txt' -a -name 'a*'`：
- 模型 P：b.md 走左边（-name '*.md' 为真 → -o 短路）⇒ 命中 b.md；
          a.txt 走右边（-name '*.txt' 为真 且 -name 'a*' 为真）⇒ 命中 a.txt
          ⇒ 命中 {a.txt, b.md}
- 模型 Q：(name.md -o name.txt) 为真，再 -a name.a*
          ⇒ b.md 虽然过了前半段，但后半段 -name 'a*' 不匹配 ⇒ 只有 a.txt

两种模型给出的命中集合不同，用它就能定案。

★ 全部经 bash 拉起 GNU find（Windows 原生程序直接 spawn MSYS 程序时，
   MSYS 运行时会先改掉 argv 里的 {}，量到的不是 GNU 的行为）。

用法: python AI/脚本/_t820_probe_find_precedence.py
产出: AI/数据/find_fix/precedence2.txt
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
    # 判据用例：模型 P 命中 {a.txt, b.md}，模型 Q 只命中 {a.txt}
    ("判据-md或(txt且a开头)", ["-name", "*.md", "-o", "-name", "*.txt", "-a", "-name", "a*"]),
    # 反向判据
    ("判据-txt或(md且b开头)", ["-name", "*.txt", "-o", "-name", "*.md", "-a", "-name", "b*"]),
    # 三段链
    ("三段-txt或md或py", ["-name", "*.txt", "-o", "-name", "*.md", "-o", "-name", "*.py"]),
    ("三段-and混排", ["-name", "*.txt", "-o", "-name", "*.md", "-a", "-name", "a*"]),
]


def build_fixture(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.txt").write_bytes(b"alpha\n")
    (root / "b.md").write_bytes(b"# b\n")


def main() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    tree = BASE / "tree7"
    if tree.exists():
        shutil.rmtree(tree, ignore_errors=True)
    build_fixture(tree)
    run_dir = BASE / "run7"
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True)

    for old in BASE.glob("prec2_*"):
        old.unlink()

    lines: list[str] = [
        "# 由 _t820_probe_find_precedence.py 生成，勿手改",
        "set -u",
        f"cd '{run_dir.as_posix()}'",
        f"TREE='{tree.as_posix()}'",
    ]
    for index, (_title, extra) in enumerate(CASES):
        quoted = " ".join("'" + part.replace("'", "'\\''") + "'" for part in extra)
        lines.append(
            f"/usr/bin/find \"$TREE\" {quoted} "
            f"> '{BASE.as_posix()}/prec2_{index:02d}.out' "
            f"2> '{BASE.as_posix()}/prec2_{index:02d}.err'; "
            f"echo $? > '{BASE.as_posix()}/prec2_{index:02d}.code'"
        )
    script = BASE / "precedence2.sh"
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")

    bash = shutil.which("bash") or r"E:\software\Git\Git\bin\bash.exe"
    proc = subprocess.run([bash, str(script)], capture_output=True)
    if proc.returncode != 0:
        print("bash 探针执行失败：")
        print(proc.stderr.decode("utf-8", "replace"))
        return 1

    report: list[str] = []
    for index, (title, extra) in enumerate(CASES):
        out = (BASE / f"prec2_{index:02d}.out").read_bytes()
        err = (BASE / f"prec2_{index:02d}.err").read_bytes()
        code = (BASE / f"prec2_{index:02d}.code").read_text(encoding="utf-8").strip()
        report.append("=" * 72)
        report.append(f"### {title}")
        report.append(f"$ find {' '.join(extra)}")
        report.append(f"exit={code}")
        report.append(f"stdout: {out.decode('utf-8', 'replace')!r}")
        report.append(f"stderr: {err.decode('utf-8', 'replace')!r}")

    (BASE / "precedence2.txt").write_text("\n".join(report), encoding="utf-8")
    print(f"用例 {len(CASES)} 条")
    print(f"优先级判据 -> {BASE / 'precedence2.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
