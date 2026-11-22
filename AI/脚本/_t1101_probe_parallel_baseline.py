"""并行搜索基线探针。

回答四个问题：
1. 本机的 GNU grep 在哪、是什么版本（差分对照要对着它比）。
2. multiprocessing 的 spawn 方式在这台机器上能不能跑（Windows 走 spawn，
   子进程要重新 import 主模块与项目模块，这是并行方案的头号风险）。
3. 子进程能不能 import w2l.commands.grep 并跑一次真实的文件搜索。
4. 串行搜索在合成树上的耗时，用来给并行方案定验收指标。

结果落盘到 AI/数据/ 下，报告用 read 工具读，不用终端显示（终端会吃掉连续空格）。
"""

from __future__ import annotations

import io
import multiprocessing
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "grep_parallel"
REPORT = DATA / "baseline.txt"

sys.path.insert(0, str(ROOT))


def build_tree(root: Path, dirs: int = 30, per_dir: int = 30) -> int:
    """造一棵合成目录树：每层文件里掺入命中行、不命中行、空文件与二进制文件。"""
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    count = 0
    for d in range(dirs):
        sub = root / f"pkg{d:03d}"
        sub.mkdir()
        for f in range(per_dir):
            target = sub / f"mod{f:03d}.txt"
            body = [f"line {f} of {d}", "ERROR boom", "plain text", "another ERROR line"]
            target.write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
            count += 1
        if d % 5 == 0:
            (sub / "empty.txt").write_bytes(b"")
            (sub / "bin.dat").write_bytes(b"\x00\x01ERROR\x00\n")
            count += 2
    return count


def _child_probe(payload):
    """子进程里跑的真实工作：import 项目模块，搜索一个文件。

    放在模块顶层而不是函数内部，是为了让 spawn 的子进程能 pickle 它。
    """
    target, pattern = payload
    from w2l.commands.grep import _detect_encoding, _decode_lines  # noqa: PLC0415

    with open(target, "rb") as handle:
        sample = handle.read(8192)
        encoding = _detect_encoding(sample)
        handle.seek(0)
        lines = list(_decode_lines(handle, encoding))
    return (target, pattern, encoding, len(lines))


def time_serial_grep(tree: Path, pattern: str) -> tuple[float, int]:
    """跑本项目现有的串行 grep，记录耗时与输出行数。"""
    from w2l.commands.grep import build_parser, grep  # noqa: PLC0415
    from w2l.context import RunContext  # noqa: PLC0415

    namespace = build_parser().parse_args(["-r", pattern, str(tree)])
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(cwd=ROOT, stdout=out, stderr=err, stdin=io.StringIO(""))
    start = time.perf_counter()
    code = grep(namespace, ctx)
    elapsed = time.perf_counter() - start
    return elapsed, out.getvalue().count("\n")


def time_gnu_grep(tree: Path, pattern: str) -> tuple[float, int, str]:
    exe = shutil.which("grep")
    if exe is None:
        return 0.0, -1, ""
    start = time.perf_counter()
    proc = subprocess.run(
        [exe, "-r", pattern, str(tree)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.perf_counter() - start
    return elapsed, proc.stdout.count("\n"), proc.stderr.strip()


def main() -> int:
    lines: list[str] = []

    def say(text: str) -> None:
        lines.append(text)
        print(text)

    say(f"python={sys.version.split()[0]} os={os.name} cpu_count={os.cpu_count()}")
    say(f"multiprocessing start methods={multiprocessing.get_all_start_methods()}")

    gnu = shutil.which("grep")
    if gnu:
        ver = subprocess.run([gnu, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        say(f"gnu grep={gnu}")
        say(f"gnu grep version={ver.stdout.splitlines()[0] if ver.stdout else '?'}")
    else:
        say("gnu grep=NOT FOUND")

    # spawn 自检：起一个池，子进程里 import 项目模块并做一次真实搜索。
    DATA.mkdir(parents=True, exist_ok=True)
    probe_file = DATA / "spawn_probe.txt"
    probe_file.write_text("ERROR spawn ok\nfine\n", encoding="utf-8", newline="\n")
    try:
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(processes=2) as pool:
            results = pool.map(_child_probe, [(str(probe_file), "ERROR")] * 2)
        say(f"spawn pool=OK result={results[0]}")
    except Exception as exc:  # noqa: BLE001
        say(f"spawn pool=FAILED {type(exc).__name__}: {exc}")

    count = build_tree(DATA / "tree")
    say(f"fixture files={count} path={DATA / 'tree'}")

    serial_t, serial_lines = time_serial_grep(DATA / "tree", "ERROR")
    say(f"project serial: {serial_t:.3f}s lines={serial_lines}")

    gnu_t, gnu_lines, gnu_err = time_gnu_grep(DATA / "tree", "ERROR")
    say(f"gnu grep      : {gnu_t:.3f}s lines={gnu_lines} stderr={gnu_err!r}")

    DATA.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"\nreport -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
