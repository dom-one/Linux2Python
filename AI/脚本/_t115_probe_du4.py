"""探针 4：钉死 GNU du -h 的小数位边界、--si 的单位阶梯、负阈值的比较口径。

要回答的：
1. 「小于 10 保留一位小数、>= 10 用整数」的分界看的是取整前还是取整后的值
2. --si 的单位字母（k/M/G）与 1000 进制阶梯
3. 负阈值 -t 是跟「显示值」比还是跟「原始字节」比
"""

from __future__ import annotations

import ctypes
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "du_probe4"
OUT = DATA / "probe_out.txt"

GNU_DU = r"E:\software\Git\Git\usr\bin\du.exe"


def make_sparse(path: Path, size: int) -> None:
    if size == 0:
        path.write_bytes(b"")
        return
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateFileW(str(path), 0x40000000, 0, None, 2, 0x80, None)
    if handle == -1 or handle == 0xFFFFFFFFFFFFFFFF:
        raise OSError(f"CreateFileW 失败: {path}")
    try:
        distance = ctypes.c_longlong(size)
        kernel32.SetFilePointerEx(handle, distance, None, 0)
        kernel32.SetEndOfFile(handle)
    finally:
        kernel32.CloseHandle(handle)


def run_du(args: list[str]) -> str:
    proc = subprocess.run(
        [GNU_DU, *args],
        cwd=str(DATA),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = proc.stdout.strip()
    return out if out else f"<empty rc={proc.returncode} err={proc.stderr.strip()!r}>"


def main() -> int:
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)

    lines: list[str] = []

    # --- 1. 小数位边界 ---
    lines.append("### 小数位边界（-h）")
    lines.append("size\t-h\t--si -h")
    for size in (10239, 10240, 10241, 102399, 102400, 102401, 10485759, 10485760):
        f = DATA / f"b{size}.bin"
        make_sparse(f, size)
        h = run_du(["-bh", f.name]).split("\t")[0]
        si = run_du(["--si", "-bh", f.name]).split("\t")[0]
        lines.append(f"{size}\t{h}\t{si}")
    lines.append("")

    # --- 2. --si 的单位阶梯 ---
    lines.append("### --si 单位阶梯")
    for size in (999, 1000, 1001, 1000000, 1000001, 10**9, 10**10):
        f = DATA / f"c{size}.bin"
        make_sparse(f, size)
        lines.append(f"{size}\tsi={run_du(['--si', '-bh', f.name]).split(chr(9))[0]}")
    lines.append("")

    # --- 3. 负阈值比的是显示值还是原始字节 ---
    lines.append("### 负阈值口径")
    tree = DATA / "t"
    tree.mkdir()
    (tree / "small.bin").write_bytes(b"x" * 100)  # 显示值 1 块，原始 100 字节
    (tree / "mid.bin").write_bytes(b"y" * 2048)  # 显示值 2 块，原始 2048 字节
    (tree / "big.bin").write_bytes(b"z" * 4096)  # 显示值 4 块，原始 4096 字节
    for args in (
        ["--apparent-size", "-t", "-1024", "-a", "t"],
        ["--apparent-size", "-t", "-2048", "-a", "t"],
        ["--apparent-size", "-t", "-1", "-a", "t"],
        ["--apparent-size", "-t", "1", "-a", "t"],
        ["--apparent-size", "-t", "2", "-a", "t"],
        ["-b", "-t", "-1024", "-a", "t"],
        ["-b", "-t", "-2048", "-a", "t"],
        ["-b", "-t", "1024", "-a", "t"],
    ):
        lines.append(f"### du {' '.join(args)}")
        for line in run_du(args).splitlines():
            lines.append(f"OUT {line!r}")
        lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
