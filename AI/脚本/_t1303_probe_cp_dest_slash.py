"""探针：给 cp 的「目标尾斜杠」与「-T/--parents/--backup 冲突」取精确的 GNU 基准。

上一支探针（_t1301）只覆盖了几个点，这里把尾斜杠的组合矩阵补全：
源是文件还是目录、目标存不存在、目标是不是文件、给不给 -r。

判定「GNU 到底怎么表现」这一步不能靠印象写，全部实跑。

用法:
    python AI/脚本/_t1303_probe_cp_dest_slash.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "cp_defect_probe"

GNU_CP = shutil.which("cp")
if GNU_CP is None:
    raise SystemExit("本机找不到 GNU cp")


def build_fixture(root: Path) -> None:
    (root / "a.txt").write_bytes(b"hello cp\r\n")
    (root / "plain.txt").write_bytes(b"plain\r\n")
    dest = root / "destdir"
    dest.mkdir()
    (dest / "keep.txt").write_bytes(b"keep\r\n")
    d = root / "dir1"
    d.mkdir()
    (d / "inner.txt").write_bytes(b"inner\r\n")


def tree_state(root: Path) -> list[str]:
    entries: list[str] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            entries.append(f"DIR  {rel}")
        else:
            entries.append(f"FILE {rel} {path.read_bytes()!r}")
    return entries


CASES: list[tuple[str, list[str]]] = [
    # 文件源 + 目标尾斜杠
    ("file-slash-missing", ["a.txt", "nosuch/"]),
    ("file-slash-existing-dir", ["a.txt", "destdir/"]),
    ("file-slash-existing-file", ["a.txt", "plain.txt/"]),
    ("file-noslash-missing", ["a.txt", "nosuch"]),
    # 目录源 + 目标尾斜杠
    ("dir-slash-missing-r", ["-r", "dir1", "nosuch/"]),
    ("dir-slash-missing-nor", ["dir1", "nosuch/"]),
    ("dir-slash-existing-dir-r", ["-r", "dir1", "destdir/"]),
    ("dir-slash-existing-dir-nor", ["dir1", "destdir/"]),
    ("dir-slash-existing-file-r", ["-r", "dir1", "plain.txt/"]),
    # 多源 + 目标尾斜杠
    ("multi-slash-existing-dir", ["a.txt", "plain.txt", "destdir/"]),
    ("multi-slash-missing", ["a.txt", "plain.txt", "nosuch/"]),
    # -T 与尾斜杠
    ("T-slash-existing-dir", ["-T", "a.txt", "destdir/"]),
    ("T-slash-missing", ["-T", "a.txt", "nosuch/"]),
    # 目标目录带斜杠时 -t 与 --parents
    ("t-slash", ["-t", "destdir/", "a.txt"]),
    ("parents-slash", ["--parents", "a.txt", "destdir/"]),
]


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    sandbox = Path(tempfile.mkdtemp(prefix="cpslash_", dir=str(DATA)))

    lines: list[str] = []
    for index, (name, argv) in enumerate(CASES):
        work = sandbox / f"case{index:03d}"
        work.mkdir()
        build_fixture(work)
        proc = subprocess.run(
            [GNU_CP, *argv],
            cwd=str(work),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out = proc.stdout.decode("utf-8", "replace")
        err = proc.stderr.decode("utf-8", "replace")
        print("=" * 72)
        print(f"[{name}] argv={' '.join(argv)}")
        print(f"  rc  = {proc.returncode}")
        print(f"  out = {out!r}")
        print(f"  err = {err!r}")
        for entry in tree_state(work):
            print(f"  tree| {entry}")
        lines.append(f"### {name}  argv={' '.join(argv)}")
        lines.append(f"  rc  = {proc.returncode}")
        lines.append(f"  out = {out!r}")
        lines.append(f"  err = {err!r}")
        for entry in tree_state(work):
            lines.append(f"  tree| {entry}")

    out_path = DATA / "gnu_dest_slash.txt"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("=" * 72)
    print(f"用例 {len(CASES)} 条，基准已写入: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
