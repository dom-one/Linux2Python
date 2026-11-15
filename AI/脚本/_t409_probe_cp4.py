"""探针 4：-T 与 -t 的多源组合，以及 --parents 绝对路径的落点。"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "cp_probe"

CP = shutil.which("cp")
if CP is None:
    raise SystemExit("本机找不到 cp 可执行文件")


def build(tmp: Path) -> None:
    (tmp / "a.txt").write_bytes(b"a\r\n")
    (tmp / "b.txt").write_bytes(b"b\r\n")
    (tmp / "c.txt").write_bytes(b"c\r\n")
    (tmp / "d").mkdir()
    (tmp / "d" / "x.txt").write_bytes(b"x\r\n")


def run(argv: list[str], cwd: Path) -> dict:
    proc = subprocess.run(
        [CP, *argv], cwd=str(cwd),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return {
        "argv": argv,
        "rc": proc.returncode,
        "out": proc.stdout.decode("utf-8", "replace"),
        "err": proc.stderr.decode("utf-8", "replace"),
    }


CASES = [
    ["-T", "a.txt", "b.txt", "c.txt"],
    ["-T", "a.txt", "b.txt"],
    ["-t", "d", "a.txt", "b.txt"],
    ["-t", "a.txt", "a.txt"],
    ["-t", "d", "d"],
    ["--parents", "d/x.txt", "d2"],
    ["-a", "-v", "d", "d2"],
    ["-i", "-n", "a.txt", "b.txt"],
]


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    report = []
    for argv in CASES:
        tmp = Path(tempfile.mkdtemp(prefix="cpprobe4_", dir=str(DATA)))
        build(tmp)
        r = run(argv, tmp)
        after = sorted(
            p.relative_to(tmp).as_posix() + ("" if p.is_dir() else f" {p.read_bytes()!r}")
            for p in tmp.rglob("*")
        )
        report.append({**r, "after": after})
        print("=" * 66)
        print("ARGV:", " ".join(argv))
        print("RC  :", r["rc"])
        if r["out"]:
            print("OUT :", repr(r["out"]))
        if r["err"]:
            print("ERR :", repr(r["err"]))
        print("TREE:", after)

    (DATA / "probe_cp4.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
