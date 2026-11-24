"""探针：GNU 的 -i / -n 重复给出时，是「最后一次出现」赢还是「第一次」赢。

这一点决定共享辅助函数的判据：按 order.index() 取**第一次**出现的位置，
在 `-n -i -n` 这种写法上会与 GNU 不一致（GNU 是后给的那个赢）。

同时核对 GNU mv 的同一组写法（mv.py 里已有同款判据，本轮要抽成共享模块，
两边的口径必须一致）。

用法:
    python AI/脚本/_t1304_probe_cp_flag_order.py
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
GNU_MV = shutil.which("mv")


def build_fixture(root: Path) -> None:
    (root / "a.txt").write_bytes(b"hello cp\r\n")
    (root / "b.txt").write_bytes(b"old content\r\n")


def run(tool: str, argv: list[str], cwd: Path, stdin_text: str) -> dict:
    proc = subprocess.run(
        [tool, *argv],
        cwd=str(cwd),
        input=stdin_text.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "rc": proc.returncode,
        "out": proc.stdout.decode("utf-8", "replace"),
        "err": proc.stderr.decode("utf-8", "replace"),
        "b": (cwd / "b.txt").read_bytes() if (cwd / "b.txt").exists() else None,
    }


CASES: list[tuple[str, list[str]]] = [
    ("n-i-n", ["-n", "-i", "-n", "a.txt", "b.txt"]),
    ("i-n-i", ["-i", "-n", "-i", "a.txt", "b.txt"]),
    ("n-i", ["-n", "-i", "a.txt", "b.txt"]),
    ("i-n", ["-i", "-n", "a.txt", "b.txt"]),
    ("ni", ["-ni", "a.txt", "b.txt"]),
    ("in", ["-in", "a.txt", "b.txt"]),
    ("n-i-S", ["-n", "-i", "-S", ".bak", "a.txt", "b.txt"]),
    ("i-n-S", ["-i", "-n", "-S", ".bak", "a.txt", "b.txt"]),
]


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    sandbox = Path(tempfile.mkdtemp(prefix="cpflag_", dir=str(DATA)))

    lines: list[str] = []
    for tool_name, tool in (("cp", GNU_CP), ("mv", GNU_MV)):
        for index, (name, argv) in enumerate(CASES):
            work = sandbox / f"{tool_name}{index:03d}"
            work.mkdir()
            build_fixture(work)
            result = run(tool, argv, work, "y\n")
            # b.txt 变了 = 搬/拷过去了；没变 = 被跳过或没搬
            verdict = "搬了" if result["b"] == b"hello cp\r\n" else "没搬"
            prompt = "提示了" if "overwrite" in result["err"] else "没提示"
            print(
                f"[{tool_name} {name:8}] rc={result['rc']} {verdict} {prompt} "
                f"err={result['err'].strip()[:90]!r}"
            )
            lines.append(
                f"### {tool_name} {name}  argv={' '.join(argv)}\n"
                f"  rc  = {result['rc']}\n"
                f"  err = {result['err']!r}\n"
                f"  b.txt = {result['b']!r}"
            )

    out_path = DATA / "gnu_flag_order.txt"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n基准已写入: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
