"""核对 -e 的输出与 GNU cat 是否逐字节一致。

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
    tmp = Path(tempfile.mkdtemp(prefix="_t41_e_", dir=str(DATA)))
    target = tmp / "ctrl.txt"
    target.write_bytes(b"bell\x07 del\x7f esc\x1b\n")

    for opts in (["-e"], ["-E"], ["-v"], ["-A"], ["-vE"], ["-t"], ["-T"]):
        gnu = subprocess.run([GNU_CAT, *opts, str(target)], capture_output=True).stdout
        ours = subprocess.run(
            [sys.executable, str(ROOT / "main.py"), "cat", *opts, str(target)],
            capture_output=True,
        ).stdout
        flag = "OK " if gnu == ours else "DIFF"
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
