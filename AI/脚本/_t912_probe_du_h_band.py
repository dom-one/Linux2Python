"""把 -h 换档差异的区间边界再钉一遍（多点采样，确认不是单点巧合）。

产出：AI/数据/du_h_band.txt
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "du_demo"
OUT = ROOT / "AI" / "数据" / "du_h_band.txt"
GNU_DU = Path(r"E:\software\Git\Git\usr\bin\du.exe")

lines: list[str] = []


def emit(text: str = "") -> None:
    lines.append(text)


def h_out(tool: str, size: int, workdir: Path) -> str:
    target = workdir / "one.bin"
    target.write_bytes(b"\0" * size)
    if tool == "ours":
        cmd = [sys.executable, str(ROOT / "main.py"), "du", "-h", "one.bin"]
    else:
        cmd = [str(GNU_DU), "--apparent-size", "-h", "one.bin"]
    proc = subprocess.run(cmd, cwd=str(workdir), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return proc.stdout.strip().split("\t")[0]


def main() -> None:
    workdir = DATA / "onefile"
    workdir.mkdir(exist_ok=True)

    emit("=" * 72)
    emit("-h 在 1024 进制下的换档行为：项目 vs GNU（多点采样）")
    emit("=" * 72)
    emit()
    emit("  %-12s %-10s %-10s %s" % ("字节数", "项目", "GNU", ""))
    points = [
        999 * 1024 - 1,
        999 * 1024,
        999 * 1024 + 1,
        1000 * 1024,
        1000 * 1024 + 1,
        1010 * 1024,
        1022 * 1024,
        1023 * 1024 - 1,
        1023 * 1024,
        1023 * 1024 + 1,
        1023 * 1024 + 2,
        1024 * 1024 - 1,
        1024 * 1024,
    ]
    diff_lo = None
    diff_hi = None
    for size in points:
        ours = h_out("ours", size, workdir)
        gnu = h_out("gnu", size, workdir)
        mark = "" if ours == gnu else "★不一致"
        if ours != gnu:
            if diff_lo is None:
                diff_lo = size
            diff_hi = size
        emit("  %-12d %-10s %-10s %s" % (size, ours, gnu, mark))
    emit()

    # 精确的二分：项目从 K 换到 M 的最小字节数
    def first_M(tool: str, lo: int, hi: int) -> int:
        while lo < hi:
            mid = (lo + hi) // 2
            if h_out(tool, mid, workdir).endswith("M"):
                hi = mid
            else:
                lo = mid + 1
        return lo

    ours_switch = first_M("ours", 999 * 1024, 1024 * 1024)
    gnu_switch = first_M("gnu", 999 * 1024, 1024 * 1024)
    emit("  项目 K→M 的最小字节数: %d" % ours_switch)
    emit("  GNU  K→M 的最小字节数: %d" % gnu_switch)
    emit()
    emit("  ⇒ 不一致的区间: [%d, %d]，共 %d 字节" % (
        ours_switch, gnu_switch - 1, gnu_switch - ours_switch))
    emit("    项目显示 1.0M，GNU 显示 1000K ~ 1023K。")
    emit()

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("区间采样写入: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
