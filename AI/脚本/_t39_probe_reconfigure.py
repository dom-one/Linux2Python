"""探针：reconfigure(newline="") 是否会动到已有的 encoding/errors 设置。

只读：不修改仓库源码。
"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "_t39_probe_reconfigure.py"


def child() -> None:
    # 先按仓库 cli.py 的方式设置编码，再只改 newline
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(newline="")
    sys.stdout.write("中文\r\nend\n")
    sys.stdout.flush()


def main() -> int:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "child"],
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    print("stdout bytes: %r" % proc.stdout)
    print("stderr: %r" % proc.stderr[:200])
    print("expect: b'\\xe4\\xb8\\xad\\xe6\\x96\\x87\\r\\nend\\n' (编码 utf-8, 换行不翻译)")
    print()

    # StringIO 是否有 reconfigure
    print("StringIO has reconfigure:", hasattr(io.StringIO(), "reconfigure"))
    print()

    # 只改 newline 时 encoding 是否保留：直接读 sys.stdout.encoding
    code = (
        "import sys\n"
        "sys.stdout.reconfigure(encoding='utf-8', errors='replace')\n"
        "sys.stdout.reconfigure(newline='')\n"
        "sys.stdout.write(sys.stdout.encoding + '|' + sys.stdout.errors + '|' + repr(sys.stdout.newlines) + '\\n')\n"
    )
    proc2 = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    print("encoding after reconfigure:", proc2.stdout)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        child()
    else:
        sys.exit(main())