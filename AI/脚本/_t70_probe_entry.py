"""探针：核对 w2l/entry.py 的真实行为。

要弄清五件事：
1. entry_name() 在没有 DMLINUX / 有 DMLINUX 时分别返回什么
2. DMLINUX 的取值判定规则（空串？0？任意字符串？）
3. command_prog() 拼出来的前缀
4. 顶层 --help 的输出在两种入口下的差异
5. 各指令 --help 里 argparse 的 prog 用的是哪个名字

跑法：
    python AI/脚本/_t70_probe_entry.py
"""

from __future__ import annotations

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


def run(cmd: list[str], env: dict[str, str] | None = None) -> tuple[int, str]:
    """跑一条命令，返回 (退出码, 输出)。"""
    full_env = dict(os.environ)
    full_env.pop("DMLINUX", None)
    if env:
        full_env.update(env)
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        env=full_env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def main() -> None:
    from w2l.entry import ENV_FLAG, command_prog, entry_name

    section("1. entry_name() 在不同 DMLINUX 取值下的返回值")
    base = dict(os.environ)
    base.pop("DMLINUX", None)
    cases = [
        ("未设置", None),
        ("=1", "1"),
        ("=0", "0"),
        ("= 空串", ""),
        ("=yes", "yes"),
        ("= 空格", " "),
    ]
    for label, value in cases:
        env = dict(base)
        if value is not None:
            env[ENV_FLAG] = value
        old = os.environ.get(ENV_FLAG)
        if value is None:
            os.environ.pop(ENV_FLAG, None)
        else:
            os.environ[ENV_FLAG] = value
        try:
            print("  DMLINUX %-8s -> entry_name() = %r" % (label, entry_name()))
        finally:
            if old is None:
                os.environ.pop(ENV_FLAG, None)
            else:
                os.environ[ENV_FLAG] = old

    section("2. command_prog() 拼出来的前缀")
    os.environ.pop(ENV_FLAG, None)
    print("  无 DMLINUX: command_prog('grep') = %r" % command_prog("grep"))
    os.environ[ENV_FLAG] = "1"
    try:
        for name in ("grep", "ls", "cat", "head", "tail"):
            print("  有 DMLINUX: command_prog(%r) = %r" % (name, command_prog(name)))
    finally:
        os.environ.pop(ENV_FLAG, None)

    section("3. 顶层 --help 的输出对比")
    rc_a, out_a = run([sys.executable, "main.py", "--help"])
    print("  [python main.py --help] 退出码 %d" % rc_a)
    print(out_a)
    rc_b, out_b = run([sys.executable, "main.py", "--help"], {"DMLINUX": "1"})
    print("")
    print("  [DMLINUX=1 python main.py --help] 退出码 %d" % rc_b)
    print(out_b)

    section("4. 无参数（退出码应为 1，帮助走顶层）")
    rc_c, out_c = run([sys.executable, "main.py"])
    print("  [python main.py] 退出码 %d" % rc_c)
    print(out_c)

    section("5. 指令级 --help 里 argparse 的 prog")
    for cmd in ("grep", "ls", "cat", "head", "tail"):
        rc, out = run([sys.executable, "main.py", cmd, "--help"])
        first = out.splitlines()[0] if out else "(空)"
        print("  python main.py %-6s --help -> %s" % (cmd, first))
    print("")
    for cmd in ("grep", "ls", "cat", "head", "tail"):
        rc, out = run([sys.executable, "main.py", cmd, "--help"], {"DMLINUX": "1"})
        first = out.splitlines()[0] if out else "(空)"
        print("  DMLINUX=1 ... %-6s --help -> %s" % (cmd, first))

    section("6. argparse 用法错误信息里的 prog")
    rc, out = run([sys.executable, "main.py", "grep", "--bogus"])
    print("  [python main.py grep --bogus] 退出码 %d" % rc)
    print(out)
    rc, out = run([sys.executable, "main.py", "grep", "--bogus"], {"DMLINUX": "1"})
    print("")
    print("  [DMLINUX=1 ... grep --bogus] 退出码 %d" % rc)
    print(out)

    section("7. DMLINUX=0 时顶层帮助显示什么（0 是非空字符串）")
    rc, out = run([sys.executable, "main.py", "--help"], {"DMLINUX": "0"})
    print(out)

    section("8. 经由 bin/ 启动器（PATH 命中）")
    bin_dir = os.path.join(ROOT, "bin")
    env = dict(os.environ)
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    env.pop("DMLINUX", None)
    for args in (["--help"], ["grep", "--help"]):
        proc = subprocess.run(
            ["cmd.exe", "/d", "/c", "dmlinux " + " ".join(args)],
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        print("  [dmlinux %s] 退出码 %d" % (" ".join(args), proc.returncode))
        print((proc.stdout + proc.stderr).strip())
        print("")

    section("9. shell 版启动器（bin/dmlinux 无扩展名）")
    bash = r"E:\software\Git\Git\bin\bash.exe"
    if os.path.isfile(bash):
        env2 = dict(env)
        proc = subprocess.run(
            [bash, "-c", 'PATH="$PATH" dmlinux --help'],
            cwd=ROOT,
            env=env2,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        print("  [bash dmlinux --help] 退出码 %d" % proc.returncode)
        print((proc.stdout + proc.stderr).strip())
    else:
        print("  没找到 Git Bash，跳过")

    section("10. 启动器有没有污染调用者的环境变量")
    print("  dmlinux.cmd 用 setlocal，dmlinux 用 export+exec：")
    print("  - cmd 版 setlocal 后设的变量不外泄")
    print("  - sh 版 export 后 exec 替换自身进程，变量只影响被 exec 的 python")
    proc = subprocess.run(
        ["cmd.exe", "/d", "/c", "dmlinux --help && echo AFTER=[%DMLINUX%]"],
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print("")
    print("  [cmd: dmlinux --help && echo AFTER=...] 退出码 %d" % proc.returncode)
    print((proc.stdout + proc.stderr).strip())


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
