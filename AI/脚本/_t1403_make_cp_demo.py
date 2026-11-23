"""给 teach/29 教程准备演示夹具。

用法：
    python AI/脚本/_t1403_make_cp_demo.py

产出目录：AI/数据/cp_demo/（该目录在 .gitignore 里，不进版本库）

夹具内容刻意挑了三种典型：
- hello.txt  两行 CRLF 文本（能看出「按字节复制，不改换行」）
- legacy.txt GBK 编码的中文（能看出「复制不做编码转换」）
- payload.bin 0~255 全字节（能看出「二进制逐字节保真」）
- project/  三层目录树（能看出递归、合并与 --parents 的落点）

输出是固定的一串「相对路径 + 字节数」，不随 case/ 子目录里已有的内容变化，
所以教程里可以把它当预期输出照抄。
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEMO = ROOT / "AI" / "数据" / "cp_demo"

FILES: dict[str, bytes] = {
    "hello.txt": b"hello cp\r\nsecond line\r\n",
    "legacy.txt": ("旧内容\n中文第二行\n".encode("gb18030")),
    "payload.bin": bytes(range(256)),
    "project/src/main.py": b"print('main')\r\n",
    "project/src/util.py": b"def util():\r\n    return 1\r\n",
    "project/docs/readme.md": b"# readme\r\n",
    "project/backup/old.txt": b"old copy\r\n",
}


def main() -> int:
    DEMO.mkdir(parents=True, exist_ok=True)
    for name, data in FILES.items():
        path = DEMO / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    print(f"已生成 AI/数据/cp_demo/（{len(FILES)} 个文件）")
    for name in FILES:
        size = (DEMO / name).stat().st_size
        print(f"  {name:<26} {size:>4} 字节")
    return 0


if __name__ == "__main__":
    sys.exit(main())
