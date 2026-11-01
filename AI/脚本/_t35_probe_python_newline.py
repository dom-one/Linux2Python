"""探针：确认 Python 在 Windows 上的换行翻译行为与 StringIO 能力。

只读：不修改仓库源码。
"""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path


def main() -> int:
    print("python:", sys.version)
    print("stdout newline attr:", repr(getattr(sys.stdout, "newlines", None)))
    print("stdout has reconfigure:", hasattr(sys.stdout, "reconfigure"))
    print("StringIO has reconfigure:", hasattr(io.StringIO(), "reconfigure"))

    buf = io.StringIO()
    buf.write("a\nb\n")
    print("StringIO default write repr:", repr(buf.getvalue()))

    buf2 = io.StringIO(newline="")
    buf2.write("a\nb\n")
    print("StringIO newline='' write repr:", repr(buf2.getvalue()))

    if hasattr(io.StringIO(), "reconfigure"):
        buf3 = io.StringIO()
        try:
            buf3.reconfigure(newline="")
            buf3.write("x\ny\n")
            print("StringIO reconfigure(newline='') repr:", repr(buf3.getvalue()))
        except Exception as exc:  # noqa: BLE001
            print("StringIO reconfigure failed:", type(exc).__name__, exc)

    # 真文件：写文本时是否翻译换行
    tmp = Path(tempfile.mkdtemp(prefix="_t35_txt_"))
    target = tmp / "out.txt"
    with open(target, "w", encoding="utf-8", newline="") as handle:
        handle.write("a\nb\n")
    print("file newline='' bytes:", target.read_bytes())
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("a\nb\n")
    print("file default  bytes:", target.read_bytes())

    target.unlink()
    tmp.rmdir()
    return 0


if __name__ == "__main__":
    sys.exit(main())
