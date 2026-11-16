"""探针三：查 --pid 为什么不生效。

用法:
    python AI/脚本/_t603_probe_tail_pid.py

查四件事：
1. --pid 到底有没有进 namespace（参数改写有没有把它吃掉）
2. _pid_alive 对「活着的进程」返回什么
3. _pid_alive 对「已退出但句柄未回收」的进程返回什么
4. _pid_alive 对「已退出且句柄已回收」的进程返回什么
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from w2l.commands.tail import _pid_alive, build_parser  # noqa: E402


def main() -> int:
    # 1. 参数有没有被吃掉
    ns = build_parser().parse_args(["-f", "-s", "0.2", "--pid", "12345", "x.log"])
    print("1) namespace.pid = %r  namespace.files = %r" % (ns.pid, ns.files))
    ns2 = build_parser().parse_args(["-f", "--pid=12345", "x.log"])
    print("   --pid=12345 形式：pid = %r files = %r" % (ns2.pid, ns2.files))
    ns3 = build_parser().parse_args(["--pid", "12345"])
    print("   只有 --pid：pid = %r files = %r" % (ns3.pid, ns3.files))

    # 2/3/4. 三种进程状态
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(2)"])
    print("2) 活着的进程 pid=%d -> _pid_alive = %r" % (child.pid, _pid_alive(child.pid)))

    child.wait(timeout=20)
    print("3) 已退出、句柄刚被 wait 回收 -> _pid_alive = %r" % _pid_alive(child.pid))

    # 故意留一个句柄：再启一个进程当"别人"，用完不回收句柄
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.1)"])
    other_pid = other.pid
    other.wait(timeout=20)
    print("4) 再查一次同一个 pid -> _pid_alive = %r" % _pid_alive(other_pid))

    # 直接看 Windows 的 OpenProcess 行为与 GetLastError
    import ctypes

    kernel32 = ctypes.windll.kernel32
    for pid in (child.pid, other_pid, 999999):
        handle = kernel32.OpenProcess(0x1000, False, pid)
        err = kernel32.GetLastError()
        print("   OpenProcess(pid=%d) handle=%r GetLastError=%d" % (pid, handle, err))
        if handle:
            kernel32.CloseHandle(handle)
    return 0


if __name__ == "__main__":
    sys.exit(main())
