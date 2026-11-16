"""探针二：补 mv 的边界场景。

第一轮探针没覆盖到的几个关键点：
- 目标同名目录已存在但**是空**时，GNU mv 能不能落进去
- 目标同名目录已存在但是**普通文件**时，报什么
- -u 的时间戳判定（第一轮里两个文件是先后创建的，时间太近判不准）
- 目标是只读文件时能不能覆盖
- -b 备份在目录场景下怎么落
- 源目录的父目录不存在时怎么报错
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "mv_probe"

GNU_MV = shutil.which("mv")
if GNU_MV is None:
    raise SystemExit("本机找不到 GNU mv")

STAMP_OLD = 1_000_000_000
STAMP_NEW = 2_000_000_000


def base_fixture(root: Path) -> None:
    (root / "a.txt").write_bytes(b"hello mv\r\nsecond line\r\n")
    (root / "b.txt").write_bytes(b"old content\r\n")
    d = root / "dir1"
    d.mkdir()
    (d / "inner.txt").write_bytes(b"inner\r\n")
    dest = root / "destdir"
    dest.mkdir()
    (dest / "b.txt").write_bytes(b"existing in destdir\r\n")


def tree_state(root: Path) -> dict:
    state: dict = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            state[rel] = "DIR"
        else:
            state[rel] = f"FILE {path.stat().st_size}"
    return state


# 名字, argv, stdin, 预置动作
CASES = [
    ("dest-subdir-empty", ["dir1", "destdir"], None, "empty_subdir"),
    ("dest-subdir-file", ["dir1", "destdir"], None, "file_subdir"),
    ("update-src-older", ["-u", "a.txt", "b.txt"], None, "stamps_old_new"),
    ("update-src-newer", ["-u", "b.txt", "a.txt"], None, "stamps_old_new"),
    ("update-same-mtime", ["-u", "a.txt", "b.txt"], None, "stamps_same"),
    ("readonly-dest", ["a.txt", "b.txt"], None, "readonly_dest"),
    ("readonly-dest-force", ["-f", "a.txt", "b.txt"], None, "readonly_dest"),
    ("backup-onto-dir", ["-b", "dir1", "destdir"], None, "empty_subdir"),
    ("backup-verbose", ["-b", "-v", "a.txt", "b.txt"], None, "plain"),
    ("src-parent-missing", ["nodir/a.txt", "copy.txt"], None, "plain"),
    ("dest-parent-missing-dir", ["dir1", "nodir/out"], None, "plain"),
    ("verbose-dir-into-dir", ["-v", "dir1", "destdir"], None, "empty_subdir"),
    ("interactive-dir-merge", ["-i", "dir1", "destdir"], "y\n", "empty_subdir"),
    ("noclobber-verbose", ["-n", "-v", "a.txt", "b.txt"], None, "plain"),
    ("hardlink-same", ["a.txt", "hard.txt"], None, "hardlink"),
    ("move-into-self-file", ["a.txt", "a.txt"], None, "plain"),
    ("dest-is-src-dir-name", ["dir1", "dir1"], None, "plain"),
    ("two-src-one-dir-src", ["dir1", "b.txt", "destdir"], None, "plain"),
]


def prepare(root: Path, action: str) -> None:
    if action == "empty_subdir":
        (root / "destdir" / "dir1").mkdir()
    elif action == "file_subdir":
        (root / "destdir" / "dir1").write_bytes(b"i am a file\r\n")
    elif action == "stamps_old_new":
        os.utime(root / "a.txt", (STAMP_OLD, STAMP_OLD))
        os.utime(root / "b.txt", (STAMP_NEW, STAMP_NEW))
    elif action == "stamps_same":
        os.utime(root / "a.txt", (STAMP_OLD, STAMP_OLD))
        os.utime(root / "b.txt", (STAMP_OLD, STAMP_OLD))
    elif action == "readonly_dest":
        target = root / "b.txt"
        target.chmod(0o444)
    elif action == "hardlink":
        try:
            os.link(root / "a.txt", root / "hard.txt")
        except OSError:
            pass


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    sandbox_root = Path(tempfile.mkdtemp(prefix="mvprobe2_", dir=str(DATA)))

    report = []
    for index, (name, argv, stdin_text, action) in enumerate(CASES):
        base = sandbox_root / f"case{index:03d}"
        base.mkdir(parents=True)
        sandbox = base / "s"
        sandbox.mkdir()
        base_fixture(sandbox)
        prepare(sandbox, action)

        proc = subprocess.run(
            [GNU_MV, *argv],
            cwd=str(sandbox),
            input=stdin_text.encode() if stdin_text is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        row = {
            "name": name,
            "argv": argv,
            "action": action,
            "rc": proc.returncode,
            "out": proc.stdout.decode("utf-8", "replace"),
            "err": proc.stderr.decode("utf-8", "replace"),
            "tree": tree_state(sandbox),
        }
        report.append(row)
        print("=" * 70)
        print(f"[{name}] argv={' '.join(argv)} action={action}")
        print(f"  rc  = {row['rc']}")
        print(f"  out = {row['out']!r}")
        print(f"  err = {row['err']!r}")
        for key, value in row["tree"].items():
            print(f"    {key}  ->  {value}")

    out_path = DATA / "probe_mv_edges.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=" * 70)
    print("详细结果:", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
