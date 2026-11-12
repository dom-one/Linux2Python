"""调用 _t11_progress.py 追加 tick 日志，参数从 JSON 载荷里读。

命令行参数太长，直接在 bash 里拼容易写坏引号。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PAYLOAD = HERE / "_t124_du_tick_payload.json"
PROGRESS = ROOT / "AI" / "阅读进度.md"


def main() -> int:
    data = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    cmd = [
        sys.executable,
        str(HERE / "_t11_progress.py"),
        "--进度",
        str(PROGRESS),
    ]
    for key in ("主题", "理由", "产出", "收获", "负面", "剩余"):
        cmd.extend([f"--{key}", data.get(key, "")])
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8")
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
