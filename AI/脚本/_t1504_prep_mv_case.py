"""给 teach/30 教程的每个步骤单独重建现场。

用法：
    python AI/脚本/_t1504_prep_mv_case.py <案例名>

mv 是破坏性操作：一步跑完文件就搬走了，同一个案例没法跑第二遍。
所以每一步的演示命令前面都要先跑这个脚本重建现场。

案例名决定额外的预置内容（见 EXTRA 字典）。现场建在
AI/数据/mv_demo/case/<案例名>/ 下，跑完可以整目录删掉重来。
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEMO = ROOT / "AI" / "数据" / "mv_demo"
CASE_ROOT = DEMO / "case"

T_OLD = 1546300800      # 2019-01-01 00:00:00 UTC
T_SRC = 1577836800      # 2020-01-01 00:00:00 UTC
T_FUTURE = 1893456000   # 2030-01-01 00:00:00 UTC

BASE_FILES: dict[str, bytes] = {
    "a.txt": b"hello mv\r\nsecond line\r\n",
    "b.txt": b"old content\r\n",
    "legacy.txt": ("旧内容\n中文第二行\n".encode("gb18030")),
    "payload.bin": bytes(range(256)),
    "dir1/inner.txt": b"inner\r\n",
    "dir1/sub/deep.txt": b"deep\r\n",
    "destdir/b.txt": b"existing in destdir\r\n",
    "old.txt": b"older\r\n",
    "future.txt": b"newer\r\n",
}


def build(root: Path) -> None:
    for name, data in BASE_FILES.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (root / "emptydir").mkdir(parents=True, exist_ok=True)


def pin(root: Path) -> None:
    for name, stamp in (
        ("old.txt", T_OLD),
        ("future.txt", T_FUTURE),
        ("a.txt", T_SRC),
        ("b.txt", T_SRC),
    ):
        os.utime(root / name, (stamp, stamp))


def extra_backup_dir(root: Path) -> None:
    """b.txt~ 已存在且是个目录（带内容）。"""
    backup = root / "b.txt~"
    backup.mkdir(parents=True, exist_ok=True)
    (backup / "inside.txt").write_bytes(b"inside backup\r\n")


def extra_destdir_dir1_nonempty(root: Path) -> None:
    """destdir/dir1 已存在且非空。"""
    target = root / "destdir" / "dir1"
    target.mkdir(parents=True, exist_ok=True)
    (target / "inner.txt").write_bytes(b"OLD inner\r\n")
    (target / "stale.txt").write_bytes(b"stale\r\n")


def extra_destdir_dir1_empty(root: Path) -> None:
    """destdir/dir1 已存在但是空的。"""
    (root / "destdir" / "dir1").mkdir(parents=True, exist_ok=True)


def extra_backup_file(root: Path) -> None:
    """b.txt~ 已存在且是个文件。"""
    (root / "b.txt~").write_bytes(b"stale backup\r\n")


def extra_readonly_b(root: Path) -> None:
    """b.txt 是只读的。"""
    (root / "b.txt").chmod(0o444)


EXTRA = {
    "backup-dir": extra_backup_dir,
    "destdir-dir1-nonempty": extra_destdir_dir1_nonempty,
    "destdir-dir1-empty": extra_destdir_dir1_empty,
    "backup-file": extra_backup_file,
    "readonly-b": extra_readonly_b,
}


def _force_writable(root: Path) -> None:
    """去掉整棵树的只读属性，否则 Windows 上 rmtree 删不掉。"""
    import stat

    for path in [root, *root.rglob("*")]:
        try:
            os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
        except OSError:
            pass


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("用法: python AI/脚本/_t1504_prep_mv_case.py <案例名>", file=sys.stderr)
        return 2
    name = argv[0]
    target = CASE_ROOT / name
    if target.exists():
        # 上一轮可能留下只读文件，Windows 上 shutil.rmtree 删不掉只读文件，
        # 会抛 PermissionError。先把整棵树的只读属性去掉再删。
        _force_writable(target)
        shutil.rmtree(target)
    target.mkdir(parents=True)
    build(target)
    for key, fn in EXTRA.items():
        if key in name:
            fn(target)
    pin(target)
    # 刻意不打印任何东西：教程里这个脚本与 mv 命令写在同一个围栏块里，
    # 核对器会把块内所有行用 && 串成一条命令，脚本的输出会混进预期输出。
    # （teach/29 的 _t1405_prep_cp_case.py 也是这么做的。）
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
