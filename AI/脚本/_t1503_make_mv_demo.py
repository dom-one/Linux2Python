"""给 teach/30 教程准备演示夹具。

用法：
    python AI/脚本/_t1503_make_mv_demo.py

产出目录：AI/数据/mv_demo/（该目录在 .gitignore 里，不进版本库）

夹具内容刻意挑了四种典型：
- a.txt       两行 CRLF 文本（能看出「按字节搬，不改换行」）
- b.txt       已存在的目标（覆盖、-n、-u、-b 都拿它当靶子）
- legacy.txt  GBK 编码的中文（能看出「mv 不做编码转换」）
- payload.bin 0~255 全字节（能看出「二进制逐字节保真」）
- dir1/       两层目录树（能看出「目录整体改名」与「目录不合并」）
- destdir/    已存在的目标目录（能看出「落点是目录/源名」）
- emptydir/   空目录（能看出「同名空目录可以被替换掉」）

时间戳钉死：old.txt 钉在 2019-01-01、future.txt 钉在 2030-01-01、
源钉在 2020-01-01，都是 UTC。`-u` 的两种走向就靠这个。

mv 是破坏性操作，所以每个案例目录由 _t1504_prep_mv_case.py 单独重建。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEMO = ROOT / "AI" / "数据" / "mv_demo"

T_OLD = 1546300800      # 2019-01-01 00:00:00 UTC
T_SRC = 1577836800      # 2020-01-01 00:00:00 UTC
T_FUTURE = 1893456000   # 2030-01-01 00:00:00 UTC

FILES: dict[str, bytes] = {
    "a.txt": b"hello mv\r\nsecond line\r\n",
    "b.txt": b"old content\r\n",
    "legacy.txt": ("旧内容\n中文第二行\n".encode("gb18030")),
    "payload.bin": bytes(range(256)),
    "dir1/inner.txt": b"inner\r\n",
    "dir1/sub/deep.txt": b"deep\r\n",
    "destdir/b.txt": b"existing in destdir\r\n",
}

# 空目录：建的时候要有个占位文件（Path.mkdir 建不出空目录的父级），
# 建完立刻删掉，留下的才是真正的空目录。
EMPTY_DIR = "emptydir"


def build(root: Path) -> None:
    for name, data in FILES.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    # 空目录：先建占位文件再删掉，留下的才是真正的空目录
    empty = root / EMPTY_DIR
    empty.mkdir(parents=True, exist_ok=True)
    placeholder = empty / ".keep"
    placeholder.write_bytes(b"")
    placeholder.unlink()
    (root / "old.txt").write_bytes(b"older\r\n")
    (root / "future.txt").write_bytes(b"newer\r\n")


def pin(root: Path) -> None:
    for name, stamp in (
        ("old.txt", T_OLD),
        ("future.txt", T_FUTURE),
        ("a.txt", T_SRC),
        ("b.txt", T_SRC),
    ):
        os.utime(root / name, (stamp, stamp))


def main() -> int:
    DEMO.mkdir(parents=True, exist_ok=True)
    build(DEMO)
    pin(DEMO)
    print(f"已生成 AI/数据/mv_demo/（{len(FILES) + 3} 个文件）")
    print("mv_demo/ 下的内容：")
    # 只列夹具自己的那几项，不递归进 case/（那是每一步的现场目录，
    # 内容随步骤变，列出来会让预期输出过期）
    for name in sorted(list(FILES) + [EMPTY_DIR, "old.txt", "future.txt"]):
        path = DEMO / name
        if path.is_dir():
            print(f"  {name}/")
        else:
            print(f"  {name}  ({path.stat().st_size} 字节)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
