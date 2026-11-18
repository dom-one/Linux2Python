"""探针十一：确认「带特殊位的目标模式一律报 retained」这条规则。

已知的现象：
  chmod -v 644   （0644 文件） -> retained as 0644
  chmod -v 755   （0644 文件） -> changed from 0644 to 0755
  chmod -v 4755  （0644 文件） -> retained as 4755   （rwx 其实变了！）
  chmod -v 4644  （0644 文件） -> retained as 4644

猜的规则：目标模式里只要带 setuid / setgid / sticky 任意一位，
GNU 就一律报 retained（与实际落地状态无关）。
本轮验证：这些模式的实际只读属性怎么落、消息怎么报。

结果写进 AI/数据/chmod_probe11_report.txt。
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
DATA = AI_DIR / "数据" / "chmod_probe11"
REPORT = AI_DIR / "数据" / "chmod_probe11_report.txt"

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


def case(mode: str) -> None:
    wipe()
    DATA.mkdir(parents=True, exist_ok=True)
    target = DATA / "a.txt"
    target.write_text("x\n", encoding="utf-8")
    code, out, err = run(["chmod", "-v", mode, "a.txt"])
    st = os.stat(target)
    readonly = "只读" if not (st.st_mode & stat.S_IWRITE) else "可写"
    say(f"  chmod -v {mode:>5} -> {out.strip()!r}  [落地: {readonly}]")
    if err:
        say(f"      stderr: {err.strip()!r}")
    say("")


say("=== 目标模式带特殊位 vs 不带 ===")
say("")
for mode in (
    "0001", "0044", "0100", "0400", "0644", "0755",
    "4000", "2000", "1000", "6000", "3000", "7000",
    "4004", "4044", "4644", "4755", "6755", "1755", "7777", "4645",
):
    case(mode)

wipe()
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"报告已写入 {REPORT}")
