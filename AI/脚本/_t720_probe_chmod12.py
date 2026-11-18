"""探针十二：GNU 判断「变了没变」的规则，最后一轮定位。

要回答一个问题：GNU 比较的 old_mode 到底是「stat 读出来的模式」还是别的。
做法：chmod 4755 之后立刻问 GNU 的 stat 报什么，
再 chmod -v 4755 一次（第二次的 old_mode 就是 stat 读到的那个值）。
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
DATA = AI_DIR / "数据" / "chmod_probe12"
REPORT = AI_DIR / "数据" / "chmod_probe12_report.txt"

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


def step(label: str, cmd: list[str]) -> str:
    code, out, err = run(cmd)
    say(f"  $ {' '.join(cmd)}  -> rc={code}")
    if out:
        say("    stdout: " + out.replace("\n", "\n      ").rstrip())
    if err:
        say("    stderr: " + err.replace("\n", "\n      ").rstrip())
    return out.strip()


say("=== 4755 之后 stat 报什么 ===")
say("")
wipe()
DATA.mkdir(parents=True, exist_ok=True)
(DATA / "a.txt").write_text("x\n", encoding="utf-8")
step("先看原始模式", ["stat", "-c", "%a", "a.txt"])
step("chmod 4755", ["chmod", "4755", "a.txt"])
step("再看模式", ["stat", "-c", "%a", "a.txt"])
step("再 chmod -v 4755（old 模式 = stat 读到的）", ["chmod", "-v", "4755", "a.txt"])
step("再看模式", ["stat", "-c", "%a", "a.txt"])
say("")

say("=== 4644 / 755 / 644 的对照 ===")
say("")
for mode in ("4644", "0755", "0644", "4444"):
    wipe()
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "a.txt").write_text("x\n", encoding="utf-8")
    say(f"  --- chmod {mode}")
    step("chmod（第一遍）", ["chmod", "-v", mode, "a.txt"])
    step("stat", ["stat", "-c", "%a", "a.txt"])
    step("chmod -v（第二遍）", ["chmod", "-v", mode, "a.txt"])
    say("")

say("=== 同一个进程里连着改两个文件 ===")
say("")
wipe()
DATA.mkdir(parents=True, exist_ok=True)
(DATA / "a.txt").write_text("x\n", encoding="utf-8")
(DATA / "b.txt").write_text("x\n", encoding="utf-8")
step("chmod -v 4755 a.txt b.txt", ["chmod", "-v", "4755", "a.txt", "b.txt"])
step("stat 两个文件", ["stat", "-c", "%a %n", "a.txt", "b.txt"])

wipe()
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"报告已写入 {REPORT}")
