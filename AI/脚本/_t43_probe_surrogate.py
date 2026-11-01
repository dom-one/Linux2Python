"""探针：surrogateescape 能否在 UTF-8 输出流里保住二进制字节。

只读：不修改仓库源码。
"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "_t43_probe_surrogate_child.py"


def child() -> None:
    data = bytes(range(256))
    text = data.decode("utf-8", errors="surrogateescape")
    sys.stdout.reconfigure(encoding="utf-8", errors="surrogateescape", newline="")
    sys.stdout.write(text)
    sys.stdout.flush()


def main() -> int:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    expected = bytes(range(256))
    print("stdout len=%d expected len=%d" % (len(proc.stdout), len(expected)))
    print("byte-identical:", proc.stdout == expected)
    print("stderr: %r" % proc.stderr[:200])
    print()

    # 纯内存验证
    text = expected.decode("utf-8", errors="surrogateescape")
    back = text.encode("utf-8", errors="surrogateescape")
    print("in-memory roundtrip:", back == expected)
    print()

    # 混合：合法 UTF-8 中文 + 无效字节
    mixed = "中文内容\n".encode("utf-8") + b"\x80\xff\n"
    t2 = mixed.decode("utf-8", errors="surrogateescape")
    b2 = t2.encode("utf-8", errors="surrogateescape")
    print("mixed roundtrip:", b2 == mixed)
    print("mixed repr:", repr(t2))
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        child()
    else:
        sys.exit(main())
