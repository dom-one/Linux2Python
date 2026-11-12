"""探针 8：两个待定口径。

1. `-s` 与 `-d N` 同给是不是冲突（-d 0 呢？），报错文案与退出码
2. `--time -c` 的 total 行带不带时间戳，时间戳取的是哪个值
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "du_probe8"
OUT = DATA / "probe_out.txt"

GNU_DU = r"E:\software\Git\Git\usr\bin\du.exe"


def run_du(args: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [GNU_DU, "--apparent-size", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)
    tree = DATA / "tree"
    tree.mkdir()
    # 三个不同时间点的文件
    old = tree / "old.txt"
    mid = tree / "mid.txt"
    new = tree / "new.txt"
    for path, stamp in ((old, 1600000000), (mid, 1700000000), (new, 1750000000)):
        path.write_bytes(b"x" * 100)
        os.utime(path, (stamp, stamp))
    sub = tree / "sub"
    sub.mkdir()
    (sub / "inner.txt").write_bytes(b"y" * 100)
    os.utime(sub / "inner.txt", (1650000000, 1650000000))

    lines: list[str] = []

    for args in (
        ["-s", "-d", "0", "tree"],
        ["-s", "-d", "1", "tree"],
        ["-s", "--max-depth=0", "tree"],
        ["-s", "--max-depth=1", "tree"],
        ["-d", "1", "-s", "tree"],
        ["--time", "-c", "tree"],
        ["--time", "-a", "-c", "tree"],
        ["--time", "tree"],
        ["--time", "tree/old.txt"],
        ["--time", "tree/new.txt"],
    ):
        code, out, err = run_du(args, DATA)
        lines.append(f"### du {' '.join(args)}  exit={code}")
        for line in out.splitlines():
            lines.append(f"OUT {line!r}")
        for line in err.splitlines():
            lines.append(f"ERR {line!r}")
        lines.append("")

    lines.append("### 各文件的时间戳（本地时区）")
    for path in (old, mid, new, sub / "inner.txt"):
        lines.append(f"{path.name}: {time.strftime('%Y-%m-%d %H:%M', time.localtime(path.stat().st_mtime))}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
