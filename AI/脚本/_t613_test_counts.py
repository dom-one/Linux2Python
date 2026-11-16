"""数出每个测试文件的真实用例数，给 teach/00 的结构树用。

用法:
    python AI/脚本/_t613_test_counts.py

为什么单独写:
    结构树里写的「N 个用例」是纯数字断言，核对器不比对正文，
    得单独数一遍。数法用 pytest 自己 --collect-only 的输出。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT, capture_output=True, text=True)
    # 输出格式是 "tests/test_xxx.py: N"
    pairs = re.findall(r"(tests/[A-Za-z0-9_]+\.py):\s*(\d+)", proc.stdout)
    total = 0
    for path, count in pairs:
        print("%-28s %s" % (path, count))
        total += int(count)
    print("-" * 40)
    print("%-28s %d" % ("合计", total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
