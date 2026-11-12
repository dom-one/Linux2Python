"""差分对照：本实现的 du 与 GNU du 的逐字节比对。

本实现默认按「表观大小」统计，对应的 GNU 基线是 `du --apparent-size`，
所以每组用例都把 --apparent-size 插到 GNU 那边，其余选项保持一致。

比较方式：
- 输出的行集合（排序后）必须完全一致——GNU 用目录原始顺序，本实现按名字排序
- 退出码：GNU 的错误路径是 1，本项目约定是 2，这里分开记
- 差异逐条写进 diff_out.txt，不靠终端显示判断
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "du_diff"
OUT = DATA / "diff_out.txt"

GNU_DU = r"E:\software\Git\Git\usr\bin\du.exe"
MAIN = ROOT / "main.py"


def build_fixture(base: Path) -> None:
    """造一棵有代表性的目录树：空目录、0 字节文件、跨块大小的文件、多级目录。"""
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    tree = base / "tree"
    tree.mkdir()
    (tree / "a.txt").write_bytes(b"A" * 10)
    (tree / "b.txt").write_bytes(b"B" * 2048)
    (tree / "c.txt").write_bytes(b"C" * 100)
    (tree / "zero.txt").write_bytes(b"")
    (tree / "empty").mkdir()
    sub = tree / "sub"
    sub.mkdir()
    (sub / "d.txt").write_bytes(b"D" * 5)
    (sub / "mid.bin").write_bytes(b"E" * 3000)
    deeper = sub / "deeper"
    deeper.mkdir()
    (deeper / "e.txt").write_bytes(b"F" * 4096)
    (base / "single.txt").write_bytes(b"G" * 777)


def run_ours(args: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(MAIN), "du", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_gnu(args: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [GNU_DU, "--apparent-size", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


CASES = [
    ["tree"],
    ["-a", "tree"],
    ["-s", "tree"],
    ["-c", "tree"],
    ["-c", "-s", "tree"],
    ["-a", "-c", "tree"],
    ["-b", "tree"],
    ["-b", "-a", "tree"],
    ["-h", "tree"],
    ["-h", "-a", "tree"],
    ["--si", "tree"],
    ["--si", "-a", "tree"],
    ["-h", "-s", "tree"],
    ["-k", "tree"],
    ["-m", "tree"],
    ["-B", "100", "tree"],
    ["-B", "100", "-a", "tree"],
    ["-B", "1K", "tree"],
    ["-d", "0", "tree"],
    ["-d", "1", "tree"],
    ["-d", "2", "tree"],
    ["-a", "-d", "1", "tree"],
    ["-x", "tree"],
    ["-S", "tree"],
    ["-S", "-a", "tree"],
    ["-t", "1K", "tree"],
    ["-t", "1K", "-a", "tree"],
    ["-t", "-1K", "tree"],
    ["-t", "-1K", "-a", "tree"],
    ["-t", "1", "-a", "tree"],
    ["-t", "2048", "-a", "tree"],
    ["-t", "1M", "-a", "tree"],
    ["-t", "0", "tree"],
    ["single.txt"],
    ["-a", "single.txt"],
    ["tree", "single.txt"],
    ["tree", "tree/a.txt"],
    ["tree/sub"],
    ["tree/"],
    ["./tree"],
    ["."],
    ["-0", "-s", "tree"],
    ["--time", "tree"],
    ["--time", "-a", "tree"],
    ["-l", "tree", "tree/a.txt"],
    ["tree", "tree"],
    ["tree", "tree/sub"],
    ["-s", "tree", "tree/a.txt", "tree/sub"],
    ["-a", "tree", "tree/a.txt"],
    ["-l", "tree", "tree/a.txt"],
    ["-L", "tree"],
    ["-H", "tree"],
    ["-P", "tree"],
    ["-x", "tree"],
    ["-x", "."],
    ["--time", "-s", "tree"],
    ["--time", "-c", "tree"],
    ["-B", "1", "tree"],
    ["-B", "2", "tree"],
    ["-B", "512", "tree"],
    ["-B", "1M", "tree"],
    ["-t", "5", "-a", "tree"],
    ["-t", "-5", "-a", "tree"],
    ["-t", "1K", "-s", "tree"],
    ["-h", "-c", "tree"],
    ["--si", "-c", "tree"],
    ["-d", "3", "tree"],
    ["-d", "1", "-s", "tree"],
    ["-S", "-c", "tree"],
    ["-S", "-d", "1", "tree"],
    ["nosuchfile"],
    ["tree", "nosuchfile"],
    ["nosuch1", "nosuch2"],
    ["-s", "tree", "nosuchfile"],
    ["single.txt", "tree"],
    ["-a", "single.txt", "tree"],
    ["-c", "single.txt", "tree"],
    ["-h", "single.txt"],
    ["--si", "single.txt"],
    ["-b", "single.txt"],
    ["-k", "single.txt"],
    ["-m", "single.txt"],
]


def main() -> int:
    base = DATA
    build_fixture(base)

    lines: list[str] = []
    same = 0
    diff = 0
    for args in CASES:
        our_code, our_out, our_err = run_ours(args, base)
        gnu_code, gnu_out, gnu_err = run_gnu(args, base)
        our_lines = sorted(our_out.replace("\0", "\n").splitlines())
        gnu_lines = sorted(gnu_out.replace("\0", "\n").splitlines())
        if our_lines == gnu_lines:
            same += 1
            continue
        diff += 1
        lines.append(f"### 不一致：du {' '.join(args)}")
        lines.append(f"  ours exit={our_code} err={our_err.strip()!r}")
        lines.append(f"  gnu  exit={gnu_code} err={gnu_err.strip()!r}")
        only_ours = [item for item in our_lines if item not in gnu_lines]
        only_gnu = [item for item in gnu_lines if item not in our_lines]
        for item in only_ours:
            lines.append(f"  ONLY-OURS {item!r}")
        for item in only_gnu:
            lines.append(f"  ONLY-GNU  {item!r}")
        lines.append("")

    lines.insert(0, f"一致 {same} 组，不一致 {diff} 组，共 {len(CASES)} 组\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
