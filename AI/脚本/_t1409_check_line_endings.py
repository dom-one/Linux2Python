"""检查本轮改动过的文件里有没有 CRLF。

用法:
    python AI/脚本/_t1409_check_line_endings.py <文件> [...]

背景：Windows 上 open(..., "w") 默认把 \n 翻译成 \r\n。teach/ 下各篇都是 LF，
混进 CRLF 会让 git diff 显示整篇被重写。写盘后必须查一遍。
"""

from __future__ import annotations

import sys
from pathlib import Path


def check(path: Path) -> tuple[bool, int, int]:
    raw = path.read_bytes()
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    return crlf == 0, crlf, lf


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write("用法: python AI/脚本/_t1409_check_line_endings.py <文件> [...]\n")
        return 2
    bad = 0
    for raw in sys.argv[1:]:
        path = Path(raw)
        if not path.exists():
            print(f"{raw}  <不存在>")
            bad += 1
            continue
        ok, crlf, lf = check(path)
        flag = "LF  " if ok else "CRLF"
        print(f"{flag}  {raw}  CRLF {crlf} 行 / LF {lf} 行")
        if not ok:
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
