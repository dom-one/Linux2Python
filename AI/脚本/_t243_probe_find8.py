"""探针 8：补齐 -mmin 规则的负年龄段，并核对 -mtime 的 +/- 形式。

已知（探针 7）：
- 精确 -mmin N 命中年龄 [60(N-1), 60N)     —— 相当于 floor(age/60)+1 == N
- -mmin +N 命中 age >= 60N                 —— 自然语义
- -mmin -N 命中 age < 60N                  —— 自然语义
- 精确 -mtime N 命中 [86400N, 86400(N+1))  —— 自然语义（与 -mmin 不一致）

本探针补：
- 未来文件（age 为负）落在哪个分段
- -mtime 的 + / - 形式是否也是自然语义
结果写到 _data_find8/probe8.txt。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "_data_find8"
GNU_FIND = shutil.which("find") or r"E:\software\Git\Git\usr\bin\find.exe"

AGES = [-180, -120, -90, -61, -60, -30, -1, 0, 30, 59, 60, 61, 120, 121]


def build_tree(root: Path, now: float) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for age in AGES:
        path = root / f"age{age:+07d}.txt"
        path.write_bytes(b"x\n")
        stamp = now - age
        os.utime(path, (stamp, stamp))


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


def matched_ages(out: str) -> list[int]:
    return sorted(
        int(line.rsplit("age", 1)[1].split(".")[0])
        for line in out.splitlines()
        if "age" in line
    )


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    tree = OUT_DIR / "tree"
    now = time.time()
    build_tree(tree, now)
    empty_cwd = OUT_DIR / "run"
    empty_cwd.mkdir()
    tree_abs = tree.as_posix()

    lines: list[str] = [f"建树时刻 T = {now:.3f}", ""]
    lines.append(f"样本年龄: {AGES}")
    lines.append("")

    lines.append("### 精确 -mmin N")
    for n in range(-3, 4):
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-mmin", str(n)])
        lines.append(f"-mmin {n:>3} -> {matched_ages(out)}")
    lines.append("")

    lines.append("### -mmin +N")
    for n in range(0, 3):
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-mmin", f"+{n}"])
        lines.append(f"-mmin +{n} -> {matched_ages(out)}")
    lines.append("")

    lines.append("### -mmin -N")
    for n in range(0, 3):
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-mmin", f"-{n}"])
        lines.append(f"-mmin -{n} -> {matched_ages(out)}")
    lines.append("")

    lines.append("### -mtime 的三种形式")
    for spec in ("0", "1", "+0", "+1", "-0", "-1"):
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-mtime", spec])
        lines.append(f"-mtime {spec:>3} -> {matched_ages(out)}")
    lines.append("")

    lines.append("### -mtime 用 2 天前的样本再测一次")
    for spec in ("0", "1", "2", "+0", "+1", "-1", "-2"):
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-mtime", spec, "-name", "age+00086400.txt"])
        lines.append(f"-mtime {spec:>3} (只看 1 天前样本) -> 命中 {matched_ages(out)}")

    (OUT_DIR / "probe8.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"probe8 写入 {OUT_DIR / 'probe8.txt'}")


if __name__ == "__main__":
    main()
