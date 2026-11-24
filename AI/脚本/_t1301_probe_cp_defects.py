"""探针：给 cp 的四处候选缺陷取 GNU cp 8.32 的基准行为。

本轮要修的是教程任务交回来的四处偏差（README 写错了、行为也与 GNU 不一致）：

1. `-n` / `-i` 两个选项同时给时谁赢（项目写的是「-n 压过 -i」，GNU 是后给的那个赢）
2. `--preserve` 裸写时会不会把后面的操作数吃掉（GNU 要求 `--preserve=列表`）
3. 目标尾部带斜杠时，目标不存在会怎样
4. `-T` 与 `--parents` 同时给会怎样

探针只跑 GNU 那一侧，把真实行为记成可核对的文本；
判定「GNU 到底怎么表现」这一步不能靠印象写。

用法:
    python AI/脚本/_t1301_probe_cp_defects.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "cp_defect_probe"

GNU_CP = shutil.which("cp")
if GNU_CP is None:
    raise SystemExit("本机找不到 GNU cp")


def build_fixture(root: Path) -> None:
    (root / "a.txt").write_bytes(b"hello cp\r\nsecond line\r\n")
    (root / "b.txt").write_bytes(b"old content\r\n")
    dest = root / "destdir"
    dest.mkdir()
    (dest / "keep.txt").write_bytes(b"keep\r\n")


def run_gnu(argv: list[str], cwd: Path, stdin_text: str | None) -> dict:
    proc = subprocess.run(
        [GNU_CP, *argv],
        cwd=str(cwd),
        input=stdin_text.encode() if stdin_text is not None else b"",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "rc": proc.returncode,
        "out": proc.stdout.decode("utf-8", "replace"),
        "err": proc.stderr.decode("utf-8", "replace"),
    }


def tree_state(root: Path) -> list[str]:
    entries: list[str] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            entries.append(f"DIR  {rel}")
        else:
            entries.append(f"FILE {rel} {path.read_bytes()!r}")
    return entries


# 名字, argv, stdin
CASES: list[tuple[str, list[str], str | None]] = [
    # 1. -n / -i 同时给：谁赢
    ("n-i-order", ["-n", "-i", "a.txt", "b.txt"], "y\n"),
    ("i-n-order", ["-i", "-n", "a.txt", "b.txt"], "y\n"),
    ("n-only", ["-n", "a.txt", "b.txt"], "y\n"),
    ("i-only", ["-i", "a.txt", "b.txt"], "y\n"),
    ("ni-joined", ["-ni", "a.txt", "b.txt"], "y\n"),
    ("in-joined", ["-in", "a.txt", "b.txt"], "y\n"),
    # 2. --preserve 裸写
    ("preserve-bare", ["--preserve", "a.txt", "copy.txt"], None),
    ("preserve-eq", ["--preserve=mode", "a.txt", "copy.txt"], None),
    ("preserve-eq-all", ["--preserve=all", "a.txt", "copy.txt"], None),
    ("preserve-space-mode", ["--preserve", "mode", "a.txt", "copy.txt"], None),
    ("no-preserve-bare", ["--no-preserve", "a.txt", "copy.txt"], None),
    ("no-preserve-eq", ["--no-preserve=mode", "a.txt", "copy.txt"], None),
    # 3. 目标尾斜杠
    ("dest-trailing-slash-missing", ["a.txt", "nosuch/"], None),
    ("dest-trailing-slash-existing", ["a.txt", "destdir/"], None),
    ("dest-trailing-slash-root", ["-r", "destdir", "nosuch/"], None),
    # 4. -T 与 --parents 同时给
    ("T-and-parents", ["-T", "--parents", "a.txt", "destdir"], None),
    ("parents-and-T", ["--parents", "-T", "a.txt", "destdir"], None),
    ("parents-only", ["--parents", "a.txt", "destdir"], None),
    # 5. -S 与 -n 同时给
    ("S-and-n", ["-S", ".bak", "-n", "a.txt", "b.txt"], None),
    ("n-and-S", ["-n", "-S", ".bak", "a.txt", "b.txt"], None),
    # 6. -u 与 -n 同时给
    ("u-and-n", ["-u", "-n", "a.txt", "b.txt"], None),
    # 7. --backup 与 --no-clobber 的冲突判定与 -i 的先后关系
    ("S-n-i", ["-S", ".bak", "-n", "-i", "a.txt", "b.txt"], "y\n"),
    ("n-i-S", ["-n", "-i", "-S", ".bak", "a.txt", "b.txt"], "y\n"),
    ("i-n-S", ["-i", "-n", "-S", ".bak", "a.txt", "b.txt"], "y\n"),
    ("S-and-i", ["-S", ".bak", "-i", "a.txt", "b.txt"], "y\n"),
    ("preserve-twice", ["--preserve=mode", "--preserve=timestamps", "a.txt", "copy.txt"], None),
    ("preserve-bare-then-eq", ["--preserve", "--preserve=mode", "a.txt", "copy.txt"], None),
    ("preserve-eq-then-bare", ["--preserve=mode", "--preserve", "a.txt", "copy.txt"], None),
]


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    sandbox = Path(tempfile.mkdtemp(prefix="cpdefect_", dir=str(DATA)))

    report: list[dict] = []
    for index, (name, argv, stdin_text) in enumerate(CASES):
        work = sandbox / f"case{index:03d}"
        work.mkdir()
        build_fixture(work)
        # 两个沙箱的 mtime 无关紧要，这里不比时间戳。
        result = run_gnu(argv, work, stdin_text)
        print("=" * 72)
        print(f"[{name}] argv={' '.join(argv)}  stdin={stdin_text!r}")
        print(f"  rc  = {result['rc']}")
        print(f"  out = {result['out']!r}")
        print(f"  err = {result['err']!r}")
        for line in tree_state(work):
            print(f"  tree| {line}")
        report.append(
            {
                "name": name,
                "argv": argv,
                "stdin": stdin_text,
                "rc": result["rc"],
                "out": result["out"],
                "err": result["err"],
                "tree": tree_state(work),
            }
        )

    out_path = DATA / "gnu_baseline.txt"
    lines = []
    for item in report:
        lines.append(f"### {item['name']}  argv={' '.join(item['argv'])}  stdin={item['stdin']!r}")
        lines.append(f"  rc  = {item['rc']}")
        lines.append(f"  out = {item['out']!r}")
        lines.append(f"  err = {item['err']!r}")
        for entry in item["tree"]:
            lines.append(f"  tree| {entry}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("=" * 72)
    print(f"用例 {len(CASES)} 条，基准已写入: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
