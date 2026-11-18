"""探针十：GNU 判断「变了 / 没变」时到底比的是哪些位。

现象：chmod -v u+s 在 0644 的文件上，GNU 报的是
「retained as 4644」而不是「changed from 0644 to 4644」，
说明它的比较里不含 setuid/setgid/sticky 位。

要定死：比的是全部 12 位，还是只比低 9 位（rwx）？
结果写进 AI/数据/chmod_probe10_report.txt。
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
DATA = AI_DIR / "数据" / "chmod_probe10"
REPORT = AI_DIR / "数据" / "chmod_probe10_report.txt"

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


def case(label: str, args: list[str]) -> None:
    wipe()
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "a.txt").write_text("x\n", encoding="utf-8")
    code, out, err = run(["chmod", "-v", *args])
    say(f"--- {label}: chmod -v {' '.join(args)}")
    say("    stdout: " + out.replace("\n", "\n      ").rstrip())
    if err:
        say("    stderr: " + err.replace("\n", "\n      ").rstrip())
    # 连续再跑一次，看看第二次报什么
    code, out, err = run(["chmod", "-v", *args])
    say("    再跑一次: " + out.replace("\n", "\n      ").rstrip())
    say("")


say("=== 八进制带特殊位 ===")
say("")
for mode in ("4644", "2644", "1644", "6644", "4755", "2755", "1755", "4645"):
    case(f"八进制 {mode}", [mode, "a.txt"])

say("=== 符号模式带特殊位 ===")
say("")
for spec in ("u+s", "g+s", "+t", "a+s", "u+s,g+s"):
    case(f"符号 {spec}", [spec, "a.txt"])

say("=== 只读文件上的特殊位 ===")
say("")
wipe()
DATA.mkdir(parents=True, exist_ok=True)
(DATA / "a.txt").write_text("x\n", encoding="utf-8")
os.chmod(DATA / "a.txt", stat.S_IREAD)
code, out, err = run(["chmod", "-v", "u+s", "a.txt"])
say(f"--- 只读文件上 chmod -v u+s: {out.strip()}")

wipe()
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"报告已写入 {REPORT}")
