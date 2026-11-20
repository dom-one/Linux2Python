"""精确定位 -h 人类可读的档位切换边界：项目 vs GNU。

问题：把字节数换算成 1024 进制后，商落在 [1000, 1024) 这一段时，
GNU 继续用 K（显示 1000K~1023K），本实现直接换成 M（显示 1.0M）。

这个脚本二分找出两边各自的切换点。

产出：AI/数据/du_h_boundary.txt
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "du_demo"
OUT = ROOT / "AI" / "数据" / "du_h_boundary.txt"
GNU_DU = Path(r"E:\software\Git\Git\usr\bin\du.exe")

lines: list[str] = []


def emit(text: str = "") -> None:
    lines.append(text)


def unit_of(tool: str, size: int, workdir: Path) -> str:
    """给一个精确大小的文件，返回 -h 显示的大小列（不含路径）。"""
    target = workdir / "one.bin"
    if target.exists():
        target.unlink()
    target.write_bytes(b"\0" * size)
    if tool == "ours":
        cmd = [sys.executable, str(ROOT / "main.py"), "du", "-h", "one.bin"]
    else:
        cmd = [str(GNU_DU), "--apparent-size", "-h", "one.bin"]
    proc = subprocess.run(cmd, cwd=str(workdir), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    # 输出是「大小<TAB>路径」，只要第一列；不能对整行 endswith，
    # 因为路径尾巴是 one.bin，永远不以 M 结尾（二分查找会恒为 False）
    return proc.stdout.strip().split("\t")[0]


def main() -> None:
    workdir = DATA / "onefile"
    workdir.mkdir(exist_ok=True)
    if not GNU_DU.is_file():
        print("找不到 GNU du")
        return 1

    emit("=" * 72)
    emit("一、二分找两边的档位切换点")
    emit("=" * 72)
    emit()

    # 项目：从 1M 往上找第一个显示成 M 的更小的值（K→M 的切换点）
    def project_switches_to_M(lo: int, hi: int) -> int:
        """在 [lo, hi] 里找最小的 size 使项目显示的单位是 M。"""
        while lo < hi:
            mid = (lo + hi) // 2
            if unit_of("ours", mid, workdir).endswith("M"):
                hi = mid
            else:
                lo = mid + 1
        return lo

    def gnu_switches_to_M(lo: int, hi: int) -> int:
        while lo < hi:
            mid = (lo + hi) // 2
            if unit_of("gnu", mid, workdir).endswith("M"):
                hi = mid
            else:
                lo = mid + 1
        return lo

    ours_switch = project_switches_to_M(999 * 1024, 1024 * 1024)
    gnu_switch = gnu_switches_to_M(999 * 1024, 1024 * 1024)

    emit("  项目 K→M 切换点: %d 字节 (%.4f K)" % (ours_switch, ours_switch / 1024))
    emit("  GNU  K→M 切换点: %d 字节 (%.4f K)" % (gnu_switch, gnu_switch / 1024))
    emit("  差 %d 字节" % (gnu_switch - ours_switch))
    emit()
    emit("  项目的规则: size > 999 * 1024 = %d 时换档" % (999 * 1024))
    emit("  ⇒ 项目的切换点就是 999K + 1 = %d" % (999 * 1024 + 1))
    emit()

    emit("=" * 72)
    emit("二、切换点前后各取几个样本")
    emit("=" * 72)
    emit()
    samples = [
        999 * 1024,
        999 * 1024 + 1,
        1000 * 1024,
        1000 * 1024 + 1,
        1023 * 1024,
        1023 * 1024 + 1,
        gnu_switch - 1,
        gnu_switch,
        1024 * 1024 - 1,
        1024 * 1024,
    ]
    emit("  %-14s %-10s %-10s %s" % ("字节数", "项目", "GNU", ""))
    for size in sorted(set(samples)):
        ours = unit_of("ours", size, workdir)
        gnu = unit_of("gnu", size, workdir)
        mark = "一致" if ours == gnu else "★不一致"
        emit("  %-14d %-10s %-10s %s" % (size, ours, gnu, mark))
    emit()

    emit("=" * 72)
    emit("三、结论")
    emit("=" * 72)
    emit()
    emit("  本实现的 _format_human 用「商不超过 999」选档（du.py 第 492 行）：")
    emit("      while size > 999 * divisor:")
    emit("  GNU 用的是「商不超过 1023」——商到 1024 才换档。")
    emit()
    emit("  所以字节数落在 [%d, %d] 这一段时两边显示不同：" % (
        ours_switch, gnu_switch - 1))
    emit("      项目显示 1.0M，GNU 显示 1000K ~ 1023K。")
    emit("  差 %d 字节（约 %.1f KB）。" % (
        gnu_switch - ours_switch, (gnu_switch - ours_switch) / 1024))
    emit()

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("边界定位写入: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
