"""探针 2：把 GNU du 的取整模型、去重规则、阈值语义和 Windows 侧的分配大小测死。

关注点：
1. --apparent-size 是「先按原始字节求和再取整一次」还是「每个文件各自取整再求和」
2. 默认（磁盘占用）模式下 MSYS2 的 st_blocks 到底是什么
3. 同一个 inode 被多个操作数覆盖时是否去重、是否还打行
4. -t 阈值比的是原始字节还是缩放后的值
5. Windows 的 GetCompressedFileSizeW 能不能拿到真实分配大小
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "du_probe2"
OUT = DATA / "probe_out.txt"

GNU_DU = r"E:\software\Git\Git\usr\bin\du.exe"
GNU_STAT = r"E:\software\Git\Git\usr\bin\stat.exe"


def build_fixture() -> Path:
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)
    tree = DATA / "tree"
    tree.mkdir()
    (tree / "a.txt").write_bytes(b"A" * 10)
    (tree / "b.txt").write_bytes(b"B" * 2048)
    (tree / "c.txt").write_bytes(b"C" * 100)
    (tree / "zero.txt").write_bytes(b"")
    sub = tree / "sub"
    sub.mkdir()
    (sub / "d.txt").write_bytes(b"D" * 5)
    deeper = sub / "deeper"
    deeper.mkdir()
    (deeper / "e.txt").write_bytes(b"E" * 3000)
    return tree


def run_du(args: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [GNU_DU, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def show(title, code, out, err, lines):
    lines.append(f"### {title}")
    lines.append(f"exit={code}")
    for line in out.splitlines():
        lines.append(f"OUT {line!r}")
    if not out:
        lines.append("OUT <empty>")
    for line in err.splitlines():
        lines.append(f"ERR {line!r}")
    if not err:
        lines.append("ERR <empty>")
    lines.append("")


def main() -> int:
    tree = build_fixture()
    lines: list[str] = []

    cases = [
        ["--apparent-size", "-a", "tree"],
        ["-b", "-a", "tree"],
        ["--apparent-size", "-c", "tree"],
        ["-b", "-c", "tree"],
        ["-h", "--apparent-size", "tree"],
        ["--si", "--apparent-size", "tree"],
        ["-B", "100", "--apparent-size", "tree"],
        ["-B", "100", "tree"],
        ["-B", "100", "-a", "tree"],
        ["-s", "tree/a.txt", "tree/b.txt"],
        ["-s", "tree/sub", "tree/a.txt"],
        ["tree", "tree/a.txt"],
        ["-a", "tree", "tree/a.txt"],
        ["-t", "0", "tree"],
        ["-t", "1K", "-a", "tree"],
        ["-t", "2048", "tree"],
        ["-t", "2048", "--apparent-size", "tree"],
        ["-t", "-2048", "--apparent-size", "tree"],
        ["-c", "-s", "tree", "tree/a.txt"],
        ["."],
        ["-s", "."],
        ["--max-depth=1", "tree"],
        ["--time", "-a", "tree"],
        ["-S", "-a", "tree"],
        ["-s", "-h", "tree"],
        ["-a", "-s", "tree"],
    ]
    for args in cases:
        code, out, err = run_du(args, DATA)
        show("du " + " ".join(args), code, out, err, lines)

    # --- MSYS2 stat 的 st_blocks / st_blksize ---
    lines.append("### MSYS2 stat -c '%s %b %B %n'")
    proc = subprocess.run(
        [GNU_STAT, "-c", "%s %b %B %n", "tree/a.txt", "tree/b.txt", "tree/c.txt",
         "tree/zero.txt", "tree/sub", "tree/sub/deeper", "tree"],
        cwd=str(DATA),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    for line in proc.stdout.splitlines():
        lines.append(f"STAT {line!r}")
    lines.append(f"STAT exit={proc.returncode} err={proc.stderr!r}")
    lines.append("")

    # --- Windows 的 GetCompressedFileSizeW：真实分配大小 ---
    lines.append("### GetCompressedFileSizeW (真实分配字节)")
    kernel32 = ctypes.windll.kernel32
    kernel32.GetCompressedFileSizeW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p]
    kernel32.GetCompressedFileSizeW.restype = ctypes.c_uint32
    for rel in ("tree/a.txt", "tree/b.txt", "tree/c.txt", "tree/zero.txt",
                "tree/sub", "tree/sub/deeper", "tree"):
        p = DATA / rel
        st = os.stat(str(p))
        high = ctypes.c_uint32(0)
        low = kernel32.GetCompressedFileSizeW(str(p), ctypes.byref(high))
        alloc = (high.value << 32) | low
        lines.append(
            f"{rel}: st_size={st.st_size} allocated={alloc} "
            f"cluster_ratio={(alloc / st.st_size) if st.st_size else 'n/a'}"
        )
    lines.append("")

    # --- 目录自身的 st_size 在 Windows 上稳不稳 ---
    lines.append("### 目录 st_size 稳定性（Windows）")
    big = DATA / "manyfiles"
    big.mkdir()
    for i in range(30):
        (big / f"f{i}.txt").write_bytes(b"x")
    for _ in range(3):
        lines.append(f"manyfiles st_size={os.stat(str(big)).st_size}")
    lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
