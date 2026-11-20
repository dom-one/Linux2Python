"""跑全量教程核对，把结果落盘（bash 重定向到中文路径会被安全策略拦下，所以走 Python）。

产出：AI/数据/du_full_verify.txt

用法:
    python AI/脚本/_t916_run_full_verify.py
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

OUT = ROOT / "AI" / "数据" / "du_full_verify.txt"


def main() -> int:
    import _t12_verify_teach as verifier

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        verifier.main()
    text = buffer.getvalue()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)

    summary = [ln for ln in text.splitlines() if ln.startswith("合计")]
    for line in summary:
        print(line)
    print("明细写入: %s" % OUT)

    # 把每篇的汇总行也打出来，便于对比
    for line in text.splitlines():
        if line.startswith("合计") or ".md:" in line:
            print("  " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
