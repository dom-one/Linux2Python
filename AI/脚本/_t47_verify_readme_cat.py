"""核对 README 里 cat 章节的示例命令是否真能跑通。

只读：不修改仓库源码。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CASES = [
    ["cat", "w2l/cli.py"],
    ["cat", "-n", "w2l/registry.py"],
    ["cat", "-b", "w2l/registry.py"],
    ["cat", "-E", "w2l/registry.py"],
    ["cat", "-e", "w2l/registry.py"],
    ["cat", "-T", "w2l/registry.py"],
    ["cat", "-t", "w2l/registry.py"],
    ["cat", "-s", "w2l/registry.py"],
    ["cat", "-v", "w2l/registry.py"],
    ["cat", "-A", "w2l/registry.py"],
    ["cat", "-u", "w2l/registry.py"],
    ["cat", "README.md", "AGENTS.md"],
    ["cat"],
]


def main() -> int:
    failures = 0
    for argv in CASES:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "main.py"), *argv],
            cwd=str(ROOT),
            capture_output=True,
            stdin=subprocess.DEVNULL,
        )
        ok = proc.returncode == 0 and proc.stderr == b""
        if not ok:
            failures += 1
        print("%s %-46s code=%d stderr=%r" % (
            "OK  " if ok else "FAIL",
            " ".join(argv),
            proc.returncode,
            proc.stderr[:100],
        ))

    print()
    print("failures=%d" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
