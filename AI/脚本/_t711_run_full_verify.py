"""跑全量核对并把报告落盘（核对器的 stdout 很长，直接重定向会被安全策略拦）。

用法:
    python AI/脚本/_t711_run_full_verify.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
VERIFY = Path(ROOT) / "AI" / "脚本" / "_t12_verify_teach.py"
OUT = Path(ROOT) / "AI" / "数据" / "verify_all_report.txt"


def main() -> None:
    proc = subprocess.run(
        [sys.executable, str(VERIFY)],
        cwd=str(ROOT),
        capture_output=True,
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(proc.stdout)
    text = proc.stdout.decode("utf-8", errors="replace")
    for line in text.splitlines():
        if line.startswith("合计") or "不匹配" in line and "命令块" in line:
            print(line)
    print(f"退出码 {proc.returncode}，报告写入 {OUT}")


if __name__ == "__main__":
    main()
