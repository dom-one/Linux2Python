"""探针九：GNU 允许权限串里带运算符（a+rw-x），查它的确切语义。"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
DATA = AI_DIR / "数据" / "chmod_probe9"
REPORT = AI_DIR / "数据" / "chmod_probe9_report.txt"

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)


def run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd, cwd=str(DATA), capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return proc.returncode, proc.stdout, proc.stderr


def wipe() -> None:
    if not DATA.exists():
        return
    for item in DATA.rglob("*"):
        try:
            os.chmod(item, stat.S_IREAD | stat.S_IWRITE)
        except OSError:
            pass
    shutil.rmtree(DATA, ignore_errors=True)


def case(spec: str, readonly: bool = False) -> None:
    wipe()
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "a.txt").write_text("x\n", encoding="utf-8")
    if readonly:
        os.chmod(DATA / "a.txt", stat.S_IREAD)
    code, out, err = run(["chmod", "-v", spec, "a.txt"])
    mode = run(["stat", "-c", "%a", "a.txt"])[1].strip()
    say(f"  {spec!r} (初始{'只读' if readonly else '可写'}) -> rc={code} stat={mode}")
    if out:
        say("    stdout: " + out.replace("\n", "\n      ").rstrip())
    if err:
        say("    stderr: " + err.replace("\n", "\n      ").rstrip())


say("=== 权限串里带运算符 ===")
say("")
for spec in (
    "a+rw-x", "u+rw-x", "a+rwx-x", "a+rw-x+rw", "u+rw,g-w", "a+x-r", "a+rw+x",
    "a-rw+x", "a+rw-x", "u+rw-x", "go+rwx-rwx", "a+rwX-x", "a+s-u", "u+r-w",
    "a=rw", "a=rw-x", "a+", "a-", "a=",
):
    case(spec)

say("")
say("=== 只读文件上的同一批 ===")
for spec in ("a+rw-x", "a+x-r", "u+rw-x"):
    case(spec, readonly=True)

wipe()
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"报告已写入 {REPORT}")
