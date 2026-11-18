"""探针六：补最后两处语义。

1. 缺失文件的 "failed to change mode of 'X' from ??" —— from 到底是哪来的
   （探针一显示像是第一个文件的模式，探针三显示像是 0444，需要定死）
2. 符号模式的复制写法（u+g / g=u / o=g）与 X、s、t 的落法
3. -R 的输出顺序

结果写进 AI/数据/chmod_probe6_report.txt。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
DATA = AI_DIR / "数据" / "chmod_probe6"
REPORT = AI_DIR / "数据" / "chmod_probe6_report.txt"

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


def show(label: str, cmd: list[str]) -> None:
    code, out, err = run(cmd, cwd=DATA)
    say(f"  {label}")
    say(f"    $ {' '.join(cmd)}")
    say(f"    rc={code}")
    if out:
        say("    stdout: " + out.replace("\n", "\n      ").rstrip())
    if err:
        say("    stderr: " + err.replace("\n", "\n      ").rstrip())
    say("")


def wipe() -> None:
    """删目录前先清只读属性（Windows 上只读文件会挡住 rmtree）。"""
    if not DATA.exists():
        return
    import stat as _stat

    for item in DATA.rglob("*"):
        try:
            os.chmod(item, _stat.S_IREAD | _stat.S_IWRITE)
        except OSError:
            pass
    shutil.rmtree(DATA, ignore_errors=True)


def fixture() -> None:
    wipe()
    DATA.mkdir(parents=True, exist_ok=True)
    for name in ("a.txt", "b.txt", "c.txt"):
        (DATA / name).write_text("x\n", encoding="utf-8")
    sub = DATA / "sub"
    sub.mkdir()
    (sub / "in1.txt").write_text("x\n", encoding="utf-8")
    deep = sub / "deep"
    deep.mkdir()
    (deep / "leaf.txt").write_text("x\n", encoding="utf-8")


def main() -> int:
    say("=== 缺失文件的 from 是什么 ===")
    say("")
    fixture()
    show("a 可写、b 只读", ["chmod", "-v", "644", "a.txt", "b.txt", "missing.txt"])
    fixture()
    run(["chmod", "444", "a.txt"], cwd=DATA)
    show("a 只读、b 可写", ["chmod", "-v", "644", "a.txt", "b.txt", "missing.txt"])
    fixture()
    run(["chmod", "444", "b.txt"], cwd=DATA)
    show("a 可写、b 只读（换位置）", ["chmod", "-v", "644", "b.txt", "a.txt", "missing.txt"])
    fixture()
    show("只有一个文件 + 缺失", ["chmod", "-v", "644", "a.txt", "missing.txt"])
    fixture()
    show("缺失在第一个", ["chmod", "-v", "644", "missing.txt", "a.txt"])
    say("")

    say("=== 符号模式细节 ===")
    say("")
    for spec in (
        "u+g", "g=u", "o=g", "u=g", "a+X", "u+X", "X", "u+s", "g+s", "+t", "a+s",
        "u+rw,go-w", "a-w,u+w", "u=rw", "g=u,o=",
    ):
        fixture()
        show(f"chmod -v {spec} a.txt（a 初始 644）", ["chmod", "-v", spec, "a.txt"])

    say("=== 符号模式在只读文件上 ===")
    for spec in ("u+x", "a+x", "X", "u+s"):
        fixture()
        run(["chmod", "444", "a.txt"], cwd=DATA)
        show(f"chmod -v {spec} a.txt（a 初始 444）", ["chmod", "-v", spec, "a.txt"])

    say("=== -R 的输出顺序 ===")
    say("")
    fixture()
    show("chmod -v -R 700 sub", ["chmod", "-v", "-R", "700", "sub"])
    fixture()
    show("chmod -v -R 444 sub", ["chmod", "-v", "-R", "444", "sub"])

    shutil.rmtree(DATA, ignore_errors=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"报告已写入 {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
