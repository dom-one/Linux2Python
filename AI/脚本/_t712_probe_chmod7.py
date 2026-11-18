"""探针七：补两处 GNU 规则的细节。

1. 只读属性的判定到底看哪个写位：owner-w、任意写位，还是别的？
   （差分对照发现 chmod 7 = 0007 时 GNU 没有设只读，而本实现设了）
2. 空的权限串（"o="、"u+"、"a="）GNU 收不收
3. 打不开的文件报的「原模式」是不是上一个处理过的文件的新模式

结果写进 AI/数据/chmod_probe7_report.txt。
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
DATA = AI_DIR / "数据" / "chmod_probe7"
REPORT = AI_DIR / "数据" / "chmod_probe7_report.txt"

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


def fixture() -> None:
    wipe()
    DATA.mkdir(parents=True, exist_ok=True)
    for name in ("a.txt", "b.txt", "c.txt"):
        (DATA / name).write_text("x\n", encoding="utf-8")


def readonly(name: str) -> str:
    mode = os.stat(DATA / name).st_mode
    return "只读" if not (mode & stat.S_IWRITE) else "可写"


say("=== 目标模式里的哪个写位决定只读 ===")
say("")
for mode in ("000", "001", "002", "004", "007", "020", "0020", "0002", "040", "0040", "0004",
             "060", "006", "0060", "066", "070", "007", "077", "0700", "0007", "0707", "0701"):
    fixture()
    code, out, err = run(["chmod", mode, "a.txt"])
    gnu = run(["stat", "-c", "%a", "a.txt"])[1].strip()
    say(f"  chmod {mode:>5} -> GNU stat={gnu} 本机属性={readonly('a.txt')} rc={code}")
say("")

say("=== 空的权限串 ===")
say("")
for spec in ("o=", "u+", "a=", "g=u,o=", "u=", "a+", "u+r,", ",u+r", "u+r,g="):
    fixture()
    code, out, err = run(["chmod", "-v", spec, "a.txt"])
    say(f"  chmod -v {spec!r} -> rc={code}")
    if out:
        say("    stdout: " + out.replace("\n", "\n      ").rstrip())
    if err:
        say("    stderr: " + err.replace("\n", "\n      ").rstrip())
say("")

say("=== 缺失文件的「原模式」跟谁走 ===")
say("")
for setup, args in (
    ([], ["-v", "644", "missing.txt"]),
    ([], ["-v", "444", "a.txt", "missing.txt"]),
    ([], ["-v", "600", "a.txt", "missing.txt"]),
    ([], ["-v", "444", "a.txt", "644", "b.txt", "missing.txt"]),
    ([], ["-v", "444", "a.txt", "400", "b.txt", "missing.txt"]),
    ([], ["-v", "755", "sub", "missing.txt"]),
):
    fixture()
    (DATA / "sub").mkdir()
    code, out, err = run(["chmod", *args])
    say(f"  $ chmod {' '.join(args)}")
    say("    stdout: " + out.replace("\n", "\n      ").rstrip())
say("")

wipe()
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"报告已写入 {REPORT}")
