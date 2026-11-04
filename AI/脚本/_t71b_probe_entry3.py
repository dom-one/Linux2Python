"""探针三：argparse 默认 prog 到底怎么推导的。

要弄清：
1. python main.py 时 argparse 默认 prog 是什么
2. 绝对路径调用 main.py 时默认 prog 是什么
3. 为什么要显式覆盖成 "python main.py grep" 而不是让它用默认值
4. prog 里带空格时 argparse 怎么处理（缩进对齐）

跑法：
    python AI/脚本/_t71b_probe_entry3.py
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def section(title: str) -> None:
    print("")
    print("=" * 60)
    print(title)
    print("=" * 60)


def run(argv, env=None):
    full = dict(os.environ)
    full.pop("DMLINUX", None)
    if env:
        full.update(env)
    proc = subprocess.run(
        argv,
        cwd=ROOT,
        env=full,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def main() -> None:
    section("1. argparse 默认 prog 的推导规则（sys.argv[0] 的 basename）")
    probe = (
        "import argparse,sys;"
        "p=argparse.ArgumentParser();"
        "p.add_argument('pattern');"
        "print('argv0=%r' % sys.argv[0]);"
        "print('prog=%r' % p.prog);"
        "p.parse_args(['--help'])"
    )
    for label, argv in (
        ("相对路径 main.py", [sys.executable, "main.py"]),
        ("绝对路径 main.py", [sys.executable, os.path.join(ROOT, "main.py")]),
    ):
        rc, out = run(argv + ["-c", probe] if False else [sys.executable, "-c", probe])
        # 用 -c 时 argv[0] 是 '-c'，改用真实脚本入口验证
        print("  (%s) 下面用真实 main.py 验证" % label)

    # 真实入口：临时写一个脚本打印 prog
    tmp = os.path.join(ROOT, "AI", "数据", "_t71b_probe_prog.py")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(
            "import argparse, sys\n"
            "p = argparse.ArgumentParser()\n"
            "p.add_argument('pattern')\n"
            "print('argv0=%r' % sys.argv[0])\n"
            "print('prog=%r' % p.prog)\n"
        )
    try:
        for label, argv in (
            ("相对路径", [sys.executable, tmp]),
            ("绝对路径", [sys.executable, os.path.join(ROOT, "AI", "数据", "_t71b_probe_prog.py")]),
        ):
            rc, out = run(argv)
            print("  %s: %s" % (label, out.replace("\n", " | ")))
    finally:
        os.remove(tmp)

    section("2. prog 带空格时 usage 行的对齐")
    probe2 = (
        "import argparse\n"
        "p = argparse.ArgumentParser(prog='python main.py grep')\n"
        "p.add_argument('pattern')\n"
        "p.add_argument('paths', nargs='*')\n"
        "p.parse_args(['--help'])\n"
    )
    rc, out = run([sys.executable, "-c", probe2])
    print(out)

    section("3. 对比：让 argparse 用默认值会得到什么")
    probe3 = (
        "import argparse\n"
        "p = argparse.ArgumentParser()\n"
        "p.add_argument('pattern')\n"
        "p.add_argument('paths', nargs='*')\n"
        "p.parse_args(['--help'])\n"
    )
    rc, out = run([sys.executable, "-c", probe3])
    print(out)

    section("4. 项目实际输出（覆盖后的样子）")
    rc, out = run([sys.executable, "main.py", "grep", "--help"])
    print(out.splitlines()[0])
    print(out.splitlines()[1] if len(out.splitlines()) > 1 else "")

    section("5. 顶层帮助是手写的，不是 argparse")
    rc, out = run([sys.executable, "main.py", "--help"])
    print(out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
