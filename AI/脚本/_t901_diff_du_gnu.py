"""du 实现与 GNU coreutils 8.32 的差分对照。

对照基线是 GNU du 的 --apparent-size（表观大小）口径，因为本实现默认就按
文件字节数统计，Windows 上也拿不到 st_blocks。

产出：AI/数据/du_gnu_diff.txt（人看的对照表）+ 终端摘要。

用法:
    python AI/脚本/_t901_diff_du_gnu.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "du_demo"
OUT = ROOT / "AI" / "数据" / "du_gnu_diff.txt"

GNU_DU = Path(r"E:\software\Git\Git\usr\bin\du.exe")

# (说明, 项目参数, GNU 参数)
# GNU 侧统一加 --apparent-size，其余参数照抄
CASES = [
    ("默认（1K 块，向上取整）", [], []),
    ("-b 按字节", ["-b"], ["--apparent-size", "-b"]),
    ("-a 连文件一起列", ["-a"], ["--apparent-size", "-a"]),
    ("-s 只给总数", ["-s"], ["--apparent-size", "-s"]),
    ("-c 末尾加 total", ["-s", "-c"], ["--apparent-size", "-s", "-c"]),
    ("-d 1 只打印到第 1 层", ["-d", "1"], ["--apparent-size", "-d", "1"]),
    ("-d 0 只打印操作数", ["-d", "0"], ["--apparent-size", "-d", "0"]),
    ("-t 1024 阈值", ["-t", "1024", "-a"], ["--apparent-size", "-t", "1024", "-a"]),
    ("-t -1024 负阈值", ["-t", "-1024", "-a"], ["--apparent-size", "-t", "-1024", "-a"]),
    ("-h 人类可读", ["-s", "-h"], ["--apparent-size", "-s", "-h"]),
    ("--si 十进制", ["-s", "--si"], ["--apparent-size", "-s", "--si"]),
    ("-B 100 块大小", ["-s", "-B", "100"], ["--apparent-size", "-s", "-B", "100"]),
    ("-S 目录不含子目录", ["-s", "-S"], ["--apparent-size", "-s", "-S"]),
    ("-0 NUL 分隔", ["-s", "-0"], ["--apparent-size", "-s", "-0"]),
    ("同一棵树给两次", ["tree", "tree"], ["--apparent-size", "tree", "tree"]),
    ("-l 硬链接重复计", ["-s", "-l", "tree", "tree"], ["--apparent-size", "-s", "-l", "tree", "tree"]),
]


def run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    """跑一条命令，返回 (退出码, stdout, stderr)。"""
    proc = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> None:
    if not GNU_DU.is_file():
        print("找不到 GNU du: %s" % GNU_DU)
        return 1
    if not DATA.is_dir():
        print("夹具不存在，先跑 _t900_make_du_fixture.py")
        return 1

    lines: list[str] = []
    same = 0
    diff = 0

    for label, ours, gnu in CASES:
        our_code, our_out, our_err = run(
            [sys.executable, str(ROOT / "main.py"), "du", *ours, "tree"], DATA)
        gnu_code, gnu_out, gnu_err = run(
            [GNU_DU, *gnu, "tree"], DATA)

        lines.append("=" * 72)
        lines.append("案例: %s" % label)
        lines.append("  项目参数: du %s tree" % " ".join(ours))
        lines.append("  GNU 参数: du %s tree" % " ".join(gnu))
        lines.append("-" * 72)
        lines.append("  [项目] 退出码 %d" % our_code)
        for ln in our_out.splitlines():
            lines.append("    | %s" % ln)
        if our_err.strip():
            for ln in our_err.splitlines():
                lines.append("    E %s" % ln)
        lines.append("  [GNU ] 退出码 %d" % gnu_code)
        for ln in gnu_out.splitlines():
            lines.append("    | %s" % ln)
        if gnu_err.strip():
            for ln in gnu_err.splitlines():
                lines.append("    E %s" % ln)

        # 逐行比对（GNU 的排序与目录大小口径不同，这里只标出是否完全一致）
        if our_out == gnu_out and our_code == gnu_code:
            lines.append("  => 逐字节一致")
            same += 1
        else:
            lines.append("  => 有差异")
            diff += 1
        lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("对照结果写入: %s" % OUT)
    print("逐字节一致 %d 例，有差异 %d 例" % (same, diff))
    return 0


if __name__ == "__main__":
    sys.exit(main())
