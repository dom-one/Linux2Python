"""探针十三：验证「GNU 判定变了没变」的候选规则。

候选规则（从实测数据归纳出来的）：
    只读状态没变（目标模式与原模式的写位有无一致）时，
    目标模式带 setuid/setgid/sticky 任一位 -> 报 retained；
    否则比低 9 位（rwx）是否一致。

本轮把规则套到一批模式 × 初始状态上跑 GNU，逐条核对预测。
结果写进 AI/数据/chmod_probe13_report.txt。
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
DATA = AI_DIR / "数据" / "chmod_probe13"
REPORT = AI_DIR / "数据" / "chmod_probe13_report.txt"

lines: list[str] = []

MODES = [
    "0644", "0755", "0777", "0700", "0600", "0400", "0444", "0000", "0001", "0044",
    "0100", "0200", "0400", "0111", "0464", "0640", "0700", "0777",
    "4644", "2644", "1644", "6644", "4755", "6755", "1755", "7777", "4645", "4444",
    "4000", "2000", "1000", "6000", "3000", "7000", "4004", "4044", "4744", "4750",
]


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


def predict(old_mode: int, new_mode: int) -> str:
    writable_changed = bool(old_mode & 0o222) != bool(new_mode & 0o222)
    if writable_changed:
        return "changed"
    if new_mode & 0o7000:
        return "retained"
    return "retained" if (old_mode & 0o777) == (new_mode & 0o777) else "changed"


def main() -> int:
    say("=== 规则验证 ===")
    say("")
    bad = 0
    total = 0
    for old_state in ("可写", "只读"):
        for mode_text in MODES:
            mode = int(mode_text, 8)
            wipe()
            DATA.mkdir(parents=True, exist_ok=True)
            target = DATA / "a.txt"
            target.write_text("x\n", encoding="utf-8")
            if old_state == "只读":
                os.chmod(target, stat.S_IREAD)
            old_mode = 0o444 if old_state == "只读" else 0o644
            code, out, err = run(["chmod", "-v", mode_text, "a.txt"])
            gnu = "retained" if "retained as" in out else ("changed" if "changed from" in out else "?")
            guess = predict(old_mode, mode)
            total += 1
            mark = "OK " if gnu == guess else "不符"
            if gnu != guess:
                bad += 1
                say(f"  [{mark}] 初始{old_state} 目标{mode_text}: GNU={gnu} 预测={guess}")
                say(f"          GNU 原文: {out.strip()!r}")
    say("")
    say(f"=== 共 {total} 条，预测不符 {bad} 条 ===")
    wipe()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"报告已写入 {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
