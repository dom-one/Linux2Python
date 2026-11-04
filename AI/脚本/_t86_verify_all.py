"""跑全量核对，把汇总结果落到 AI/数据/ 下的文件里。

Git Bash 没法把 AI/数据/ 这个被 gitignore 的路径映射成可写目标，
所以走 Python 子进程跑核对器，再由 Python 写文件。

跑法：
    python AI/脚本/_t86_verify_all.py
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "数据", "_t86_verify_all.txt")


def main() -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, "AI", "脚本", "_t12_verify_teach.py")],
        cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=2400,
    )
    text = proc.stdout + proc.stderr
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)

    # 只打前 30 行（每篇一行汇总 + 分隔线），够看清全貌
    lines = text.splitlines()
    for line in lines[:30]:
        print(line)
    print("")
    print("完整输出: %s （%d 行）" % (OUT, len(lines)))
    print("返回码: %s" % proc.returncode)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
