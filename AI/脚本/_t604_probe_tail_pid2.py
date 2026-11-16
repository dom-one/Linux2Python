"""探针四：--pid 的正确测法。

用法:
    python AI/脚本/_t604_probe_tail_pid2.py

上一版探针的错：subprocess.Popen 的 wait() 只等退出，不关句柄。
句柄还开着 → 进程对象还在 → OpenProcess 照样能打开 → _pid_alive 返回 True。
这不是 tail 的 bug，是测法的问题。

这版让「目标进程」由一个马上就退出的中间进程拉起来：
中间进程退出时它对目标进程的句柄随之关闭，目标进程变成真正的孤儿，
这时候目标进程一退出，PID 就真的释放了。

另外测一件事：--pid 的目标进程如果一直活着，tail 就不该结束。
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from w2l.commands.tail import _pid_alive  # noqa: E402

MAIN = os.path.join(ROOT, "main.py")

# 中间进程：拉起真正的目标进程，打印它的 pid，然后自己立刻退出。
LAUNCHER = (
    "import subprocess, sys, os\n"
    "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(%d)'])\n"
    "print(p.pid, flush=True)\n"
)


def spawn_orphan(seconds: int) -> int:
    """拉起一个孤儿进程，返回它的 pid。"""
    proc = subprocess.Popen(
        [sys.executable, "-c", LAUNCHER % seconds],
        stdout=subprocess.PIPE,
    )
    pid = int(proc.stdout.readline().strip())
    proc.wait(timeout=20)
    return pid


def main() -> int:
    base = tempfile.mkdtemp(prefix="tailpid2")
    log = os.path.join(base, "p.txt")
    with open(log, "wb") as fh:
        fh.write(b"x\n")

    # 1. 孤儿进程活着 -> _pid_alive True
    pid = spawn_orphan(4)
    print("1) 孤儿进程 pid=%d 活着 -> _pid_alive=%r" % (pid, _pid_alive(pid)))

    # 2. 端到端：tail -f --pid <pid>，pid 死后 tail 要自己退出
    start = time.time()
    tail_proc = subprocess.Popen(
        [sys.executable, MAIN, "tail", "-f", "-s", "0.2", "--pid", str(pid), "p.txt"],
        cwd=base, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        tail_proc.wait(timeout=25)
        print("2) tail 在目标进程退出后自己结束，总耗时 %.1fs" % (time.time() - start))
    except subprocess.TimeoutExpired:
        print("2) tail 25s 内没结束（--pid 没生效）")
        tail_proc.terminate()
        tail_proc.wait(timeout=10)

    # 3. pid 彻底释放后再查
    time.sleep(0.5)
    print("3) 目标进程已死 -> _pid_alive=%r" % _pid_alive(pid))

    # 4. 目标进程一直活着时，tail 不该结束
    pid2 = spawn_orphan(30)
    tail2 = subprocess.Popen(
        [sys.executable, MAIN, "tail", "-f", "-s", "0.2", "--pid", str(pid2), "p.txt"],
        cwd=base, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(4)
    still = tail2.poll() is None
    print("4) 目标进程还活着，tail 是否仍在跑：%r（期望 True）" % still)
    tail2.terminate()
    try:
        tail2.wait(timeout=10)
    except subprocess.TimeoutExpired:
        tail2.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
