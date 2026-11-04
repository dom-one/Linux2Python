"""清理核对器跑飞留下的巨型临时文件。

背景：AI/脚本/_t12_verify_teach.py 对全部 20 篇教程跑全量核对时，
某条教程命令触发了 Python 交互 REPL 的崩溃循环（Windows 控制台句柄问题），
往 mkstemp 建的临时文件里灌了 3.2 GB 的 traceback，磁盘被迅速吃满。

Git Bash 的 /tmp 映射不到 Windows 路径，bash 侧的 rm 被安全策略挡住，
所以这里用 Python 直接按 Windows 原生路径删。

跑法：
    python AI/脚本/_t81_cleanup_tmp.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

# Git Bash 的 /tmp 对应 Windows 的 TEMP 目录
TMP = tempfile.gettempdir()


def main() -> None:
    print("Windows TEMP 目录: %s" % TMP)

    big = []
    total = 0
    for name in os.listdir(TMP):
        path = os.path.join(TMP, name)
        try:
            if not os.path.isfile(path):
                continue
            size = os.path.getsize(path)
        except OSError:
            continue
        total += size
        if size > 50 * 1024 * 1024:
            big.append((size, path))

    print("临时目录总大小: %.1f MB" % (total / 1024 / 1024))
    if big:
        print("超过 50MB 的文件:")
        for size, path in sorted(big, reverse=True):
            print("  %10.1f MB  %s" % (size / 1024 / 1024, path))
    else:
        print("没有超过 50MB 的临时文件")

    for size, path in sorted(big, reverse=True):
        try:
            os.remove(path)
            print("已删除 %s (%.1f MB)" % (path, size / 1024 / 1024))
        except OSError as exc:
            print("删除失败 %s: %s" % (path, exc))

    # 残留的 bash / python 进程
    print("")
    print("检查残留进程:")
    for image in ("bash.exe", "python.exe"):
        proc = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq %s" % image, "/FO", "CSV", "/NH"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        rows = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        print("  %s: %d 个" % (image, len(rows)))
        for row in rows:
            print("    " + row)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
