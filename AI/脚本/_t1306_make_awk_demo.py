#!/usr/bin/env python
"""给 teach/28 教程准备演示夹具。

用法：
    python AI/脚本/_t1306_make_awk_demo.py

产出目录：AI/数据/awk_demo/（该目录在 .gitignore 里，不进版本库）
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEMO = ROOT / "AI" / "数据" / "awk_demo"

FILES: dict[str, bytes] = {
    "app.log": (
        b"INFO start app\n"
        b"ERROR failed db\n"
        b"warn  retry queue\n"
        b"ERROR again db\n"
    ),
    "two.log": b"INFO second file\nERROR tail error\n",
    "access.csv": (
        b"10.0.0.1,GET,200,1024\n"
        b"10.0.0.2,POST,404,256\n"
        b"10.0.0.3,GET,200,4096\n"
    ),
    "semi.log": b"a;b;c\nd;e;f\n",
    "gap.log": b"a;;c\n",
    "multi.txt": b"aXXbXXc\n",
    "blank.log": b"\n\nx y\n",
    "nonl.log": b"one two",
    "gbk.log": "INFO \u5f00\u59cb\nERROR \u5931\u8d25\n".encode("gb18030"),
}


def main() -> int:
    DEMO.mkdir(parents=True, exist_ok=True)
    for name, data in FILES.items():
        (DEMO / name).write_bytes(data)
    for name in FILES:
        path = DEMO / name
        print(f"{name:<12} {len(path.read_bytes()):>5} 字节")
    return 0


if __name__ == "__main__":
    sys.exit(main())
