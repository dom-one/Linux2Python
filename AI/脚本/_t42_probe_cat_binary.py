"""探针：含高位字节的二进制文件，经过本实现后字节是否还一致。

只读：仅在 AI/数据/ 下建临时文件。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "AI" / "数据"
GNU_CAT = shutil.which("cat") or r"E:\software\Git\Git\usr\bin\cat.exe"


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="_t42_bin_", dir=str(DATA)))

    cases = {
        "high.bin": b"\x80\x81\xfe\xff\n",
        "nul.bin": b"abc\x00def\n",
        "all_bytes.bin": bytes(range(256)),
    }

    for name, data in cases.items():
        target = tmp / name
        target.write_bytes(data)
        gnu = subprocess.run([GNU_CAT, str(target)], capture_output=True).stdout
        ours = subprocess.run(
            [sys.executable, str(ROOT / "main.py"), "cat", str(target)],
            capture_output=True,
        ).stdout
        flag = "SAME" if gnu == ours else "DIFF"
        print("%s %-14s in=%d bytes gnu=%d ours=%d" % (flag, name, len(data), len(gnu), len(ours)))
        if gnu != ours:
            print("   gnu  head=%r" % gnu[:32])
            print("   ours head=%r" % ours[:32])

    print()
    print("=== -v 对高位字节是否逐字节一致 ===")
    target = tmp / "high.bin"
    for opts in (["-v"], ["-A"], ["-e"]):
        gnu = subprocess.run([GNU_CAT, *opts, str(target)], capture_output=True).stdout
        ours = subprocess.run(
            [sys.executable, str(ROOT / "main.py"), "cat", *opts, str(target)],
            capture_output=True,
        ).stdout
        flag = "SAME" if gnu == ours else "DIFF"
        print("%s opts=%-8r gnu=%r ours=%r" % (flag, opts, gnu, ours))

    for path in sorted(tmp.rglob("*"), reverse=True):
        if path.is_dir():
            os.rmdir(path)
        else:
            path.unlink()
    os.rmdir(tmp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
