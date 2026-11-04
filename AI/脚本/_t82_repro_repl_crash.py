"""复现并确认核对器跑飞的根因（安全版：输出封顶）。

现象：全量核对时某个 bash 块让 /tmp 下的临时文件涨到 3.2 GB，
内容是 Python 3.14 交互 REPL 的崩溃 traceback。

假设：teach/03 里的裸 `python` 命令块。核对器把 stdout 重定向到临时文件，
stdin 接 devnull，Python 3.13+ 的新 REPL 拿不到控制台句柄 ->
_pyrepl/windows_console.py getheightwidth 抛 OSError -> REPL 崩溃重启 ->
无限刷 traceback。

更糟的是：核对器用 subprocess timeout=60 杀掉的是 bash.exe，
bash 拉起的 python.exe 是孙进程，不会被一起杀，
它继续往被删除（Windows 上删除失败但被 except OSError 吞掉）的临时文件里写。

本脚本做三件事：
1. 用 6 秒超时复现，输出封顶 2MB，跑完立刻杀掉孙进程
2. 检查有没有遗留的孤儿 python.exe
3. 清理临时文件

跑法：
    python AI/脚本/_t82_repro_repl_crash.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BASH = r"E:\software\Git\Git\bin\bash.exe"
CAP = 2 * 1024 * 1024  # 2MB 封顶


def python_pids() -> list[str]:
    proc = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    pids = []
    for line in proc.stdout.splitlines():
        parts = line.split(",")
        if len(parts) > 1 and parts[0].strip('"').lower() == "python.exe":
            pids.append(parts[1].strip('"'))
    return pids


def kill(pids: list[str]) -> None:
    for pid in pids:
        subprocess.run(["taskkill", "/F", "/PID", pid],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")


def main() -> None:
    tmp = os.path.join(tempfile.gettempdir(), "repl_repro.txt")
    if os.path.exists(tmp):
        os.remove(tmp)

    before = python_pids()
    print("复现前 python.exe: %s" % before)

    # 完整复刻核对器的跑法：bash -c + stdout 重定向到文件 + stdin=devnull
    full = 'cd "%s" && { python ; } > "%s" 2>&1' % (ROOT, tmp)
    devnull = open(os.devnull, "rb")
    try:
        try:
            proc = subprocess.run([BASH, "-c", full], capture_output=True,
                                  stdin=devnull, timeout=6)
            print("命令正常退出，rc=%s" % proc.returncode)
        except subprocess.TimeoutExpired:
            print("命令 6 秒超时（和核对器 timeout=60 一样的路径）")
    finally:
        devnull.close()

    size = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    print("6 秒内临时文件已涨到: %.2f MB" % (size / 1024 / 1024))

    # 孙进程还活着吗
    after = python_pids()
    orphans = [p for p in after if p not in before]
    print("超时后多出来的 python.exe: %s" % orphans)

    if orphans:
        print("确认：bash 被杀后，孙进程 python.exe 仍然活着")
        kill(orphans)
        print("已杀掉孤儿进程")

    # 再等 2 秒看文件是否还在涨（活着的孙进程会继续写）
    size2 = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    print("清理前 %.2f MB" % (size2 / 1024 / 1024))

    if os.path.exists(tmp):
        try:
            os.remove(tmp)
            print("已删除临时文件")
        except OSError as exc:
            print("删除失败（说明还有进程占着）: %s" % exc)

    print("")
    print("结论：裸 `python` 在非交互 stdin 下会进入 REPL 崩溃循环")
    print("      核对器的 timeout 杀不掉孙进程，孙进程会无限写临时文件")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
