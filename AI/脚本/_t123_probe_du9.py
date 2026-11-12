"""探针 9：--time 对目录给的是「目录自己的 mtime」还是「子树里最新的 mtime」。

做法：把子文件的 mtime 设到未来、把父目录的 mtime 设到过去，
看 GNU 报的是哪一个。
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
DATA = ROOT / "AI" / "数据" / "du_probe9"
OUT = DATA / "probe_out.txt"

GNU_DU = r"E:\software\Git\Git\usr\bin\du.exe"

OLD = 946684800   # 2000-01-01
NEW = 1893456000  # 2030-01-01


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

    lines: list[str] = []

    # 情形一：父目录旧、子文件新
    p1 = DATA / "p1"
    p1.mkdir()
    (p1 / "future.txt").write_bytes(b"x" * 100)
    os.utime(p1 / "future.txt", (NEW, NEW))
    os.utime(p1, (OLD, OLD))

    # 情形二：父目录新、子文件旧
    p2 = DATA / "p2"
    p2.mkdir()
    (p2 / "past.txt").write_bytes(b"x" * 100)
    os.utime(p2 / "past.txt", (OLD, OLD))
    os.utime(p2, (NEW, NEW))

    # 情形三：父目录旧、子目录新
    p3 = DATA / "p3"
    p3.mkdir()
    sub = p3 / "sub"
    sub.mkdir()
    (sub / "f.txt").write_bytes(b"x" * 100)
    os.utime(sub, (NEW, NEW))
    os.utime(p3, (OLD, OLD))

    for args in (["--time", "p1"], ["--time", "-a", "p1"], ["--time", "p2"], ["--time", "p3"], ["--time", "-c", "p1"]):
        code, out, err = run_du(args, DATA)
        lines.append(f"### du {' '.join(args)}  exit={code}")
        for line in out.splitlines():
            lines.append(f"OUT {line!r}")
        for line in err.splitlines():
            lines.append(f"ERR {line!r}")
        lines.append("")

    lines.append("### 实际时间戳")
    for label, path in (
        ("p1 (目录)", p1),
        ("p1/future.txt", p1 / "future.txt"),
        ("p2 (目录)", p2),
        ("p3 (目录)", p3),
        ("p3/sub (目录)", p3 / "sub"),
    ):
        stamp = path.stat().st_mtime
        lines.append(f"{label}: {time.strftime('%Y-%m-%d %H:%M', time.localtime(stamp))} ({stamp})")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
