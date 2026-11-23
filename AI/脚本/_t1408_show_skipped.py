"""列出核对器在某一篇教程里跳过（判为危险）的命令块。

用法:
    python AI/脚本/_t1408_show_skipped.py teach/29-w2l-commands-cp.py-目标落点与属性保留.md

复用核对器自己的 is_risky 判据，不另写一套口径。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from _t12_verify_teach import RISKY_PATTERNS, is_risky  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write("用法: python AI/脚本/_t1408_show_skipped.py <教程文件>\n")
        return 2
    path = Path(sys.argv[1])
    if not path.is_absolute():
        path = ROOT / path
    text = path.read_text(encoding="utf-8")

    fence = re.compile(r"```([A-Za-z]*)\n(.*?)```", re.DOTALL)
    blocks = [(m.group(1), m.group(2)) for m in fence.finditer(text)]

    count = 0
    for lang, content in blocks:
        if lang.lower() != "bash":
            continue
        count += 1
        cmd_lines = [
            ln.strip()
            for ln in content.strip().splitlines()
            if not ln.strip().lower().startswith("cd ")
        ]
        if not cmd_lines:
            continue
        payload = " && ".join(cmd_lines)
        if is_risky(payload):
            hits = [p.pattern for p in RISKY_PATTERNS if p.search(payload)]
            print(f"[块 #{count}] 被判为危险")
            print(f"  命令: {payload}")
            print(f"  命中: {hits}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
