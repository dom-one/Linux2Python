"""探针四：抓教程里要写的「预期输出」原文。

要拿到：
1. 相对路径调用时 argparse 默认 prog 的 basename
2. grep --help 在两种入口下的完整 usage 行（含折行）
3. ls --help 的完整 usage 行
4. 顶层 --help 的完整原文
5. 环境变量不漏回父 shell 的确认

跑法：
    python AI/脚本/_t71c_probe_entry4.py
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, "AI", "数据")


def section(title: str) -> None:
    print("")
    print("=" * 60)
    print(title)
    print("=" * 60)


def run(argv, env=None, cwd=None):
    full = dict(os.environ)
    full.pop("DMLINUX", None)
    if env:
        full.update(env)
    proc = subprocess.run(
        argv,
        cwd=cwd or ROOT,
        env=full,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def show(title, rc, out):
    print("")
    print("--- %s （退出码 %d）---" % (title, rc))
    print(out)


def main() -> None:
    section("1. 相对路径调用时 argparse 默认 prog")
    os.makedirs(DATA, exist_ok=True)
    tmp = os.path.join("AI", "数据", "_t71c_probe_prog.py")
    with open(os.path.join(ROOT, tmp), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(
            "import argparse, os, sys\n"
            "p = argparse.ArgumentParser()\n"
            "print('argv0=%r' % sys.argv[0])\n"
            "print('prog=%r' % p.prog)\n"
            "print('basename=%r' % os.path.basename(sys.argv[0]))\n"
        )
    try:
        rc, out = run([sys.executable, tmp])
        print("  相对路径调用: %s" % out.replace("\n", " | "))
        rc, out = run([sys.executable, os.path.join(ROOT, tmp)])
        print("  绝对路径调用: %s" % out.replace("\n", " | "))
    finally:
        os.remove(os.path.join(ROOT, tmp))

    section("2. argparse 源码里的默认 prog 规则")
    import argparse
    import inspect
    src = inspect.getsource(argparse.ArgumentParser.__init__)
    for line in src.splitlines():
        if "prog" in line:
            print("  " + line.strip())

    section("3. grep --help 两种入口的完整 usage 行")
    rc, out = run([sys.executable, "main.py", "grep", "--help"])
    show("python main.py grep --help", rc, "\n".join(out.splitlines()[:2]))
    rc, out = run([sys.executable, "main.py", "grep", "--help"], {"DMLINUX": "1"})
    show("DMLINUX=1 ... grep --help", rc, "\n".join(out.splitlines()[:2]))

    section("4. ls --help 两种入口的完整 usage 行")
    rc, out = run([sys.executable, "main.py", "ls", "--help"])
    show("python main.py ls --help", rc, "\n".join(out.splitlines()[:2]))
    rc, out = run([sys.executable, "main.py", "ls", "--help"], {"DMLINUX": "1"})
    show("DMLINUX=1 ... ls --help", rc, "\n".join(out.splitlines()[:2]))

    section("5. 顶层 --help 完整原文（无 DMLINUX）")
    rc, out = run([sys.executable, "main.py", "--help"])
    show("python main.py --help", rc, out)

    section("6. 顶层 --help 完整原文（有 DMLINUX）")
    rc, out = run([sys.executable, "main.py", "--help"], {"DMLINUX": "1"})
    show("DMLINUX=1 ... --help", rc, out)

    section("7. 未知选项的报错原文")
    rc, out = run([sys.executable, "main.py", "grep", "-Z"])
    show("python main.py grep -Z", rc, out)
    rc, out = run([sys.executable, "main.py", "grep", "-Z"], {"DMLINUX": "1"})
    show("DMLINUX=1 ... grep -Z", rc, out)

    section("8. entry.py 里每个命令的 prog 实际值")
    from w2l.registry import load_commands
    load_commands()
    from w2l.entry import command_prog
    os.environ.pop("DMLINUX", None)
    for name in ("cat", "grep", "head", "ls", "tail"):
        print("  无 DMLINUX: %-14s <- command_prog(%r)" % (command_prog(name), name))
    os.environ["DMLINUX"] = "1"
    try:
        for name in ("cat", "grep", "head", "ls", "tail"):
            print("  有 DMLINUX: %-14s <- command_prog(%r)" % (command_prog(name), name))
    finally:
        os.environ.pop("DMLINUX", None)

    section("9. shell 版启动器不漏回环境变量")
    bash = r"E:\software\Git\Git\bin\bash.exe"
    if os.path.isfile(bash):
        script = (
            'export PATH="$PATH:$PWD/bin"; unset DMLINUX; '
            'dmlinux --help >/dev/null 2>&1; '
            'if [ -z "${DMLINUX:-}" ]; then echo "父 shell: DMLINUX 未设置（不漏回）"; '
            'else echo "父 shell: DMLINUX=[$DMLINUX]（漏回！）"; fi'
        )
        proc = subprocess.run(
            [bash, "-c", script],
            cwd=ROOT,
            env={k: v for k, v in os.environ.items() if k != "DMLINUX"},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        print("  " + (proc.stdout + proc.stderr).strip())


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
