"""并行搜索：大目录树上的真实差距。

前面两轮探针已经排除了「新文件被 Defender 扫一遍」这个假象（暖树 0.070s vs GNU 0.057s，
已经在同一量级）。这一轮换到机器上真实的大目录树上量：

① 本项目串行 grep -r vs GNU grep -r，输出行数必须一致（量的是速度，不是口径）。
② 拆出「遍历」与「搜索」两段，看大树上时间花在哪。
③ 量出并行能拿到的收益上限：按 CPU 核数分片的理论加速比。

目标是回答一个问题：并行搜索到底值不值得做，值得做在哪条指令上。
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "grep_parallel"
REPORT = DATA / "bigtree.txt"

sys.path.insert(0, str(ROOT))

from w2l.commands.grep import build_parser, grep  # noqa: E402
from w2l.context import RunContext  # noqa: E402

TARGETS = [
    ("E:/1", "import"),
    ("C:/Windows/System32", "kernel32"),
]


def count_files(root: str) -> int:
    total = 0
    for _dirpath, _dirnames, filenames in os.walk(root):
        total += len(filenames)
    return total


def walk_only(root: str) -> tuple[float, int]:
    """只遍历不读内容，看遍历本身在大树上占多少。"""
    start = time.perf_counter()
    total = 0
    for _dirpath, _dirnames, filenames in os.walk(root):
        total += len(filenames)
    return time.perf_counter() - start, total


def run_project(root: str, pattern: str) -> tuple[float, int, int]:
    namespace = build_parser().parse_args(["-r", pattern, root])
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(cwd=ROOT, stdout=out, stderr=err, stdin=io.StringIO(""))
    start = time.perf_counter()
    code = grep(namespace, ctx)
    elapsed = time.perf_counter() - start
    return elapsed, out.getvalue().count("\n"), code


def run_gnu(root: str, pattern: str) -> tuple[float, int]:
    exe = shutil.which("grep")
    start = time.perf_counter()
    proc = subprocess.run(
        [exe, "-r", pattern, root],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return time.perf_counter() - start, proc.stdout.count("\n")


def main() -> int:
    lines: list[str] = []

    def say(text: str) -> None:
        lines.append(text)
        print(text)

    say(f"cpu_count={os.cpu_count()}")
    for root, pattern in TARGETS:
        if not os.path.isdir(root):
            say(f"{root}: 不存在，跳过")
            continue
        say(f"\n===== {root}  pattern={pattern!r} =====")
        elapsed, files = walk_only(root)
        say(f"01 纯遍历          : {elapsed:.3f}s files={files}")

        elapsed, hits, code = run_project(root, pattern)
        say(f"02 本项目串行      : {elapsed:.3f}s lines={hits} exit={code}")

        elapsed, hits = run_gnu(root, pattern)
        say(f"03 GNU grep        : {elapsed:.3f}s lines={hits}")

    DATA.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"\nreport -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
