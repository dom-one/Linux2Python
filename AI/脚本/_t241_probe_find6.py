"""探针 6：精确定位 -mmin 的「年龄 → 分段」映射。

探针 5 显示 -mmin 1 命中 0~59 秒、-mmin 2 命中 60~119 秒，
看起来整条映射被平移了一段。本探针在每个 60 秒边界附近造细粒度样本，
直接读出「年龄落在哪个分段」，再用 Python 独立复算公式验证。

结果写到 _data_find6/probe6.txt。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "_data_find6"
GNU_FIND = shutil.which("find") or r"E:\software\Git\Git\usr\bin\find.exe"

# 每个 60 秒边界附近取样
AGES = [
    0, 30, 59, 60, 61, 89, 90, 91,
    119, 120, 121, 149, 150, 151,
    179, 180, 181, 209, 210, 211,
    239, 240, 241, 269, 270, 271,
]


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

    # 每个 N 命中的年龄集合
    band: dict[int, set[int]] = {}
    for n in range(0, 6):
        code, out, err = run_gnu(empty_cwd, [tree_abs, "-mmin", str(n)])
        band[n] = {
            int(line.rsplit("age", 1)[1].split(".")[0])
            for line in out.splitlines()
            if "age" in line
        }

    lines: list[str] = []
    lines.append("### 各 -mmin N 命中的年龄（秒）")
    for n, ages in band.items():
        lines.append(f"-mmin {n} -> {sorted(ages)}")

    lines.append("")
    lines.append("### 每个年龄落在哪个分段")
    assignment: dict[int, int] = {}
    for age in AGES:
        hits = [n for n, ages in band.items() if age in ages]
        assignment[age] = hits[0] if hits else -1
        lines.append(f"年龄 {age:>4} 秒 -> 分段 {assignment[age]}")

    lines.append("")
    lines.append("### 用候选公式复算（以采样时刻 now 为基准）")
    candidates = {
        "floor(age/60)": lambda age: age // 60,
        "floor(age/60)+1": lambda age: age // 60 + 1,
        "ceil(age/60)": lambda age: -(-age // 60),
        "round(age/60)": lambda age: (age + 30) // 60,
    }
    for name, fn in candidates.items():
        ok = all(fn(age) == assignment[age] for age in AGES)
        lines.append(f"{name:<16} -> {'完全吻合' if ok else '不吻合'}")
        if not ok:
            bad = [(age, assignment[age], fn(age)) for age in AGES if fn(age) != assignment[age]]
            lines.append(f"    差异（年龄, 实测, 公式）: {bad[:8]}")

    lines.append("")
    lines.append("### 实际执行时刻（考虑 find 启动有延迟）")
    lines.append(f"建树时刻 now = {now:.3f}")
    after = time.time()
    lines.append(f"全部探查结束   = {after:.3f}（find 实际启动时间在此之前）")

    (OUT_DIR / "probe6.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"probe6 写入 {OUT_DIR / 'probe6.txt'}")


if __name__ == "__main__":
    main()
