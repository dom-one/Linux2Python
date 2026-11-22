"""并行搜索：在大目录树上量并行到底值多少。

上一轮探针（_t1104）在 E:/1（17790 个文件）上量到：
    本项目串行 170.117s，GNU grep 10.024s，命中行数一致（12110）。
这说明「串行版本在大仓上是明显瓶颈」不是空话。

这一轮在同一棵树上量并行：
① -j 4 与 -j 8 的耗时；
② 并行输出与串行输出逐字节一致（并行没改变结果，只是改了速度）；
③ 加速比。

注意：本机同时有用户的重负载脚本在跑，耗时数字带噪声，
所以每档都紧挨着再跑一次串行做参照，报加速比而不是报绝对秒数。
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
REPORT = DATA / "parallel_gain.txt"

sys.path.insert(0, str(ROOT))

from w2l.commands.grep import build_parser, grep  # noqa: E402
from w2l.context import RunContext  # noqa: E402

TREE = "E:/1"
PATTERN = "import"


def run(jobs: int) -> tuple[float, str, int]:
    argv = ["-r", PATTERN, TREE]
    if jobs > 1:
        argv = ["-j", str(jobs)] + argv
    namespace = build_parser().parse_args(argv)
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(cwd=ROOT, stdout=out, stderr=err, stdin=io.StringIO(""))
    start = time.perf_counter()
    code = grep(namespace, ctx)
    return time.perf_counter() - start, out.getvalue(), code


def main() -> int:
    lines: list[str] = []

    def say(text: str) -> None:
        lines.append(text)
        print(text, flush=True)

    say(f"cpu_count={os.cpu_count()} tree={TREE} pattern={PATTERN!r}")

    serial_t, serial_out, serial_code = run(1)
    say(f"串行(第1次)      : {serial_t:8.3f}s lines={serial_out.count(chr(10))} exit={serial_code}")

    for jobs in (4, 8):
        par_t, par_out, par_code = run(jobs)
        same = par_out == serial_out
        say(f"并行 -j {jobs:<2d}      : {par_t:8.3f}s lines={par_out.count(chr(10))} exit={par_code}")
        say(f"   与串行逐字节一致: {'是' if same else '否'}   加速比={serial_t / par_t:.2f}x")

    serial_t2, serial_out2, _ = run(1)
    say(f"串行(第2次)      : {serial_t2:8.3f}s lines={serial_out2.count(chr(10))}")
    baseline = min(serial_t, serial_t2)
    say(f"串行取较小值做基准: {baseline:.3f}s")

    exe = shutil.which("grep")
    if exe:
        start = time.perf_counter()
        proc = subprocess.run(
            [exe, "-r", PATTERN, TREE],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        say(f"GNU grep        : {time.perf_counter() - start:8.3f}s lines={proc.stdout.count(chr(10))}")

    DATA.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"\nreport -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
