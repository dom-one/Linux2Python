"""并行搜索：加速比的干净测量（带预热）。

上一版探针（_t1106）测出来的数字不可用，两处都被污染了：
① 第一次串行跑的是**冷**文件（Windows Defender 要逐个扫一遍），187.9s；
   紧接着第二次串行同样的树只要 70.4s。拿冷的那次当基准，加速比算出来是假的。
② E:/1 在测量期间被用户的脚本持续写入，两次运行的命中行数都不一样
   （12155 / 12162），所以两次运行的输出本来就不可能逐字节相同。

这一版：
① 先跑一次预热（丢弃结果），把文件缓存热起来；
② 预热之后依次量 串行 / -j 4 / -j 8 / 串行，取两次串行的较小值当基准；
③ 只报加速比与耗时，不在活的树上做逐字节比对
   （逐字节等价性由 _t1105 在静态树上单独证明）。

机器上同时有用户的重负载脚本在跑，所以绝对秒数带噪声，
加速比也比空闲机器上的理论值低。
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "grep_parallel"
REPORT = DATA / "parallel_gain_warm.txt"

sys.path.insert(0, str(ROOT))

from w2l.commands.grep import build_parser, grep  # noqa: E402
from w2l.context import RunContext  # noqa: E402

TREE = "E:/1"
PATTERN = "import"


def run(jobs: int) -> tuple[float, int]:
    argv = ["-r", PATTERN, TREE]
    if jobs > 1:
        argv = ["-j", str(jobs)] + argv
    namespace = build_parser().parse_args(argv)
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(cwd=ROOT, stdout=out, stderr=err, stdin=io.StringIO(""))
    start = time.perf_counter()
    grep(namespace, ctx)
    return time.perf_counter() - start, out.getvalue().count("\n")


def main() -> int:
    lines: list[str] = []

    def say(text: str) -> None:
        lines.append(text)
        print(text, flush=True)

    say(f"tree={TREE} pattern={PATTERN!r}")

    warm, warm_lines = run(1)
    say(f"预热(丢弃)      : {warm:8.3f}s lines={warm_lines}")

    serial_a, lines_a = run(1)
    say(f"串行 A          : {serial_a:8.3f}s lines={lines_a}")

    par4, lines4 = run(4)
    say(f"并行 -j 4       : {par4:8.3f}s lines={lines4}")

    par8, lines8 = run(8)
    say(f"并行 -j 8       : {par8:8.3f}s lines={lines8}")

    serial_b, lines_b = run(1)
    say(f"串行 B          : {serial_b:8.3f}s lines={lines_b}")

    baseline = min(serial_a, serial_b)
    say(f"串行基准(取小)  : {baseline:8.3f}s")
    say(f"加速比 -j 4     : {baseline / par4:.2f}x")
    say(f"加速比 -j 8     : {baseline / par8:.2f}x")
    say(f"命中行数是否一致: 串行A={lines_a} -j4={lines4} -j8={lines8} 串行B={lines_b}")

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
        gnu_t = time.perf_counter() - start
        say(f"GNU grep        : {gnu_t:8.3f}s lines={proc.stdout.count(chr(10))}")
        say(f"本项目/GNU 倍数 : {baseline / gnu_t:.2f}x")

    DATA.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"\nreport -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
