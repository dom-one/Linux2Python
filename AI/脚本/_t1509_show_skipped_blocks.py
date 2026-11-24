"""列出核对器跳过的是哪几个命令块（核对器本身不打印跳过明细）。

用法:
    python AI/脚本/_t1509_show_skipped_blocks.py [教程路径]

做法: 直接复用核对器的 is_risky() 判据，把每个 bash 块与命中的危险模式
打印出来。为什么需要单独一个脚本: 核对器只报「跳过 N 个」，
不说是哪几个——教程里如果有个块其实不危险却被跳了，就永远查不出来。
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

VERIFIER = HERE / "_t12_verify_teach.py"


def load_verifier():
    spec = importlib.util.spec_from_file_location("_t12_verify_teach", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str]) -> int:
    if argv:
        target = Path(argv[0])
        if not target.is_absolute():
            target = ROOT / argv[0]
    else:
        target = ROOT / "teach" / "30-w2l-commands-mv.py-落点判定与覆盖策略.md"

    v = load_verifier()
    text = target.read_text(encoding="utf-8")

    fence = re.compile(r"```([A-Za-z]*)\n(.*?)```", re.DOTALL)
    blocks = [(m.group(1), m.group(2)) for m in fence.finditer(text)]

    bash_index = 0
    for lang, content in blocks:
        if lang.lower() != "bash":
            continue
        bash_index += 1
        cmd_lines = [
            ln for ln in content.strip().splitlines()
            if not ln.strip().lower().startswith("cd ")
        ]
        if not cmd_lines:
            continue
        payload = " && ".join(ln.strip() for ln in cmd_lines)
        hits = [p.pattern for p in v.RISKY_PATTERNS if p.search(payload)]
        repl = [seg.strip() for seg in v.SEGMENT_SPLIT.split(payload)
                if v.REPL_ONLY.match(seg.strip())]
        if hits or repl:
            print(f"块 #{bash_index}: 命中危险模式 {hits}"
                  + (f" 裸 python 段 {repl}" if repl else ""))
            print(f"    {payload[:120]}")
        else:
            print(f"块 #{bash_index}: 不危险（会真跑）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
