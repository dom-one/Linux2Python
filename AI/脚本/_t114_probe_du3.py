"""探针 3：钉死 GNU du -h 的人类可读格式，以及 -h 与 --si 的取值口径。

关键问题：
1. -h 的值是「精确字节」还是「按块取整后的字节」
2. 小数位规则：小于 10 保留一位，>= 10 用整数？向上取整还是截断？
3. --si 的 1000 进制与 K/M/G 的 1024 进制
4. -h 与 -b 同时给是否等价于「精确字节的人类可读」

大文件用 fsutil file createnew 建稀疏文件（Python 的 truncate 会真的写零，1GB 要写很久）。
"""

from __future__ import annotations

import ctypes
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "du_probe3"
OUT = DATA / "probe_out.txt"

GNU_DU = r"E:\software\Git\Git\usr\bin\du.exe"

# 覆盖：1 字节、跨 1024 边界、跨 10 进制边界、跨 M/G 边界
SIZES = [
    0, 1, 10, 999, 1000, 1023, 1024, 1025, 1100, 1536, 2000,
    5120, 9216, 10240, 102400, 1048575, 1048576, 1048577,
    1572864, 10485760, 1073741824, 1610612736, 1099511627776,
]


def make_sparse(path: Path, size: int) -> None:
    """建一个指定大小的稀疏文件。

    不用 fsutil：它是控制台程序，走 ANSI 代码页，中文路径会被改写。
    这里用 ctypes 直接调 CreateFileW + SetFilePointerEx + SetEndOfFile。
    """
    if size == 0:
        path.write_bytes(b"")
        return
    kernel32 = ctypes.windll.kernel32
    GENERIC_WRITE = 0x40000000
    CREATE_ALWAYS = 2
    FILE_ATTRIBUTE_NORMAL = 0x80
    handle = kernel32.CreateFileW(
        str(path), GENERIC_WRITE, 0, None, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, None
    )
    if handle == -1 or handle == 0xFFFFFFFFFFFFFFFF:
        raise OSError(f"CreateFileW 失败: {path}")
    try:
        distance = ctypes.c_longlong(size)
        kernel32.SetFilePointerEx(handle, distance, None, 0)  # FILE_BEGIN
        kernel32.SetEndOfFile(handle)
    finally:
        kernel32.CloseHandle(handle)


def du_bytes(path: Path, args: list[str]) -> str:
    proc = subprocess.run(
        [GNU_DU, *args, path.name],
        cwd=str(DATA),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = proc.stdout.strip()
    if "\t" in out:
        out = out.split("\t", 1)[0]
    return out if out else f"<empty rc={proc.returncode} err={proc.stderr.strip()!r}>"


def main() -> int:
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)

    lines: list[str] = []
    lines.append("size\tdu -bh\tdu --si -bh\tdu -b")
    for size in SIZES:
        f = DATA / f"f{size}.bin"
        make_sparse(f, size)
        lines.append(
            "\t".join(
                [str(size), du_bytes(f, ["-bh"]), du_bytes(f, ["--si", "-bh"]), du_bytes(f, ["-b"])]
            )
        )
    lines.append("")

    # -h 与块取整的关系：同一棵树，-h vs --apparent-size -h
    tree = DATA / "tree"
    tree.mkdir()
    (tree / "a.bin").write_bytes(b"x" * 3000)
    (tree / "b.bin").write_bytes(b"y" * 3000)
    lines.append("### 同一棵树的几种口径")
    for args in (
        ["-h", "tree"],
        ["--apparent-size", "-h", "tree"],
        ["-bh", "tree"],
        ["-B", "100", "-h", "tree"],
        ["-h", "-B", "100", "tree"],
        ["--si", "-h", "tree"],
    ):
        proc = subprocess.run(
            [GNU_DU, *args],
            cwd=str(DATA),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        lines.append(f"### du {' '.join(args)}  exit={proc.returncode}")
        for line in proc.stdout.splitlines():
            lines.append(f"OUT {line!r}")
        for line in proc.stderr.splitlines():
            lines.append(f"ERR {line!r}")
        lines.append("")

    # -h 与 -b 同时给是否被 GNU 接受
    lines.append("### -h -b 组合的报错检查")
    for args in (["-h", "-b", "tree"], ["-h", "-B", "100", "tree"]):
        proc = subprocess.run(
            [GNU_DU, *args],
            cwd=str(DATA),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        lines.append(
            f"du {' '.join(args)} exit={proc.returncode} out={proc.stdout!r} err={proc.stderr!r}"
        )
    lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
