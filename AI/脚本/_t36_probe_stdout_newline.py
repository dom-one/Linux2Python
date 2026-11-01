"""探针：确认 stdout 的换行翻译行为与 reconfigure(newline="") 的效果。

用法:
    python _t36_probe_stdout_newline.py          # 作为父进程，跑对照
    python _t36_probe_stdout_newline.py plain    # 作为子进程，写 A\\nB\\n
    python _t36_probe_stdout_newline.py reconf   # 子进程，先关掉换行翻译
"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "_t36_probe_stdout_newline.py"


def run_child(mode: str) -> None:
    """子进程入口：按 mode 决定要不要关掉换行翻译。"""
    if mode == "reconf":
        sys.stdout.reconfigure(newline="")
    sys.stdout.write("A\nB\n")
    sys.stdout.flush()


def main() -> int:
    print("isatty(stdout):", sys.stdout.isatty())
    print()

    for mode in ("plain", "reconf"):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), mode],
            capture_output=True,
            stdin=subprocess.DEVNULL,
        )
        print("mode=%-8s stdout bytes=%r stderr=%r" % (mode, proc.stdout, proc.stderr[:200]))
    print()

    buf = io.BytesIO()
    print("BytesIO write repr:", repr(buf.getvalue()))
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_child(sys.argv[1])
    else:
        sys.exit(main())
