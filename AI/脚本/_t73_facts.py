"""收集教程要用到的最后一批事实。

要确认：
1. entry.py 的行数
2. 谁引用了 entry.py（消费者清单）
3. 测试总数与 test_launcher.py 的用例数
4. 入口名在项目里的两处落点（顶层 help / 各指令 prog）
5. argparse 的 _prog_name 规则源码

跑法：
    python AI/脚本/_t73_facts.py
"""

from __future__ import annotations

import argparse
import inspect
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def section(title: str) -> None:
    print("")
    print("=" * 60)
    print(title)
    print("=" * 60)


def main() -> None:
    section("1. entry.py 行数与内容")
    p = os.path.join(ROOT, "w2l", "entry.py")
    with open(p, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8")
    lines = text.splitlines()
    print("  字节数 %d，行数 %d" % (len(raw), len(lines)))
    print("  末尾有换行: %s" % raw.endswith(b"\n"))
    print("  函数: %s" % re.findall(r"^def (\w+)", text, re.M))
    print("  常量: %s" % re.findall(r"^(\w+)\s*=", text, re.M))

    section("2. 谁引用了 entry.py")
    hit = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "__pycache__", "build", "dist",
                                    ".pytest_cache", "egg-info")]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT)
            with open(full, "rb") as fh:
                try:
                    body = fh.read().decode("utf-8")
                except UnicodeDecodeError:
                    continue
            if "entry" in body and ("from .entry" in body or "from ..entry" in body
                                    or "w2l.entry" in body):
                for i, ln in enumerate(body.splitlines(), 1):
                    if "entry" in ln and ("import" in ln or "command_prog" in ln
                                          or "entry_name" in ln):
                        hit.append("%s:%d  %s" % (rel, i, ln.strip()))
    for h in hit:
        print("  " + h)

    section("3. 测试数量")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--collect-only"],
        cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    tail = proc.stdout.strip().splitlines()
    print("  " + (tail[-1] if tail else "(空)"))
    proc2 = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_launcher.py", "-q"],
        cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    print("  test_launcher.py: %s" % proc2.stdout.strip().splitlines()[-1])

    section("4. argparse 的 prog 默认规则")
    from argparse import _prog_name
    src = inspect.getsource(_prog_name)
    print(src.rstrip())

    section("5. 顶层 help 与各指令 prog 的落点")
    with open(os.path.join(ROOT, "w2l", "cli.py"), "rb") as fh:
        cli = fh.read().decode("utf-8")
    for i, ln in enumerate(cli.splitlines(), 1):
        if "entry_name" in ln or "prog" in ln.lower():
            print("  w2l/cli.py:%d  %s" % (i, ln.strip()))
    cmd_dir = os.path.join(ROOT, "w2l", "commands")
    for fn in sorted(os.listdir(cmd_dir)):
        if not fn.endswith(".py"):
            continue
        with open(os.path.join(cmd_dir, fn), "rb") as fh:
            body = fh.read().decode("utf-8")
        for i, ln in enumerate(body.splitlines(), 1):
            if "command_prog" in ln:
                print("  w2l/commands/%s:%d  %s" % (fn, i, ln.strip()))

    section("6. 启动器里设置 DMLINUX 的位置")
    for fn in ("dmlinux.cmd", "dmlinux"):
        full = os.path.join(ROOT, "bin", fn)
        with open(full, "rb") as fh:
            body = fh.read().decode("utf-8")
        for i, ln in enumerate(body.splitlines(), 1):
            if "DMLINUX" in ln:
                print("  bin/%s:%d  %s" % (fn, i, ln.strip()))

    section("7. DMLINUX 会不会传给被启动器拉起的子进程")
    # 启动器设置的是自己的进程环境；python 进程继承它。
    # 验证：dmlinux 里面再启动一个 python，看它是否看到 DMLINUX
    bash = r"E:\software\Git\Git\bin\bash.exe"
    if os.path.isfile(bash):
        script = (
            'export PATH="$PATH:$PWD/bin"; '
            'dmlinux grep --help >/dev/null 2>&1; '
            'echo "父 shell: DMLINUX=[${DMLINUX:-未设置}]"'
        )
        proc = subprocess.run([bash, "-c", script], cwd=ROOT,
                              env={k: v for k, v in os.environ.items() if k != "DMLINUX"},
                              stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
        print("  " + (proc.stdout + proc.stderr).strip())


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
