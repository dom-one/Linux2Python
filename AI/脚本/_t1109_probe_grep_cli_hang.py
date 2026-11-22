"""并行搜索：复现 CLI 路径的挂死，并把子进程的报错抓出来。

现象：`python main.py grep -r -j 4 ...` 直接在命令行里跑是好的（退出码 0，输出正确），
但被一个 Python 父进程用 subprocess 拉起来、并且 stdout/stderr 走管道时，主进程卡住，
池里的工作进程一个都没剩下。

这一版把父进程换成管道收集，边跑边读 stderr（不能等 communicate()，
因为主进程不退出就读不到 EOF），超时就杀掉并把抓到的 stderr 原样打出来。
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "grep_parallel"
REPORT = DATA / "cli_hang.txt"

TREE = DATA / "equiv_tree"
PATTERN = "ERROR"
TIMEOUT = 60


def run_capture(extra: list[str], capture: bool) -> tuple[int, bytes, bytes, str]:
    argv = [sys.executable, "main.py", "grep", "-r", *extra, PATTERN, str(TREE)]
    if capture:
        proc = subprocess.Popen(
            argv,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    else:
        proc = subprocess.Popen(
            argv,
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    chunks: list[bytes] = []
    notes: list[str] = []

    def drain() -> None:
        assert proc.stderr is not None
        while True:
            data = proc.stderr.read(4096)
            if not data:
                break
            chunks.append(data)

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()

    deadline = time.time() + TIMEOUT
    while proc.poll() is None and time.time() < deadline:
        time.sleep(0.1)
    if proc.poll() is None:
        notes.append(f"超时 {TIMEOUT}s 未退出，强杀")
        proc.kill()
    proc.wait()
    reader.join(timeout=5)
    out = proc.stdout.read() if (capture and proc.stdout) else b""
    return proc.returncode, out, b"".join(chunks), "\n".join(notes)


def main() -> int:
    lines: list[str] = []

    def say(text: str) -> None:
        lines.append(text)
        print(text, flush=True)

    if not TREE.exists():
        say(f"语料树不存在: {TREE}")
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        return 1

    say("=== A: stdout 与 stderr 都走管道 ===")
    code, out, err, note = run_capture(["-j", "4"], capture=True)
    say(f"退出码={code} stdout字节={len(out)}")
    say(f"备注: {note}")
    say(f"stderr 内容（{len(err)} 字节）:")
    say(err.decode("utf-8", errors="replace")[:4000])

    say("\n=== B: stdout 丢弃，只 stderr 走管道 ===")
    code2, out2, err2, note2 = run_capture(["-j", "4"], capture=False)
    say(f"退出码={code2}")
    say(f"备注: {note2}")
    say(f"stderr 内容（{len(err2)} 字节）:")
    say(err2.decode("utf-8", errors="replace")[:4000])

    DATA.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"\nreport -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
