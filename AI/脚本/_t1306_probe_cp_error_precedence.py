"""探针：确认 cp 的几个「用法错误」之间的先后次序。

要回答：这些冲突/缺参的检查，谁先谁后？

1. `-S .bak -n`（--backup 与 --no-clobber 互斥）撞上「缺少操作数」时先报哪个
2. `-S .bak -n` 撞上「目标不是目录」时先报哪个
3. `-T --parents` 撞上「缺少操作数」时先报哪个（上一支探针已见：先报缺少操作数）
4. `-T --parents` 的报错文案到底是「目标必须是目录」还是别的
5. 多个源 + 目标不存在 + 目标带尾斜杠时，报的又是哪一条

判据是 GNU 自己先报哪一条，不靠推测。

用法:
    python AI/脚本/_t1306_probe_cp_error_precedence.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "cp_defect_probe"

GNU_CP = shutil.which("cp")


def build_fixture(root: Path) -> None:
    (root / "a.txt").write_bytes(b"hello cp\r\n")
    (root / "plain.txt").write_bytes(b"plain\r\n")
    dest = root / "destdir"
    dest.mkdir()


CASES: list[tuple[str, list[str]]] = [
    ("S-n-no-operand", ["-S", ".bak", "-n"]),
    ("S-n-one-operand", ["-S", ".bak", "-n", "a.txt"]),
    ("S-n-multi-bad-target", ["-S", ".bak", "-n", "a.txt", "plain.txt", "nosuch"]),
    ("S-n-normal", ["-S", ".bak", "-n", "a.txt", "b.txt"]),
    ("T-parents-no-operand", ["-T", "--parents"]),
    ("T-parents-one-operand", ["-T", "--parents", "a.txt"]),
    ("T-parents-normal", ["-T", "--parents", "a.txt", "destdir"]),
    ("parents-no-operand", ["--parents"]),
    ("multi-slash-missing", ["a.txt", "plain.txt", "nosuch/"]),
    ("multi-slash-existing-file", ["a.txt", "plain.txt", "plain.txt/"]),
    ("preserve-bogus-plus-operands", ["--preserve=bogus", "a.txt", "b.txt"]),
    ("no-preserve-bogus-plus-operands", ["--no-preserve=bogus", "a.txt", "b.txt"]),
]


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    sandbox = Path(tempfile.mkdtemp(prefix="cpprec_", dir=str(DATA)))

    lines: list[str] = []
    for index, (name, argv) in enumerate(CASES):
        work = sandbox / f"case{index:03d}"
        work.mkdir()
        build_fixture(work)
        proc = subprocess.run(
            [GNU_CP, *argv],
            cwd=str(work),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        err = proc.stderr.decode("utf-8", "replace").strip()
        first = err.splitlines()[0] if err else ""
        print(f"[{name:30}] rc={proc.returncode}")
        print(f"    首行: {first}")
        lines.append(f"### {name}  argv={' '.join(argv)}\n  rc  = {proc.returncode}\n  err = {err!r}")

    out_path = DATA / "gnu_error_precedence.txt"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n基准已写入: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
