"""探针八：定死「打不开的文件报的原模式」这条规则。

候选规则：
  A) 恒为 0644（GNU 的默认模式），目录因为默认是 0755 所以报 0755
  B) 跟着上一个处理过的文件走（取它的旧模式或新模式）

用「上一个文件的旧模式和新模式都不同」的场景来区分。
结果写进 AI/数据/chmod_probe8_report.txt。
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
DATA = AI_DIR / "数据" / "chmod_probe8"
REPORT = AI_DIR / "数据" / "chmod_probe8_report.txt"

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


def fixture(readonly_a: bool = False, readonly_b: bool = False) -> None:
    wipe()
    DATA.mkdir(parents=True, exist_ok=True)
    for name in ("a.txt", "b.txt"):
        (DATA / name).write_text("x\n", encoding="utf-8")
    (DATA / "sub").mkdir()
    if readonly_a:
        os.chmod(DATA / "a.txt", stat.S_IREAD)
    if readonly_b:
        os.chmod(DATA / "b.txt", stat.S_IREAD)


def case(label: str, args: list[str], readonly_a: bool = False, readonly_b: bool = False) -> None:
    fixture(readonly_a, readonly_b)
    code, out, err = run(["chmod", "-v", *args])
    say(f"--- {label}")
    say(f"    $ chmod -v {' '.join(args)}   (a 只读={readonly_a}, b 只读={readonly_b})")
    say("    stdout: " + out.replace("\n", "\n      ").rstrip())
    say("")


say("=== 缺失文件的「原模式」 ===")
say("")
case("a 可写 -> 400（a 旧 0644 新 0400）", ["400", "a.txt", "missing.txt"])
case("a 只读 -> 644（a 旧 0444 新 0644）", ["644", "a.txt", "missing.txt"], readonly_a=True)
case("a 只读 -> 400（a 旧 0444 新 0400）", ["400", "a.txt", "missing.txt"], readonly_a=True)
case("a 只读 -> 000（a 旧 0444 新 0000）", ["000", "a.txt", "missing.txt"], readonly_a=True)
case("b 只读，a 可写 -> 644", ["644", "a.txt", "b.txt", "missing.txt"], readonly_b=True)
case("目录 755 -> 644（sub 旧 0755 新 0644）", ["644", "sub", "missing.txt"])
case("只读文件 444 -> 755", ["755", "a.txt", "missing.txt"], readonly_a=True)

wipe()
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"报告已写入 {REPORT}")
