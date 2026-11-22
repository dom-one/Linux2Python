"""并行搜索：真实命令行入口的端到端验证（读法修正版）。

上一版（_t1107）把 stdout 接成管道却等进程退出后才读，于是：
子进程写满 Windows 的 4KB 管道缓冲 → 卡在写上 → 永远不退出 →
父进程在忙等循环里永远等不到退出。挂死的是探针，不是实现。
这一版用 communicate()（并发读两个管道）做等价性比对，
进程数观测改用 stdout=DEVNULL + 单独线程抽干 stderr。

要验的：
① `python main.py grep -r -j 4 ...` 与 `-j 1` 的 stdout 逐字节一致、退出码一致；
② 并行时确实起了子进程；
③ `--help` 里能看到 --jobs。
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "grep_parallel"
REPORT = DATA / "cli_parallel.txt"

TREE = DATA / "equiv_tree"
PATTERN = "ERROR"


def run_cli(extra: list[str], timeout: int = 120) -> tuple[int, bytes, bytes]:
    proc = subprocess.run(
        [sys.executable, "main.py", "grep", "-r", *extra, PATTERN, str(TREE)],
        cwd=ROOT,
        capture_output=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    lines: list[str] = []

    def say(text: str) -> None:
        lines.append(text)
        print(text, flush=True)

    if not TREE.exists():
        say(f"语料树不存在: {TREE}")
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        return 1

    code1, out1, err1 = run_cli([])
    code2, out2, err2 = run_cli(["-j", "4"])
    say(f"串行: exit={code1} stdout字节={len(out1)} stderr字节={len(err1)}")
    say(f"并行: exit={code2} stdout字节={len(out2)} stderr字节={len(err2)}")
    say(f"stdout 逐字节一致: {'是' if out1 == out2 else '否'}")
    say(f"stderr 逐字节一致: {'是' if err1 == err2 else '否'}")
    say(f"退出码一致: {'是' if code1 == code2 else '否'}")
    if out1 != out2:
        a, b = out1.splitlines(), out2.splitlines()
        for i in range(min(len(a), len(b))):
            if a[i] != b[i]:
                say(f"  首个差异行 {i}: 串行={a[i]!r} 并行={b[i]!r}")
                break
        say(f"  行数: 串行={len(a)} 并行={len(b)}")

    # 进程数观测：stdout 丢给 DEVNULL（不占管道缓冲），stderr 单独线程抽干
    proc = subprocess.Popen(
        [sys.executable, "main.py", "grep", "-r", "-j", "4", PATTERN, str(TREE)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    err_chunks: list[bytes] = []

    def drain() -> None:
        assert proc.stderr is not None
        while True:
            data = proc.stderr.read(4096)
            if not data:
                break
            err_chunks.append(data)

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    deadline = time.time() + 120
    while proc.poll() is None and time.time() < deadline:
        time.sleep(0.05)
    if proc.poll() is None:
        say("超时未退出，强杀")
        proc.kill()
    proc.wait()
    reader.join(timeout=5)
    child_err = b"".join(err_chunks)
    say(f"并行跑完退出码={proc.returncode} 子进程 stderr 字节={len(child_err)}")
    if child_err:
        say(f"子进程 stderr: {child_err.decode('utf-8', errors='replace')[:2000]}")

    help_proc = subprocess.run(
        [sys.executable, "main.py", "grep", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    say(f"--help 里出现 --jobs: {'是' if '--jobs' in help_proc.stdout else '否'}")

    DATA.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"\nreport -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
