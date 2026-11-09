"""探针 9：最终判定 —— 精确形式的分段边界到底在哪。

造几个「卡在边界上」的样本：
- 正好 90 秒（自然规则应落 -mmin 1，平移一格规则应落 -mmin 2）
- 正好 1 天（自然规则应落 -mtime 1，平移一格规则应落 -mtime 2）
- 正好 2 天

结果写到 _data_find9/probe9.txt。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "_data_find9"
GNU_FIND = shutil.which("find") or r"E:\software\Git\Git\usr\bin\find.exe"

SAMPLES = {
    "s0000090": 90,          # 90 秒
    "s0000060": 60,          # 60 秒
    "s0000120": 120,         # 120 秒
    "s0864000": 86400,       # 1 天
    "s1728000": 172800,      # 2 天
    "s0043200": 43200,       # 半天
}


def build_tree(root: Path, now: float) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, age in SAMPLES.items():
        path = root / f"{name}.txt"
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

    lines = [f"建树时刻 T = {now:.3f}", f"样本(名字=年龄秒): {SAMPLES}", ""]
    for pred, values in (("-mmin", ["0", "1", "2", "3"]), ("-mtime", ["0", "1", "2", "3"])):
        lines.append(f"### {pred} 精确形式")
        for v in values:
            code, out, err = run_gnu(empty_cwd, [tree_abs, pred, v])
            hits = sorted(
                line.rsplit("/", 1)[1].split(".")[0]
                for line in out.splitlines()
                if line.endswith(".txt")
            )
            lines.append(f"{pred} {v} -> {hits}")
        lines.append("")

    (OUT_DIR / "probe9.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"probe9 写入 {OUT_DIR / 'probe9.txt'}")


if __name__ == "__main__":
    main()
