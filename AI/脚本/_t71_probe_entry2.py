"""探针二：w2l/entry.py 的环境变量语义与 argparse prog 覆盖。

要弄清：
1. 启动器设置的 DMLINUX 会不会漏回调用者的环境
2. 调用者自己预设 DMLINUX=0 会怎样（假阳性）
3. 不设 prog 时 argparse 默认用什么（解释为什么要覆盖）
4. entry_name() 是调用时求值还是导入时求值
5. DMLINUX 已存在时，启动器用的是自己的值还是继承的

跑法：
    python AI/脚本/_t71_probe_entry2.py
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)


def section(title: str) -> None:
    print("")
    print("=" * 60)
    print(title)
    print("=" * 60)


def run(cmd, env=None, cwd=None):
    full = dict(os.environ)
    full.pop("DMLINUX", None)
    if env:
        full.update(env)
    proc = subprocess.run(
        cmd,
        cwd=cwd or ROOT,
        env=full,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def main() -> None:
    section("1. 启动器设置的 DMLINUX 会不会漏回调用者环境")
    # 在父 shell 里 unset，跑一次 dmlinux，再在同一个 shell 里看 DMLINUX 还在不在
    script = 'dmlinux --help >nul 2>&1 & if defined DMLINUX (echo LEAKED=[%DMLINUX%]) else (echo NOT_LEAKED)'
    proc = subprocess.run(
        ["cmd.exe", "/d", "/c", script],
        cwd=ROOT,
        env={k: v for k, v in os.environ.items() if k != "DMLINUX"},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print("  cmd 版启动器跑完后父 shell 里的 DMLINUX: %s"
          % (proc.stdout + proc.stderr).strip())

    bash = r"E:\software\Git\Git\bin\bash.exe"
    if os.path.isfile(bash):
        script2 = 'PATH="$PATH:$PWD/bin"; unset DMLINUX; dmlinux --help >/dev/null 2>&1; if [ -z "${DMLINUX:-}" ]; then echo NOT_LEAKED; else echo "LEAKED=[$DMLINUX]"; fi'
        proc2 = subprocess.run(
            [bash, "-c", script2],
            cwd=ROOT,
            env={k: v for k, v in os.environ.items() if k != "DMLINUX"},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        print("  sh  版启动器跑完后父 shell 里的 DMLINUX: %s"
              % (proc2.stdout + proc2.stderr).strip())

    section("2. 调用者自己预设 DMLINUX=0 的后果（假阳性）")
    rc, out = run([sys.executable, "main.py", "--help"], {"DMLINUX": "0"})
    print("  [DMLINUX=0 python main.py --help] 退出码 %d，第一行：%s"
          % (rc, out.splitlines()[0] if out else "(空)"))
    rc, out = run([sys.executable, "main.py", "--help"], {"DMLINUX": ""})
    print("  [DMLINUX=  python main.py --help] 退出码 %d，第一行：%s"
          % (rc, out.splitlines()[0] if out else "(空)"))

    section("3. 启动器会不会被调用者预设的 DMLINUX 影响")
    bin_dir = os.path.join(ROOT, "bin")
    env = dict(os.environ)
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    env["DMLINUX"] = "0"
    proc = subprocess.run(
        ["cmd.exe", "/d", "/c", "dmlinux --help"],
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print("  [父环境 DMLINUX=0，dmlinux --help] 第一行：%s"
          % (proc.stdout.splitlines()[0] if proc.stdout.strip() else "(空)"))

    section("4. 不覆盖 prog 时 argparse 默认用什么")
    print("  sys.argv[0] = %r" % sys.argv[0])
    p = argparse.ArgumentParser(description="x")
    p.add_argument("pattern")
    print("  默认 prog 推导结果：")
    try:
        p.parse_args(["--help"])
    except SystemExit:
        pass

    print("")
    print("  显式 prog='python main.py grep' 时：")
    p2 = argparse.ArgumentParser(prog="python main.py grep", description="x")
    p2.add_argument("pattern")
    try:
        p2.parse_args(["--help"])
    except SystemExit:
        pass

    print("")
    print("  显式 prog='dmlinux grep' 时：")
    p3 = argparse.ArgumentParser(prog="dmlinux grep", description="x")
    p3.add_argument("pattern")
    try:
        p3.parse_args(["--help"])
    except SystemExit:
        pass

    section("5. entry_name() 是导入时求值还是调用时求值")
    from w2l.entry import entry_name
    print("  导入后立刻调用: %r" % entry_name())
    os.environ["DMLINUX"] = "1"
    print("  运行中改环境变量后再调用: %r" % entry_name())
    os.environ.pop("DMLINUX", None)
    print("  再删掉环境变量后调用: %r" % entry_name())

    section("6. prog 覆盖对错误信息的影响")
    rc, out = run([sys.executable, "main.py", "head", "-n"])
    print("  [python main.py head -n] 退出码 %d" % rc)
    print(out)
    print("")
    rc, out = run([sys.executable, "main.py", "head", "-n"], {"DMLINUX": "1"})
    print("  [DMLINUX=1 ... head -n] 退出码 %d" % rc)
    print(out)

    section("7. argparse 的 prog 会不会被 -h/--help 之外的路径改写")
    # sys.argv[0] 在不同调用方式下的取值
    for cmd in ([sys.executable, "main.py"], [sys.executable, os.path.join(ROOT, "main.py")]):
        proc = subprocess.run(
            cmd + ["--bogus-cmd"],
            cwd=ROOT,
            env={k: v for k, v in os.environ.items() if k != "DMLINUX"},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        first = (proc.stdout + proc.stderr).splitlines()
        print("  调用 %s -> %s" % (" ".join(cmd)[-30:], first[0] if first else "(空)"))

    section("8. 直接 import 时 argparse 默认 prog 是什么")
    rc, out = run([sys.executable, "-c",
                   "import argparse;p=argparse.ArgumentParser();p.add_argument('x');"
                   "import sys;print('argv0=',sys.argv[0]);"
                   "try:p.parse_args(['--help'])\nexcept SystemExit:pass"])
    print(out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
