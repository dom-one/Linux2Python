"""探针 5：把 -mmin / -mtime 的年龄口径测准。

探针 4 里出现反直觉结果：0.2 秒大的文件不匹配 -mmin 0，却匹配 -mmin 1。
本探针造一批精确年龄的文件（0/10/30/59/60/61/90/119/120/121/300/3600/86400/172800 秒），
跑 -mmin 与 -mtime 的各个 N，看匹配集合反推出公式。

同时对照三方的时钟：
- GNU find 内部算出的年龄（通过匹配结果反推）
- MSYS2 的 stat -c %Y
- Python 的 os.stat().st_mtime 与 time.time()

结果写到 _data_find5/probe5.txt。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "_data_find5"
GNU_FIND = shutil.which("find") or r"E:\software\Git\Git\usr\bin\find.exe"
MSYS_STAT = r"E:\software\Git\Git\usr\bin\stat.exe"
MSYS_DATE = r"E:\software\Git\Git\usr\bin\date.exe"

AGES = [0, 10, 30, 59, 60, 61, 90, 119, 120, 121, 300, 3600, 86400, 172800]


def build_tree(root: Path, now: float) -> dict[str, float]:
    root.mkdir(parents=True, exist_ok=True)
    written: dict[str, float] = {}
    for age in AGES:
        name = f"age{age:>07d}.txt"
        path = root / name
        path.write_bytes(b"x\n")
        stamp = now - age
        os.utime(path, (stamp, stamp))
        written[name] = stamp
    return written


def run_gnu(cwd: Path, argv: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        [GNU_FIND, *argv],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    tree = OUT_DIR / "tree"
    now = time.time()
    stamps = build_tree(tree, now)
    empty_cwd = OUT_DIR / "run"
    empty_cwd.mkdir()
    tree_abs = tree.as_posix()

    lines: list[str] = []
    lines.append("### 时钟对照")
    sample = tree / f"age{0:>07d}.txt"
    stat_out = subprocess.run(
        [MSYS_STAT, "-c", "%Y %y %n", sample.as_posix()],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    date_out = subprocess.run(
        [MSYS_DATE, "+%s"], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    lines.append(f"Python time.time()      = {now:.3f}")
    lines.append(f"Python os.stat mtime    = {os.stat(sample).st_mtime:.3f}")
    lines.append(f"MSYS stat -c %Y         = {stat_out.stdout.strip()}")
    lines.append(f"MSYS date +%s           = {date_out.stdout.strip()}")
    lines.append("")

    lines.append("### -mmin 各 N 的匹配集合")
    for n in [0, 1, 2, 5, 10, 60, 120, 1440, 2880]:
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-mmin", str(n)])
        matched = sorted(
            int(line.rsplit("age", 1)[1].split(".")[0])
            for line in out.splitlines()
            if "age" in line
        )
        lines.append(f"-mmin {n:>5} -> 年龄秒数 {matched}")
    lines.append("")

    lines.append("### -mtime 各 N 的匹配集合")
    for n in [0, 1, 2, 5, 10, 60]:
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-mtime", str(n)])
        matched = sorted(
            int(line.rsplit("age", 1)[1].split(".")[0])
            for line in out.splitlines()
            if "age" in line
        )
        lines.append(f"-mtime {n:>5} -> 年龄秒数 {matched}")
    lines.append("")

    lines.append("### -newer 参照文件（age0000000.txt，mtime=建树时刻）")
    ref = tree / f"age{0:>07d}.txt"
    code, out, err = run_gnu(empty_cwd, [tree_abs, "-newer", ref.as_posix()])
    matched = sorted(
        int(line.rsplit("age", 1)[1].split(".")[0])
        for line in out.splitlines()
        if "age" in line
    )
    lines.append(f"-newer -> 年龄秒数 {matched}")
    lines.append("")

    lines.append("### -size 带 k/M 后缀")
    big = tree / "big.bin"
    big.write_bytes(b"z" * 3000)
    for spec in ["-1", "-6", "+2", "6c", "3000c", "+2999c", "3k", "4k", "+2k"]:
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-size", spec, "-name", "big.bin"])
        lines.append(f"-size {spec:>8} -> {'命中' if out.strip() else '不命中'}")
    lines.append("")

    lines.append("### -type 各种取值")
    for t in ["f", "d", "l", "b", "c", "p", "s"]:
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-type", t])
        lines.append(f"-type {t} -> 命中 {len(out.splitlines())} 个")
    lines.append("")

    lines.append("### 错误信息")
    for argv in (
        [tree_abs, "-name"],
        [tree_abs, "-badpred"],
        [tree_abs, "-type", "x"],
        [tree_abs, "-size", "abc"],
        [tree_abs, "-size"],
        [tree_abs, "-maxdepth", "x"],
        [tree_abs, "-maxdepth"],
        [tree_abs, "(", "-name", "*.txt"],
        [tree_abs, "-name", "*.txt", "extra"],
        ["不存在的路径"],
        [tree_abs, "-printf", "%z\n"],
        [tree_abs, "-exec"],
        [tree_abs, "-newer", "不存在"],
    ):
        code, out, err = run_gnu(empty_cwd, argv)
        lines.append(f"$ find {' '.join(argv)}")
        lines.append(f"  exit={code}")
        lines.append(f"  stdout={out.strip()[:200]!r}")
        lines.append(f"  stderr={err.strip()[:300]!r}")

    (OUT_DIR / "probe5.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"probe5 写入 {OUT_DIR / 'probe5.txt'}")


if __name__ == "__main__":
    main()
