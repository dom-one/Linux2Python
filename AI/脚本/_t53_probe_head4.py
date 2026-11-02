"""探针第四轮：精确量出乘数后缀的字节数，并补齐几个语法形式。

用输出长度而不是肉眼数 X 的个数。
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


def locate_head() -> str:
    candidate = shutil.which("head")
    if candidate and "System32" not in candidate:
        return candidate
    return GNU_HEAD


def run(args: list[str], cwd: Path, stdin: bytes = b"") -> tuple[int, bytes, bytes]:
    proc = subprocess.run(
        [locate_head(), *args],
        cwd=str(cwd),
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.returncode, proc.stdout, proc.stderr


def measure(title: str, args: list[str], cwd: Path, stdin: bytes = b"") -> None:
    code, out, err = run(args, cwd, stdin)
    print(f"--- {title}")
    print(f"    argv   : head {' '.join(args)}")
    print(f"    exit   : {code}  stdout 长度: {len(out)}")
    if err:
        print(f"    stderr : {err!r}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    DATA.mkdir(parents=True, exist_ok=True)

    root = Path(tempfile.mkdtemp(prefix="probe_head4_"))
    try:
        (root / "big.bin").write_bytes(b"X" * 5000)
        (root / "lf.txt").write_bytes(b"l1\nl2\nl3\nl4\nl5\n")
        (root / "one.txt").write_bytes(b"only\n")

        print("=" * 70)
        print("Z. 乘数后缀精确字节数（文件 5000 字节）")
        for spec in ("1", "1b", "1k", "1K", "1kB", "1KB", "1KiB", "1M", "1MB", "1MiB"):
            measure(f"-c {spec}", ["-c", spec, "big.bin"], root)
        print("  预期: b=512 k/kB=1000 K/KiB=1024 kB=1000 KB=1000000 M/MiB=1048576")

        print("=" * 70)
        print("AA. -n 是否也接受后缀")
        measure("-n 1k（文件只有 5 行）", ["-n", "1k", "lf.txt"], root)
        measure("-n 2（对照）", ["-n", "2", "lf.txt"], root)

        print("=" * 70)
        print("BB. 语法形式")
        measure("-n-2 贴着写", ["-n-2", "lf.txt"], root)
        measure("-c-2 贴着写", ["-c-2", "lf.txt"], root)
        measure("--lines=-2", ["--lines=-2", "lf.txt"], root)
        measure("-- -n 当文件名", ["--", "-n"], root)
        measure("-- -2 当文件名", ["--", "-2"], root)
        measure("-n2 贴着写", ["-n2", "lf.txt"], root)
        measure("-2 紧凑写法", ["-2", "lf.txt"], root)
        measure("-0 紧凑写法", ["-0", "lf.txt"], root)

        print("=" * 70)
        print("CC. 错误措辞（Windows 路径不存在）")
        measure("不存在文件", ["missing.txt"], root)
        measure("空文件名", [""], root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
