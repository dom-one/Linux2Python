"""探针：确认 GNU 的 --preserve 重复给出时属性是「并集」还是「最后一个覆盖」。

GNU coreutils 的 cp.c 里 --preserve 是往同一组标志位上 OR，
所以「mode 再 timestamps」应当两样都保住（时间戳被保住）；
若实现按「最后一个覆盖」，时间戳就保不住。

顺带确认 --preserve 裸写（等价 --preserve=all）是否真的保住时间戳，
以及 --backup 与 --no-clobber 的冲突是不是在动文件之前就报。

用法:
    python AI/脚本/_t1305_probe_cp_preserve_union.py
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
STAMP = 1_000_000_000


def build_fixture(root: Path) -> None:
    src = root / "a.txt"
    src.write_bytes(b"hello cp\r\n")
    os.utime(src, (STAMP, STAMP))
    (root / "b.txt").write_bytes(b"old content\r\n")


def run(argv: list[str], cwd: Path) -> dict:
    proc = subprocess.run(
        [GNU_CP, *argv],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "rc": proc.returncode,
        "out": proc.stdout.decode("utf-8", "replace"),
        "err": proc.stderr.decode("utf-8", "replace"),
    }


CASES: list[tuple[str, list[str]]] = [
    ("preserve-bare", ["--preserve", "a.txt", "copy.txt"]),
    ("preserve-mode-only", ["--preserve=mode", "a.txt", "copy.txt"]),
    ("preserve-timestamps-only", ["--preserve=timestamps", "a.txt", "copy.txt"]),
    ("preserve-mode-then-timestamps", ["--preserve=mode", "--preserve=timestamps", "a.txt", "copy.txt"]),
    ("preserve-timestamps-then-mode", ["--preserve=timestamps", "--preserve=mode", "a.txt", "copy.txt"]),
    ("preserve-all", ["--preserve=all", "a.txt", "copy.txt"]),
    ("preserve-all-then-mode", ["--preserve=all", "--preserve=mode", "a.txt", "copy.txt"]),
    ("preserve-mode-then-no-preserve-timestamps", ["--preserve=mode", "--no-preserve=timestamps", "a.txt", "copy.txt"]),
    # 冲突判定发生在动文件之前吗
    ("S-and-n-new-target", ["-S", ".bak", "-n", "a.txt", "copy.txt"]),
    ("T-and-parents-missing-operand", ["-T", "--parents"]),
]


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    sandbox = Path(tempfile.mkdtemp(prefix="cppreserve_", dir=str(DATA)))

    lines: list[str] = []
    for index, (name, argv) in enumerate(CASES):
        work = sandbox / f"case{index:03d}"
        work.mkdir()
        build_fixture(work)
        result = run(argv, work)
        copy_path = work / "copy.txt"
        if copy_path.exists():
            stamp = int(copy_path.stat().st_mtime)
            verdict = "保住了时间戳" if stamp == STAMP else f"时间戳变了({stamp})"
        else:
            verdict = "没有落地 copy.txt"
        print(f"[{name:36}] rc={result['rc']} {verdict}")
        if result["err"].strip():
            print(f"    err={result['err'].strip()[:120]!r}")
        lines.append(
            f"### {name}  argv={' '.join(argv)}\n"
            f"  rc  = {result['rc']}\n"
            f"  err = {result['err']!r}\n"
            f"  判定 = {verdict}"
        )

    out_path = DATA / "gnu_preserve_union.txt"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n基准已写入: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
