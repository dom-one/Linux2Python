"""探针 7：判定 -mmin 的偏移是「公式错」还是「整体平移」。

关键判据：
- 精确形式 -mmin N 与 + 形式 -mmin +N 的分段边界是否一致
  · 若 +N 的边界是 60*N（自然语义）而精确 N 的边界是 60*(N-1)，说明精确分支单独错位
  · 若两者都平移一格，说明是年龄计算整体偏移（时钟或 mtime 读取）
- 用 -newermt（绝对时间）判定 find 看到的 mtime 是否准确
  · -newermt "@(T-61)" 若能命中 mtime=T-60 的文件，说明 find 读到的 mtime 是准的
    （排除了「mtime 被读早 60 秒」这个假设）

结果写到 _data_find7/probe7.txt。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "_data_find7"
GNU_FIND = shutil.which("find") or r"E:\software\Git\Git\usr\bin\find.exe"

AGES = [0, 30, 59, 60, 61, 119, 120, 121, 179, 180, 181]


def build_tree(root: Path, now: float) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for age in AGES:
        path = root / f"age{age:>06d}.txt"
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

    lines: list[str] = []
    lines.append(f"建树时刻 T = {now:.3f}")
    lines.append("")

    lines.append("### 精确形式 -mmin N")
    exact: dict[int, list[int]] = {}
    for n in range(0, 5):
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-mmin", str(n)])
        exact[n] = matched_ages(out)
        lines.append(f"-mmin {n} -> {exact[n]}")
    lines.append("")

    lines.append("### 加号形式 -mmin +N")
    plus: dict[int, list[int]] = {}
    for n in range(0, 5):
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-mmin", f"+{n}"])
        plus[n] = matched_ages(out)
        lines.append(f"-mmin +{n} -> {plus[n]}")
    lines.append("")

    lines.append("### 减号形式 -mmin -N")
    for n in range(0, 4):
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-mmin", f"-{n}"])
        lines.append(f"-mmin -{n} -> {matched_ages(out)}")
    lines.append("")

    lines.append("### -newermt 绝对时间（判定 find 读到的 mtime 是否准确）")
    probes = [
        ("@(T-1)", now - 1),
        ("@(T-61)", now - 61),
        ("@(T+1)", now + 1),
        ("@(T+59)", now + 59),
    ]
    for label, stamp in probes:
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-newermt", f"@{int(stamp)}"])
        lines.append(f"-newermt {label} -> 命中年龄 {matched_ages(out)}")
        if err:
            lines.append(f"    stderr: {err.strip()[:160]}")
    lines.append("")

    lines.append("### -newer 相对参照")
    for offset in (1, 61, 120):
        ref = OUT_DIR / f"ref{offset}.txt"
        ref.write_bytes(b"r\n")
        stamp = now - offset
        os.utime(ref, (stamp, stamp))
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-newer", ref.as_posix()])
        lines.append(f"-newer (参照 mtime = T-{offset}) -> 命中年龄 {matched_ages(out)}")

    (OUT_DIR / "probe7.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"probe7 写入 {OUT_DIR / 'probe7.txt'}")


if __name__ == "__main__":
    main()
