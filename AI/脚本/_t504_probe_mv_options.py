"""探针四：确认 mv 的选项交互细节。

- -S 单独给会不会隐含开备份
- -n 与 -i 同时给，谁压过谁
- -u 与 -i 同时给，-u 会不会先挡掉提示
- -i 提示的落点（标准错误）与回车以外的应答
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "mv_probe"

GNU_MV = shutil.which("mv")
OLD = 1_000_000_000
NEW = 2_000_000_000


def fixture(root: Path) -> None:
    (root / "a.txt").write_bytes(b"hello mv\r\n")
    (root / "b.txt").write_bytes(b"old content\r\n")


def tree(root: Path) -> dict:
    return {
        p.relative_to(root).as_posix(): ("DIR" if p.is_dir() else f"FILE {p.stat().st_size}")
        for p in sorted(root.rglob("*"))
    }


CASES = [
    ("suffix-only", ["-S", ".bak", "a.txt", "b.txt"], None),
    ("noclobber-and-interactive", ["-n", "-i", "a.txt", "b.txt"], "y\n"),
    ("interactive-and-noclobber", ["-i", "-n", "a.txt", "b.txt"], "y\n"),
    ("update-and-interactive", ["-u", "-i", "b.txt", "a.txt"], "y\n"),
    ("interactive-empty-answer", ["-i", "a.txt", "b.txt"], "\n"),
    ("interactive-garbage-answer", ["-i", "a.txt", "b.txt"], "zzz\n"),
    ("interactive-EOF", ["-i", "a.txt", "b.txt"], ""),
    ("interactive-YES", ["-i", "a.txt", "b.txt"], "YES\n"),
]


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    sandbox_root = Path(tempfile.mkdtemp(prefix="mvprobe4_", dir=str(DATA)))

    report = []
    for index, (name, argv, stdin_text) in enumerate(CASES):
        base = sandbox_root / f"case{index:03d}"
        base.mkdir(parents=True)
        sandbox = base / "s"
        sandbox.mkdir()
        fixture(sandbox)
        # b.txt 比 a.txt 新：让 -u 的判定有明确方向
        import os

        os.utime(sandbox / "a.txt", (OLD, OLD))
        os.utime(sandbox / "b.txt", (NEW, NEW))

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
            "stdin": stdin_text,
            "rc": proc.returncode,
            "out": proc.stdout.decode("utf-8", "replace"),
            "err": proc.stderr.decode("utf-8", "replace"),
            "tree": tree(sandbox),
        }
        report.append(row)
        print("=" * 70)
        print(f"[{name}] argv={' '.join(argv)} stdin={stdin_text!r}")
        print(f"  rc  = {row['rc']}")
        print(f"  out = {row['out']!r}")
        print(f"  err = {row['err']!r}")
        for key, value in row["tree"].items():
            print(f"    {key}  ->  {value}")

    out_path = DATA / "probe_mv_options.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=" * 70)
    print("详细结果:", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
