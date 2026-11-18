"""探针五：补齐 chmod 实现还缺的几个基线。

要查：
- MSYS 对 .exe / 只读 .exe / 符号链接的规范权限位是多少（决定本项目口径）
- 逗号分隔的多模式（644,755）怎么落
- --reference 与模式同时给、缺操作数等错误路径的确切文案
- -c 对缺失文件是否也打 "failed to change"

结果写进 AI/数据/chmod_probe5_report.txt。
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
DATA = AI_DIR / "数据" / "chmod_probe5"
REPORT = AI_DIR / "数据" / "chmod_probe5_report.txt"

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


def show(label: str, cmd: list[str], cwd: Path | None = None) -> None:
    code, out, err = run(cmd, cwd=cwd)
    say(f"  $ {' '.join(cmd)}")
    say(f"    rc={code}")
    if out:
        say("    stdout: " + out.replace("\n", "\n      ").rstrip())
    if err:
        say("    stderr: " + err.replace("\n", "\n      ").rstrip())


def main() -> int:
    shutil.rmtree(DATA, ignore_errors=True)
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "f.txt").write_text("hello\n", encoding="utf-8")
    (DATA / "g.txt").write_text("hello\n", encoding="utf-8")

    say("=== MSYS 对不同文件类型的规范权限位 ===")
    exe = Path(r"E:\software\Git\Git\usr\bin\ls.exe")
    if exe.exists():
        code, out, err = run(["stat", "-c", "%a %A %n", str(exe)])
        say(f"  exe: {out.strip()} {err.strip()}")
    bat = Path(r"E:\software\Git\Git\usr\bin\getopt.exe")
    if bat.exists():
        code, out, err = run(["stat", "-c", "%a %A %n", str(bat)])
        say(f"  exe2: {out.strip()}")
    say("  普通文件 / 只读文件 / 目录：")
    for name in ("f.txt", "sub"):
        pass
    (DATA / "sub").mkdir(exist_ok=True)
    for name in ("f.txt", "sub"):
        code, out, err = run(["stat", "-c", "%a %A %n", name], cwd=DATA)
        say(f"    {out.strip()}")
    run(["chmod", "444", "f.txt"], cwd=DATA)
    code, out, err = run(["stat", "-c", "%a %A %n", "f.txt"], cwd=DATA)
    say(f"    只读文件: {out.strip()}")
    run(["chmod", "000", "sub"], cwd=DATA)
    code, out, err = run(["stat", "-c", "%a %A %n", "sub"], cwd=DATA)
    say(f"    只读目录: {out.strip()}")
    say("")

    say("=== 逗号分隔的多模式 ===")
    run(["chmod", "644", "f.txt"], cwd=DATA)
    show("chmod -v 644,755 f.txt", ["chmod", "-v", "644,755", "f.txt"], cwd=DATA)
    code, out, err = run(["stat", "-c", "%a %A", "f.txt"], cwd=DATA)
    say(f"    落盘后: {out.strip()}")
    say("")

    say("=== 错误路径 ===")
    for cmd in (
        ["chmod", "--reference=f.txt", "644", "g.txt"],
        ["chmod", "-R", "644", "f.txt"],
        ["chmod", "-v", "644"],
        ["chmod", "-c", "644", "missing.txt"],
        ["chmod", "u+rw,g+r,o-w", "f.txt"],
        ["chmod", "u+g", "f.txt"],
        ["chmod", "+t", "f.txt"],
        ["chmod", "4755", "f.txt"],
        ["chmod", "0", "f.txt"],
        ["chmod", "0000", "f.txt"],
        ["chmod", "-v", "644", "f.txt", "missing.txt"],
        ["chmod", "--", "644", "f.txt"],
        ["chmod", "u=rw,go=r", "f.txt"],
        ["chmod", "a=rwx", "f.txt"],
        ["chmod", "-R", "700", "sub"],
        ["chmod", "0644", "f.txt"],
        ["chmod", "7", "f.txt"],
        ["chmod", "08", "f.txt"],
    ):
        show(" ".join(cmd), cmd, cwd=DATA)
        say("")

    say("=== 符号链接 ===")
    say("  （本机建符号链接要管理员权限，单独试）")
    code, out, err = run(["ln", "-s", "f.txt", "link.txt"], cwd=DATA)
    say(f"  $ ln -s f.txt link.txt -> rc={code} err={err.strip()}")
    if code == 0:
        code, out, err = run(["stat", "-c", "%a %A %n", "link.txt"], cwd=DATA)
        say(f"    {out.strip()}")
        show("chmod -v 644 link.txt", ["chmod", "-v", "644", "link.txt"], cwd=DATA)
    say("")

    shutil.rmtree(DATA, ignore_errors=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"报告已写入 {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
