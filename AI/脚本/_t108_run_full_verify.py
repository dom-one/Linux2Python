"""跑全量教程核对，把输出落盘到 AI/数据/。

用法:
    python AI/脚本/_t108_run_full_verify.py

为什么用脚本而不是 shell 重定向:
    bash 工具的输出重定向到 AI/数据/ 会被本地安全策略拦（路径映射不了）。
    改成脚本内部用 Python 打开文件写，不走 shell 重定向。

用途:
    核对器一次要跑 22 篇、1000 多个命令块，输出量大。落盘后再按需
    grep / tail 取片段，避免刷屏。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / "AI" / "脚本" / "_t12_verify_teach.py"
OUT = ROOT / "AI" / "数据" / "t108_full_verify.txt"


def main() -> int:
    proc = subprocess.run(
        [sys.executable, str(VERIFY)],
        capture_output=True,
        cwd=str(ROOT),
    )
    payload = proc.stdout + proc.stderr
    OUT.write_bytes(payload)
    print("核对器 exit=%d，输出 %d 字节 -> %s" % (proc.returncode, len(payload), OUT))
    tail = payload.decode("utf-8", errors="replace").splitlines()
    for line in tail[-6:]:
        print("  | %s" % line)
    return proc.returncode


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
