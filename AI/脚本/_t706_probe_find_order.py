"""检查夹具重建后 find 的遍历顺序是否稳定。

用法:
    python AI/脚本/_t706_probe_find_order.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
MAIN = Path(ROOT) / "main.py"
DEMO_REL = "AI/数据/find_demo"
GEN = Path(ROOT) / "AI" / "脚本" / "_t700_make_find_demo.py"


def run_find(args):
    p = subprocess.run(
        [sys.executable, str(MAIN), "find"] + args,
        cwd=str(ROOT),
        capture_output=True,
    )
    return p.stdout.decode("utf-8", "replace").splitlines()


def main() -> None:
    orders = []
    for round_no in range(3):
        subprocess.run([sys.executable, str(GEN)], cwd=str(ROOT), capture_output=True)
        orders.append(run_find([DEMO_REL, "-print"]))

    same = all(o == orders[0] for o in orders)
    print(f"重建 {len(orders)} 次，遍历顺序一致：{'是' if same else '否'}")
    for i, order in enumerate(orders):
        print(f"--- 第 {i + 1} 次 ---")
        for line in order:
            print(f"  {line}")


if __name__ == "__main__":
    main()
