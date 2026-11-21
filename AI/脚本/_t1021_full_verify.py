"""跑全量 teach 核对，把输出落盘，并打印汇总行。

为什么落盘：全量核对要跑七八分钟，bash 工具的后台输出只留尾部，
汇总行（「合计: 命令块 N，有预期 K，不匹配 J」）正好被吃掉。
落盘后回读最前面几行就能拿到。

用法：python AI/脚本/_t1021_full_verify.py
产物：AI/数据/full_verify.txt
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "full_verify.txt"


def main() -> int:
    proc = subprocess.run(
        [sys.executable, str(HERE / "_t12_verify_teach.py")],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    text = proc.stdout.decode("utf-8", "replace")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print("[result] 已写入 %s" % OUT)

    lines = text.splitlines()
    print("--- 每篇统计 ---")
    for line in lines:
        if line.startswith("合计:"):
            print(line)
    print("--- 不匹配的篇目 ---")
    for line in lines:
        if line.endswith("不匹配 0"):
            continue
        if "命令块" in line and "不匹配" in line:
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
