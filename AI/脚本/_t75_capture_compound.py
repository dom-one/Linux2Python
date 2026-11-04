"""测试教程里准备用的复合 shell 命令，确认在核对器环境里能跑、输出确定。

跑法：
    python AI/脚本/_t75_capture_compound.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BASH = r"E:\software\Git\Git\bin\bash.exe"


def decode(raw: bytes) -> str:
    for enc in ("utf-8", "gbk", "cp936"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def run(command: str, timeout: int = 120):
    handle, outpath = tempfile.mkstemp(suffix=".txt")
    os.close(handle)
    try:
        full = 'cd "%s" && { %s ; } > "%s" 2>&1' % (ROOT, command, outpath)
        proc = subprocess.run([BASH, "-c", full], capture_output=True,
                              stdin=subprocess.DEVNULL, timeout=timeout)
        with open(outpath, "rb") as fh:
            return proc.returncode, decode(fh.read()).strip()
    finally:
        try:
            os.remove(outpath)
        except OSError:
            pass


COMMANDS = [
    # 启动器跑完后父 shell 有没有被污染
    'PATH="$PATH:$PWD/bin" dmlinux --help > /dev/null && if [ -z "${DMLINUX:-}" ]; '
    'then echo "父 shell: DMLINUX 未设置（没漏回）"; else echo "父 shell: DMLINUX=[$DMLINUX]"; fi',
    # 启动器里能不能看到 DMLINUX
    'PATH="$PATH:$PWD/bin" dmlinux grep --help | head -1',
    # 父 shell 预设 DMLINUX=0，dmlinux 自己会不会被影响
    'PATH="$PATH:$PWD/bin" DMLINUX=0 dmlinux --help | head -1',
    # 父 shell 预设 DMLINUX=0，直接 python main.py 的表现
    'DMLINUX=0 python main.py --help | head -1',
    # 父 shell 预设 DMLINUX=空，直接 python main.py 的表现
    'DMLINUX= python main.py --help | head -1',
    # 启动器跑完后 DMLINUX 有没有传进 python 进程内部
    'PATH="$PATH:$PWD/bin" dmlinux grep --help | head -1',
    # 确认 sh 版启动器在 PATH 里命中的是无扩展名那份
    'PATH="$PATH:$PWD/bin" command -v dmlinux',
    # 顶层 help 的第一行（带 head 截断，避免整块比对）
    'python main.py --help | head -1',
    'DMLINUX=1 python main.py --help | head -1',
    # 命令级 usage 前两行
    'python main.py grep --help | head -2',
    'DMLINUX=1 python main.py grep --help | head -2',
    # 错误信息最后一行
    'python main.py grep -Z 2>&1 | tail -1',
    'DMLINUX=1 python main.py grep -Z 2>&1 | tail -1',
    # 各指令的 prog
    'python -c "from w2l.entry import command_prog;print(command_prog(\'grep\'));print(command_prog(\'ls\'));print(command_prog(\'cat\'));print(command_prog(\'head\'));print(command_prog(\'tail\'))"',
]


def main() -> None:
    for idx, cmd in enumerate(COMMANDS, 1):
        rc, out = run(cmd)
        print("")
        print("#" * 70)
        print("# [%d] %s" % (idx, cmd))
        print("# rc=%d" % rc)
        print("#" * 70)
        print(out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
