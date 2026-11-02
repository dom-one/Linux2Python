"""探针第六轮：把乘数后缀表量出来。

用一个 3,000,000 字节的文件，把每个后缀的真实字节数打印出来，
这样 1000 / 1024 / 1024^2 / 1000^2 都能区分开。
GNU head 的帮助文本与实际行为不一致（帮助说 kB=1000，实测 k=1024），
所以只能以实测为准。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
DATA = AI_DIR / "数据"

GNU_HEAD = r"C:\Program Files\Git\usr\bin\head.exe"
FILE_SIZE = 3_000_000


def locate_head() -> str:
    candidate = shutil.which("head")
    if candidate and "System32" not in candidate:
        return candidate
    return GNU_HEAD


def measure(suffix: str, cwd: Path) -> tuple[int, int, str]:
    proc = subprocess.run(
        [locate_head(), "-c", f"1{suffix}", "big.bin"],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        return proc.returncode, 0, proc.stderr.decode("utf-8", "replace").strip()
    return proc.returncode, len(proc.stdout), ""


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    DATA.mkdir(parents=True, exist_ok=True)

    root = Path(tempfile.mkdtemp(prefix="probe_head6_"))
    try:
        (root / "big.bin").write_bytes(b"X" * FILE_SIZE)

        candidates = [
            "", "b", "c", "k", "K", "m", "M", "g", "G", "t", "T",
            "p", "P", "e", "E", "z", "Z", "y", "Y",
            "B", "kB", "KB", "kb", "Kb", "MB", "GB", "TB",
            "iB", "KiB", "MiB", "GiB", "TiB",
            "KIB", "kib", "ib",
        ]

        print(f"文件大小 {FILE_SIZE} 字节；每行是该后缀实测输出的字节数")
        print(f"{'后缀':<8}{'字节数':>12}   备注")
        for suffix in candidates:
            code, size, err = measure(suffix, root)
            spec = f"1{suffix}" if suffix else "1"
            if code != 0:
                print(f"{spec:<8}{'—':>12}   非法（{err.split(': ')[-1]}）")
            else:
                note = ""
                for label, value in (
                    ("512", 512), ("1000", 1000), ("1024", 1024),
                    ("1000^2", 1000**2), ("1024^2", 1024**2),
                    ("1000^3", 1000**3), ("1024^3", 1024**3),
                ):
                    if size == value:
                        note = f"= {label}"
                        break
                if size == FILE_SIZE:
                    note = "≥ 文件大小（被截断）"
                print(f"{spec:<8}{size:>12}   {note}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
