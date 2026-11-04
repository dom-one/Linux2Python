"""修 AI/脚本/_t12_verify_teach.py 的三个安全缺陷。

背景：2026-11-05 全量核对 20 篇教程时，核对器把磁盘写满了——
临时文件涨到 3.2 GB，内容是 Python 3.14 交互 REPL 的崩溃 traceback，
根因是 teach/03 里一个裸 `python` 命令块（REPL 示例）。

三个缺陷：

1. **没有输出上限**：命令的 stdout 无限制写进临时文件。
   实测裸 `python` 在非交互 stdin 下会让 Python 3.13+ 的新 REPL
   反复抛 `_pyrepl/windows_console.py getheightwidth` 的 OSError，
   每次崩溃重启继续刷，6 秒能写 281.9 MB（~47 MB/s）。

2. **超时杀不掉孙进程**：核对器用 `subprocess.run(timeout=...)`，
   超时只杀 bash.exe；bash 拉起的 python.exe 是孙进程，
   会继续往被删（Windows 上删除失败且被 except OSError 吞掉）的文件里写。
   这就是「核对器返回了、磁盘还在涨」的原因。

3. **交互式 REPL 块没被跳过**：RISKY_PATTERNS 只挡会改工作区的命令，
   裸 `python` 不改工作区所以照跑，但它在管道里根本没法用。

修法：
- 加 MAX_OUTPUT_BYTES（4 MB）上限，边跑边看文件大小，超了立刻杀进程树
- 超时用 taskkill /T /F 杀整棵进程树
- 进交互 REPL 的命令块（裸 python / python3 / py -3）默认跳过
- 临时文件删不掉时重试，仍然失败就打印路径，别再静默吞掉

按规矩先写 .preview，断言过了再 os.replace 覆盖。

跑法：
    python AI/脚本/_t83_fix_verifier.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TARGET = os.path.join(ROOT, "AI", "脚本", "_t12_verify_teach.py")
PREVIEW = TARGET + ".preview"

BS = chr(92)  # 反斜杠，用拼接写避免本文件里的转义歧义


def build_old_risky_tail() -> str:
    return (
        '        r"' + BS + 'btee' + BS + 'b",\n'
        "    )\n"
        "]\n"
    )


def build_new_risky_tail() -> str:
    return (
        '        r"' + BS + 'btee' + BS + 'b",\n'
        "        # 进交互 REPL 的写法：管道里跑不了，还会让 Python 3.13+ 的新 REPL\n"
        "        # 反复抛控制台句柄的 OSError 刷爆输出（实测 6 秒 280 MB）\n"
        "        r\"^(python3?|py( -3)?)$\",\n"
        "    )\n"
        "]\n"
    )


OLD_RUNNER = '''def _run_outer(command: str, outpath: str, shell_cmd: str, timeout: int):
    """按给定命令模板执行一次。"""
    with open(os.devnull, "rb") as devnull:
        return subprocess.run(shell_cmd, capture_output=True, stdin=devnull, timeout=timeout)


def run_in_shell(command: str, timeout: int = 60):
    """跑一条命令，返回 (退出码, 输出文本)。

    优先用 Git Bash：教程里的命令是 bash 风格（ls、wc、rm --），
    cmd.exe 里没有这些命令。用 bash 跑才对得上读者看到的写法。

    找不到 Git Bash 时退回 cmd.exe：读者在 cmd 里敲也要能跑通。
    """
    handle, outpath = tempfile.mkstemp(suffix=".txt")
    os.close(handle)
    try:
        if BASH_BIN and os.path.isfile(BASH_BIN):
            # bash 里 stdout 重定向直接写文件，编码由 Python 端按 GBK/UTF-8 兜底
            full = 'cd "%s" && { %s ; } > "%s" 2>&1' % (WORKDIR, command, outpath)
            try:
                _run_outer(command, outpath, [BASH_BIN, "-c", full], timeout)
            except subprocess.TimeoutExpired:
                return -1, "(超时 %ds，命令没退出)" % timeout
        else:
            full = 'cd /d "%s" && %s > "%s" 2>&1' % (WORKDIR, command, outpath)
            try:
                _run_outer(command, outpath, "cmd.exe /c " + full, timeout)
            except subprocess.TimeoutExpired:
                return -1, "(超时 %ds，命令没退出)" % timeout
        with open(outpath, "rb") as fh:
            return 0, decode(fh.read()).strip()
    finally:
        try:
            os.remove(outpath)
        except OSError:
            pass
'''

NEW_RUNNER = '''# 单条命令的输出上限。超过就杀掉进程树并报错，不让磁盘被写满。
# 实测裸 `python` 在非交互 stdin 下会让 Python 3.13+ 的新 REPL 反复抛
# _pyrepl/windows_console.py getheightwidth 的 OSError，6 秒能写 280 MB。
MAX_OUTPUT_BYTES = 4 * 1024 * 1024


def _kill_tree(pid: int) -> None:
    """杀掉进程树。

    只杀父进程不够：bash 拉起的 python.exe 是孙进程，
    会继续往临时文件里写，磁盘照涨。taskkill /T 杀整棵树。
    """
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True, stdin=subprocess.DEVNULL)
    except OSError:
        pass


def _run_outer(command: str, outpath: str, shell_cmd, timeout: int):
    """按给定命令模板执行一次，返回 (退出码, 是否超限)。

    超限时杀进程树并返回 True，让调用方知道输出不可信。

    关键点是**边跑边看文件大小**，不能等命令结束再查：
    失控命令的写入速度是 ~47 MB/s，等到超时再查已经写了 2.8 GB。
    """
    deadline = time.time() + timeout
    with open(os.devnull, "rb") as devnull:
        # 命令自己的 stdout/stderr 已经被重定向进 outpath，
        # 这里把子进程的管道丢到 DEVNULL，避免在内存里再攒一份
        proc = subprocess.Popen(shell_cmd, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, stdin=devnull)
        while True:
            try:
                proc.wait(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                pass

            try:
                size = os.path.getsize(outpath)
            except OSError:
                size = 0
            if size > MAX_OUTPUT_BYTES:
                _kill_tree(proc.pid)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
                return -2, True

            if time.time() > deadline:
                _kill_tree(proc.pid)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
                return -1, False

        return proc.returncode, False


def run_in_shell(command: str, timeout: int = 60):
    """跑一条命令，返回 (退出码, 输出文本)。

    优先用 Git Bash：教程里的命令是 bash 风格（ls、wc、rm --），
    cmd.exe 里没有这些命令。用 bash 跑才对得上读者看到的写法。

    找不到 Git Bash 时退回 cmd.exe：读者在 cmd 里敲也要能跑通。

    安全约束：
    - 输出超过 MAX_OUTPUT_BYTES 立刻杀掉进程树并报错（防止刷爆磁盘）
    - 超时用 taskkill /T 杀整棵进程树（孙进程不杀就会继续写文件）
    """
    handle, outpath = tempfile.mkstemp(suffix=".txt")
    os.close(handle)
    try:
        if BASH_BIN and os.path.isfile(BASH_BIN):
            # bash 里 stdout 重定向直接写文件，编码由 Python 端按 GBK/UTF-8 兜底
            full = 'cd "%s" && { %s ; } > "%s" 2>&1' % (WORKDIR, command, outpath)
            code, over = _run_outer(command, outpath, [BASH_BIN, "-c", full], timeout)
        else:
            full = 'cd /d "%s" && %s > "%s" 2>&1' % (WORKDIR, command, outpath)
            code, over = _run_outer(command, outpath, "cmd.exe /c " + full, timeout)

        if over:
            return -2, "(输出超过 %d MB，命令已杀掉，输出不可信)" % (
                MAX_OUTPUT_BYTES // 1024 // 1024)
        if code == -1:
            return -1, "(超时 %ds，命令没退出)" % timeout

        with open(outpath, "rb") as fh:
            return code, decode(fh.read()).strip()
    finally:
        # Windows 上文件被进程占着时 os.remove 会失败，重试几次；
        # 还失败就打印路径，别再静默吞掉（上次就是它把 3.2 GB 文件留在盘上）
        for _ in range(3):
            try:
                os.remove(outpath)
                break
            except OSError:
                time.sleep(0.3)
        else:
            print("警告：临时文件删不掉，可能还有进程占着：%s" % outpath)
'''

OLD_DOC = """- 用 --allow-risky 显式放行才会真跑
"""

NEW_DOC = """- 用 --allow-risky 显式放行才会真跑

资源约束（2026-11-05 加）:
全量核对时差点把磁盘写满——教程里的裸 `python` 命令块在管道里跑，
会进 Python 3.13+ 的新 REPL，反复抛控制台句柄的 OSError 并无限刷 traceback
（实测 6 秒 280 MB）。加上：
- 单条命令输出上限 4 MB，边跑边看文件大小，超了立刻杀进程树
- 超时用 taskkill /T 杀整棵进程树（只杀 bash 杀不掉 python 孙进程）
- 进交互 REPL 的命令块（裸 python / python3 / py -3）默认跳过
"""

OLD_IMPORTS = """import argparse
import os
import re
import subprocess
import sys
import tempfile
"""

NEW_IMPORTS = """import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
"""


def main() -> None:
    with open(TARGET, "r", encoding="utf-8", newline="") as fh:
        original = fh.read()

    text = original

    for old, new, label in (
        (OLD_DOC, NEW_DOC, "docstring 段"),
        (OLD_IMPORTS, NEW_IMPORTS, "import 段"),
        (OLD_RUNNER, NEW_RUNNER, "run_in_shell 段"),
        (build_old_risky_tail(), build_new_risky_tail(), "RISKY_PATTERNS 段"),
    ):
        if old not in text:
            raise SystemExit("找不到片段：%s" % label)
        if text.count(old) != 1:
            raise SystemExit("片段出现多次，跳过：%s" % label)
        text = text.replace(old, new, 1)

    # 断言
    assert "MAX_OUTPUT_BYTES = 4 * 1024 * 1024" in text
    assert "def _kill_tree(pid: int) -> None:" in text
    assert "taskkill" in text
    assert "import time" in text
    assert "(输出超过 %d MB" in text
    assert "警告：临时文件删不掉" in text
    assert "边跑边看文件大小" in text
    assert "进交互 REPL 的写法" in text
    assert "资源约束（2026-11-05 加）" in text
    # 危险模式列表还是整类跳过 git
    assert 'r"' + BS + 'bgit' + BS + 'b",' in text
    # 新增的 REPL 判定
    assert 'r"^(python3?|py( -3)?)$",' in text

    with open(PREVIEW, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    with open(PREVIEW, "r", encoding="utf-8", newline="") as fh:
        check = fh.read()
    assert check == text, "预览文件和写入内容不一致"

    os.replace(PREVIEW, TARGET)
    print("已更新 %s" % TARGET)
    print("  加输出上限 4MB + 边跑边看文件大小，超限杀进程树")
    print("  超时改用 taskkill /T 杀整棵进程树")
    print("  裸 python / python3 / py -3 进 REPL 的块改为跳过")
    print("  临时文件删不掉时打印路径，不再静默吞掉")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
