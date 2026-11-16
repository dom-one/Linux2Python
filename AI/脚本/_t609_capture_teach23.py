"""按核对器同样的方式真跑一遍 teach/23 的命令块，把真实输出抓下来。

用法:
    python AI/脚本/_t609_capture_teach23.py

做法与 _t12_verify_teach.py 一致：Git Bash + 输出重定向到文件 + 2>&1 合并，
这样 stdout/stderr 的先后顺序与核对器看到的完全一样。

产出:
    AI/数据/teach23_actual.txt —— 每条命令的真实输出，标了分隔线
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASH = r"E:\software\Git\Git\bin\bash.exe"

MAX_OUTPUT = 4 * 1024 * 1024


def run(command: str, timeout: int = 60) -> str:
    """跑一条命令，返回合并后的输出（与核对器一致）。"""
    handle, outpath = tempfile.mkstemp(suffix=".txt")
    os.close(handle)
    try:
        full = 'cd "%s" && { %s ; } > "%s" 2>&1' % (ROOT, command, outpath)
        with open(os.devnull, "rb") as devnull:
            proc = subprocess.Popen([BASH, "-c", full], stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, stdin=devnull)
            deadline = time.time() + timeout
            while True:
                try:
                    proc.wait(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    pass
                if os.path.getsize(outpath) > MAX_OUTPUT:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                   capture_output=True)
                    break
                if time.time() > deadline:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                   capture_output=True)
                    break
        with open(outpath, "rb") as fh:
            raw = fh.read()
        for enc in ("utf-8", "gbk", "cp936"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")
    finally:
        for _ in range(3):
            try:
                os.remove(outpath)
                break
            except OSError:
                time.sleep(0.3)


DEMO = "AI/数据/tail_demo"

COMMANDS = [
    # 夹具
    "python AI/脚本/_t610_make_tail_demo.py",
    # 第 1 步
    "python main.py cat w2l/commands/tail.py | wc -l",
    # 第 2 步 默认末 10 行
    "python main.py tail %s/a.txt" % DEMO,
    # 第 3 步 +N 是起点
    "python main.py head -n +2 %s/a.txt" % DEMO,
    "python main.py tail -n +2 %s/a.txt" % DEMO,
    # 第 4 步 负号同义
    "python main.py tail -n -2 %s/a.txt" % DEMO,
    "python main.py head -n -2 %s/a.txt" % DEMO,
    # 第 5 步 0 与 +0
    "python main.py tail -n 0 %s/a.txt" % DEMO,
    "python main.py tail -n +0 %s/a.txt" % DEMO,
    # 第 6 步 -c 与 +N 字节
    "python main.py tail -c 5 %s/a.txt" % DEMO,
    "python main.py tail -c +5 %s/a.txt" % DEMO,
    "python main.py tail -c 0 %s/a.txt" % DEMO,
    "python main.py tail -c +0 %s/a.txt" % DEMO,
    # 第 7 步 后写的生效
    "python main.py tail -c 7 -n 2 %s/a.txt" % DEMO,
    "python main.py tail -n 2 -c 7 %s/a.txt" % DEMO,
    # 第 8 步 紧凑写法
    "python main.py tail -2 %s/a.txt" % DEMO,
    # 第 9 步 乘数后缀
    "python main.py tail -c 1b %s/big.txt | wc -c" % DEMO,
    "python main.py tail -c 1k %s/big.txt | wc -c" % DEMO,
    "python main.py tail -c 1kB %s/big.txt | wc -c" % DEMO,
    "python main.py tail -c 1KiB %s/big.txt | wc -c" % DEMO,
    "python main.py tail -n 1b %s/many.txt | wc -l" % DEMO,
    # 第 10 步 多文件标题
    "python main.py tail -n 1 %s/a.txt %s/b.txt" % (DEMO, DEMO),
    # 第 11 步 -q / -v
    "python main.py tail -q -n 1 %s/a.txt %s/b.txt" % (DEMO, DEMO),
    "python main.py tail -v -n 1 %s/a.txt" % DEMO,
    "python main.py tail -q -v -n 1 %s/a.txt %s/b.txt" % (DEMO, DEMO),
    "python main.py tail -v -q -n 1 %s/a.txt %s/b.txt" % (DEMO, DEMO),
    # 第 12 步 标准输入
    "printf 'l1\\nl2\\nl3\\n' | python main.py tail",
    "printf 'l1\\nl2\\nl3\\n' | python main.py tail -v -",
    # 第 13 步 -z
    "python main.py tail -z -n 2 %s/zeros.bin | od -c" % DEMO,
    # 第 14 步 CRLF / 末行无换行
    "python main.py tail -n 2 %s/crlf.txt | od -c" % DEMO,
    "python main.py tail -n 2 %s/nonl.txt | od -c" % DEMO,
    # 第 15 步 二进制透传
    "python main.py tail %s/zeros.bin | od -c" % DEMO,
    # 第 16 步 编码取输出段
    "python main.py tail -n 1 %s/mixed.txt" % DEMO,
    "python main.py head -n 1 %s/mixed.txt" % DEMO,
    # 第 17 步 错误路径
    "python main.py tail %s/nope.txt" % DEMO,
    "python main.py tail -v %s/a.txt %s/nope.txt" % (DEMO, DEMO),
    "python main.py tail -v %s" % DEMO,
    # 第 20/21 步 测试
    "python -m pytest tests/test_tail.py 2>&1 | tail -1",
    "python -m pytest 2>&1 | tail -1",
]


def main() -> int:
    out = []
    for cmd in COMMANDS:
        text = run(cmd, timeout=180)
        out.append("=" * 70)
        out.append("### CMD: %s" % cmd)
        out.append("--- OUTPUT START ---")
        out.append(text.rstrip("\n"))
        out.append("--- OUTPUT END ---")
        out.append("")
    path = os.path.join(ROOT, "AI", "数据", "teach23_actual.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print("已写出 %s（%d 条命令）" % (path, len(COMMANDS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
