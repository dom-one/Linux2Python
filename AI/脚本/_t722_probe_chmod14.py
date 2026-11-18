"""探针十四：细化「retained / changed」的判据（文件与目录分开看）。

已知：
  文件 (旧 0644): 4755/4644/4645/6755/1755/7777 -> retained
                   4000/4444/2000/1000/6000/3000/7000/4004/4044 -> changed
  目录 (旧 0755): 4000/4755 -> retained；0444/0644/0000 -> changed

候选规则：
  目标带特殊位时：
    文件 -> 只看「写位的有无」有没有变
    目录 -> 一律 retained（MSYS 的 stat 对目录恒报 0755，写位看不出来）
  目标不带特殊位时：
    比低 9 位是否一致

本轮把文件与目录各跑一批模式，逐条核对预测。
结果写进 AI/数据/chmod_probe14_report.txt。
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
DATA = AI_DIR / "数据" / "chmod_probe14"
REPORT = AI_DIR / "数据" / "chmod_probe14_report.txt"

lines: list[str] = []

MODES = [
    "0644", "0755", "0777", "0700", "0600", "0400", "0444", "0000", "0001", "0002",
    "0020", "0044", "0100", "0200", "0400", "0111", "0464", "0640", "0700",
    "4644", "2644", "1644", "6644", "4755", "6755", "1755", "7777", "4645", "4444",
    "4000", "2000", "1000", "6000", "3000", "7000", "4004", "4044", "4002", "4744",
    "4750", "0007", "0006", "0004", "0070", "0077", "0704",
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


def predict(old_mode: int, new_mode: int, is_dir: bool) -> str:
    if new_mode & 0o7000:
        if is_dir:
            return "retained"
        return "retained" if bool(old_mode & 0o222) == bool(new_mode & 0o222) else "changed"
    if bool(old_mode & 0o222) != bool(new_mode & 0o222):
        return "changed"
    return "retained" if (old_mode & 0o777) == (new_mode & 0o777) else "changed"


def main() -> int:
    say("=== 文件 ===")
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
            guess = predict(old_mode, mode, False)
            total += 1
            if gnu != guess:
                bad += 1
                say(f"  [不符] 文件 初始{old_state} 目标{mode_text}: GNU={gnu} 预测={guess}")
                say(f"          {out.strip()!r}")
    say("")

    say("=== 目录 ===")
    say("")
    for mode_text in MODES:
        mode = int(mode_text, 8)
        wipe()
        DATA.mkdir(parents=True, exist_ok=True)
        (DATA / "sub").mkdir()
        code, out, err = run(["chmod", "-v", mode_text, "sub"])
        gnu = "retained" if "retained as" in out else ("changed" if "changed from" in out else "?")
        guess = predict(0o755, mode, True)
        total += 1
        if gnu != guess:
            bad += 1
            say(f"  [不符] 目录 目标{mode_text}: GNU={gnu} 预测={guess}")
            say(f"          {out.strip()!r}")
    say("")
    say(f"=== 共 {total} 条，预测不符 {bad} 条 ===")
    wipe()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"报告已写入 {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
