"""--pid 演示，供 teach/23 的第 19 步使用。

用法:
    python AI/脚本/_t608_tail_pid_demo.py

要证明的事：目标进程退出后，`tail -f --pid <pid>` 自己结束。

测法上的坑（务必注意）:
    subprocess.Popen 的 wait() 只等进程退出，**不关句柄**。
    句柄还开着 → Windows 上进程对象还在 → OpenProcess 照样能打开它
    → _pid_alive 永远返回 True → tail 永远不结束。

    上一版探针（_t603/_t604 之前的版本）就栽在这里，误判成「--pid 没生效」。

    正确测法：让目标进程由一个「马上就退出」的中间进程拉起来。
    中间进程退出时它对目标进程的句柄随之关闭，目标进程变成真正的孤儿，
    这时目标进程一退出，PID 就真的释放了。
"""

from __future__ import annotations

import os
import shutil
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
    "import subprocess, sys\n"
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
    base = tempfile.mkdtemp(prefix="tailpid")
    try:
        with open(os.path.join(base, "p.txt"), "wb") as fh:
            fh.write(b"x\n")

        pid = spawn_orphan(4)
        print("[pid] 目标进程活着时 _pid_alive=%r" % _pid_alive(pid))

        start = time.time()
        proc = subprocess.Popen(
            [sys.executable, MAIN, "tail", "-f", "-s", "0.2",
             "--pid", str(pid), "p.txt"],
            cwd=base, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            proc.wait(timeout=25)
            print("[pid] 目标进程退出后 tail 自己结束，耗时 %.1f 秒"
                  % (time.time() - start))
        except subprocess.TimeoutExpired:
            print("[pid] tail 25 秒内没结束（--pid 没生效）")
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
    finally:
        shutil.rmtree(base, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
