"""探针：摸清本机 chmod 的可实现边界。

要查清四件事：
1. Git Bash 的 GNU chmod 到底改了什么（MSYS 有没有自己的权限层）
2. Windows Python 的 os.stat 看得到 MSYS 存下的权限位吗
3. NTFS 备用数据流（ADS）能不能存权限位、重命名后还在不在
4. GNU chmod 的命令行行为基线（-c/-v/--reference/递归/报错文案）

结果写进 AI/数据/chmod_probe_report.txt，别只看终端输出。
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
ROOT = AI_DIR.parent
DATA = AI_DIR / "数据" / "chmod_probe"
REPORT = AI_DIR / "数据" / "chmod_probe_report.txt"

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def force_rmtree(path: Path) -> None:
    if not path.exists():
        return
    for item in path.rglob("*"):
        try:
            os.chmod(item, stat.S_IREAD | stat.S_IWRITE)
        except OSError:
            pass
    try:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    except OSError:
        pass
    shutil.rmtree(path, ignore_errors=True)


def py_mode(path: Path) -> str:
    try:
        st = os.stat(path)
    except OSError as exc:
        return f"<stat 失败: {exc}>"
    return f"{stat.S_IMODE(st.st_mode):04o} (raw {oct(st.st_mode)})"


def main() -> int:
    force_rmtree(DATA)
    DATA.mkdir(parents=True, exist_ok=True)

    say("=== 0. 工具位置 ===")
    for name in ("chmod", "ls", "stat"):
        found = shutil.which(name)
        say(f"  which {name} -> {found}")
    say(f"  python -> {sys.executable}")
    say(f"  cwd    -> {os.getcwd()}")

    # ---------- 夹具 ----------
    (DATA / "f.txt").write_text("hello\n", encoding="utf-8")
    (DATA / "g.txt").write_text("hello\n", encoding="utf-8")
    sub = DATA / "sub"
    sub.mkdir()
    (sub / "inner.txt").write_text("inner\n", encoding="utf-8")
    say("")
    say("=== 1. 初始状态（Python 视角） ===")
    for name in ("f.txt", "g.txt", "sub"):
        say(f"  {name}: {py_mode(DATA / name)}")

    # ---------- 2. GNU chmod 改了什么 ----------
    say("")
    say("=== 2. GNU chmod 之后 ===")
    cases = [
        (["chmod", "600", "f.txt"], "chmod 600 f.txt"),
        (["chmod", "755", "g.txt"], "chmod 755 g.txt"),
        (["chmod", "444", "f.txt"], "chmod 444 f.txt"),
        (["chmod", "u+x", "g.txt"], "chmod u+x g.txt"),
        (["chmod", "755", "sub"], "chmod 755 sub"),
    ]
    for cmd, label in cases:
        code, out, err = run(cmd, cwd=DATA)
        say(f"  $ {label} -> rc={code} out={out!r} err={err!r}")

    say("")
    say("  GNU stat 看到的权限：")
    for name in ("f.txt", "g.txt", "sub"):
        code, out, err = run(["stat", "-c", "%a %A %n", name], cwd=DATA)
        say(f"    {out.strip()!r} (rc={code} err={err.strip()!r})")

    say("")
    say("  GNU ls -l 看到的权限：")
    code, out, err = run(["ls", "-l"], cwd=DATA)
    say("    " + out.replace("\n", "\n    ").rstrip())

    say("")
    say("  Python os.stat 看到的是：")
    for name in ("f.txt", "g.txt", "sub"):
        say(f"    {name}: {py_mode(DATA / name)}")

    say("")
    say("  GNU chmod 444 之后 Python 还能写吗：")
    try:
        with open(DATA / "f.txt", "a", encoding="utf-8") as handle:
            handle.write("appended\n")
        say("    能写 -> GNU chmod 没有设置 Windows 只读属性")
    except OSError as exc:
        say(f"    不能写 ({exc.__class__.__name__}: {exc}) -> 只读属性被设上了")

    # ---------- 3. ADS 能不能存权限位 ----------
    say("")
    say("=== 3. NTFS 备用数据流 ===")
    ads_target = DATA / "ads.txt"
    ads_target.write_text("ads\n", encoding="utf-8")
    ads_path = str(ads_target) + ":w2lmode"
    try:
        with open(ads_path, "w", encoding="utf-8") as handle:
            handle.write("0644")
        say("  写 ADS 成功")
        with open(ads_path, "r", encoding="utf-8") as handle:
            say(f"  读回 ADS 内容: {handle.read()!r}")
        say(f"  os.path.exists(ADS) -> {os.path.exists(ads_path)}")
    except OSError as exc:
        say(f"  ADS 不可用: {exc.__class__.__name__}: {exc}")

    say("")
    say("  MSYS ls -l 看得到 ADS 吗：")
    code, out, err = run(["ls", "-l"], cwd=DATA)
    say("    " + out.replace("\n", "\n    ").rstrip())
    code, out, err = run(["ls", "-la"], cwd=DATA)
    say("    ls -la: " + out.replace("\n", "\n    ").rstrip())

    say("")
    say("  ADS 跟着改名走吗：")
    renamed = DATA / "ads2.txt"
    try:
        os.replace(ads_target, renamed)
        say(f"    改名后读 ADS -> {open(str(renamed) + ':w2lmode', encoding='utf-8').read()!r}")
    except OSError as exc:
        say(f"    改名后读 ADS 失败: {exc.__class__.__name__}: {exc}")

    say("")
    say("  ADS 跟着复制走吗（普通拷贝）：")
    copy_target = DATA / "ads_copy.txt"
    shutil.copyfile(ads_target if ads_target.exists() else renamed, copy_target)
    say(f"    副本上有没有 ADS -> {os.path.exists(str(copy_target) + ':w2lmode')}")

    say("")
    say("  目录也能挂 ADS 吗：")
    try:
        with open(str(DATA / "sub") + ":w2lmode", "w", encoding="utf-8") as handle:
            handle.write("0755")
        say(f"    可以，目录 ADS 存在 -> {os.path.exists(str(DATA / 'sub') + ':w2lmode')}")
    except OSError as exc:
        say(f"    不行: {exc.__class__.__name__}: {exc}")

    # ---------- 4. GNU chmod 的命令行行为基线 ----------
    say("")
    say("=== 4. GNU chmod 命令行基线 ===")
    baseline = [
        ["chmod", "-v", "644", "f.txt"],
        ["chmod", "-c", "644", "f.txt"],
        ["chmod", "644", "missing.txt"],
        ["chmod", "-f", "644", "missing.txt"],
        ["chmod", "644"],
        ["chmod"],
        ["chmod", "999", "f.txt"],
        ["chmod", "abc", "f.txt"],
        ["chmod", "--reference=f.txt", "g.txt"],
        ["chmod", "-R", "700", "sub"],
        ["chmod", "a+rwx", "f.txt"],
        ["chmod", "u+w,g-w", "f.txt"],
        ["chmod", "--help"],
    ]
    for cmd in baseline:
        code, out, err = run(cmd, cwd=DATA)
        say(f"  $ {' '.join(cmd)}")
        say(f"    rc={code}")
        if out:
            say("    stdout: " + out.replace("\n", "\n      ").rstrip())
        if err:
            say("    stderr: " + err.replace("\n", "\n      ").rstrip())

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"报告已写入 {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
