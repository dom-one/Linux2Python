"""探针第九轮：把有争议的几个后缀的原始 stderr 打出来。

第八轮用「文件不存在」区分非法/溢出，第九轮直接看原文，
确认 1Z / 1Y / 1ZB 到底是语法非法还是数值溢出。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

GNU_HEAD = r"C:\Program Files\Git\usr\bin\head.exe"


def locate_head() -> str:
    candidate = shutil.which("head")
    if candidate and "System32" not in candidate:
        return candidate
    return GNU_HEAD


def raw(spec: str, cwd: Path, file: str) -> str:
    proc = subprocess.run(
        [locate_head(), "-c", spec, file],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.stderr.decode("utf-8", "replace").strip() or "(无 stderr)"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(tempfile.mkdtemp(prefix="probe_head9_"))
    try:
        (root / "big.bin").write_bytes(b"X" * 3000)

        print("--- 文件存在时")
        for spec in ["1Z", "1z", "1Y", "1y", "1ZB", "1YB", "1E", "1EB", "1EiB", "1ZiB", "1g", "1c"]:
            print(f"  -c {spec:<6} {raw(spec, root, 'big.bin')}")

        print("--- 文件不存在时")
        for spec in ["1Z", "1z", "1Y", "1ZB", "1EB", "1EiB"]:
            print(f"  -c {spec:<6} {raw(spec, root, 'missing.bin')}")

        print("--- 最大合法值附近")
        for spec in ["9223372036854775807", "9223372036854775808", "99999999999999999999999"]:
            print(f"  -c {spec:<24} {raw(spec, root, 'big.bin')}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
