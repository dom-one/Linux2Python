"""探针三：钉死 GNU chmod 的「请求模式 -> 实际落盘状态 -> -v 文案」映射。

探针二里有一条 `chmod -R 755 /`，在 MSYS 上 / 是 Git 安装根目录，
MSYS 的 chmod 会真的改只读属性，这条已经被删掉了（改由 _t702 做取证）。

本轮只查映射关系：
- 目标模式里的属主写位是不是唯一决定「只读 / 可写」的位
- -v 报出来的 from/to 数字分别是什么
- 目录的 from/to 是什么

结果写进 AI/数据/chmod_probe3_report.txt。
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
DATA = AI_DIR / "数据" / "chmod_probe3"
REPORT = AI_DIR / "数据" / "chmod_probe3_report.txt"

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


def force_rmtree(path: Path) -> None:
    if not path.exists():
        return
    for item in path.rglob("*"):
        try:
            os.chmod(item, stat.S_IREAD | stat.S_IWRITE)
        except OSError:
            pass
    shutil.rmtree(path, ignore_errors=True)


def gnu_mode(name: str) -> str:
    code, out, err = run(["stat", "-c", "%a %A", name], cwd=DATA)
    return out.strip() or f"<rc={code} err={err.strip()}>"


def py_view(name: str) -> str:
    path = DATA / name
    try:
        st = os.stat(path)
    except OSError as exc:
        return f"<stat 失败: {exc}>"
    mode = stat.S_IMODE(st.st_mode)
    try:
        with open(path, "a", encoding="utf-8"):
            return f"py={mode:04o} 可写"
    except OSError:
        return f"py={mode:04o} 只读"


def fixture() -> None:
    force_rmtree(DATA)
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "f.txt").write_text("hello\n", encoding="utf-8")
    (DATA / "g.txt").write_text("hello\n", encoding="utf-8")
    sub = DATA / "sub"
    sub.mkdir()
    (sub / "inner.txt").write_text("inner\n", encoding="utf-8")


def case(label: str, setup: list[str], chmod_cmd: list[str], target: str) -> None:
    fixture()
    for cmd in setup:
        run(cmd, cwd=DATA)
    before = gnu_mode(target)
    code, out, err = run(chmod_cmd, cwd=DATA)
    say(f"--- {label}")
    say(f"    命令: {' '.join(chmod_cmd)}")
    say(f"    前: {before}")
    say(f"    rc={code}")
    if out:
        say("    stdout: " + out.replace("\n", "\n      ").rstrip())
    if err:
        say("    stderr: " + err.replace("\n", "\n      ").rstrip())
    say(f"    后: GNU={gnu_mode(target)} | {py_view(target)}")
    say("")


def main() -> int:
    say("=== 目标模式矩阵（文件，初始可写） ===")
    say("")
    for mode in (
        "000", "111", "200", "400", "444", "600", "640", "644", "700", "755", "777",
        "u-w", "a-w", "u+w", "a+w", "u+x", "a+x", "g+w", "g-w", "o+w", "a=rwx",
        "u=rw,go=r", "a-w,u+w",
    ):
        case(
            f"chmod -v {mode} f.txt（初始可写）",
            [],
            ["chmod", "-v", mode, "f.txt"],
            "f.txt",
        )

    say("=== 目标模式矩阵（文件，初始只读） ===")
    say("")
    for mode in ("000", "400", "444", "600", "644", "700", "755", "u-w", "a-w", "u+w", "a+x", "g+w"):
        case(
            f"chmod -v {mode} f.txt（初始只读）",
            [["chmod", "444", "f.txt"]],
            ["chmod", "-v", mode, "f.txt"],
            "f.txt",
        )

    say("=== 目录 ===")
    say("")
    for mode in ("000", "400", "444", "600", "700", "755", "777", "u-w", "a-w", "u+w"):
        case(
            f"chmod -v {mode} sub（目录）",
            [],
            ["chmod", "-v", mode, "sub"],
            "sub",
        )

    say("=== 递归 ===")
    say("")
    case(
        "chmod -v -R 700 sub（看目录）",
        [],
        ["chmod", "-v", "-R", "700", "sub"],
        "sub",
    )
    case(
        "chmod -v -R 700 sub（看子文件）",
        [],
        ["chmod", "-v", "-R", "700", "sub"],
        "sub/inner.txt",
    )
    case(
        "chmod -v -R 444 sub（看子文件）",
        [],
        ["chmod", "-v", "-R", "444", "sub"],
        "sub/inner.txt",
    )

    say("=== --reference ===")
    say("")
    case(
        "--reference=f.txt g.txt（f 是 644 状态）",
        [],
        ["chmod", "-v", "--reference=f.txt", "g.txt"],
        "g.txt",
    )

    say("=== 多操作数与 -c ===")
    say("")
    fixture()
    run(["chmod", "444", "f.txt"], cwd=DATA)
    code, out, err = run(["chmod", "-v", "-c", "644", "f.txt", "g.txt"], cwd=DATA)
    say("  $ chmod -v -c 644 f.txt g.txt（f 只读、g 可写）")
    say(f"    rc={code}")
    say("    stdout: " + out.replace("\n", "\n      ").rstrip())
    say("    stderr: " + err.replace("\n", "\n      ").rstrip())
    say(f"    f: {gnu_mode('f.txt')} | g: {gnu_mode('g.txt')}")
    say("")

    fixture()
    code, out, err = run(["chmod", "-v", "644", "f.txt", "g.txt", "missing.txt"], cwd=DATA)
    say("  $ chmod -v 644 f.txt g.txt missing.txt")
    say(f"    rc={code}")
    say("    stdout: " + out.replace("\n", "\n      ").rstrip())
    say("    stderr: " + err.replace("\n", "\n      ").rstrip())
    say("")

    fixture()
    code, out, err = run(["chmod", "-v", "644", "f.txt", "sub"], cwd=DATA)
    say("  $ chmod -v 644 f.txt sub（操作数是目录）")
    say(f"    rc={code}")
    say("    stdout: " + out.replace("\n", "\n      ").rstrip())
    say("    stderr: " + err.replace("\n", "\n      ").rstrip())
    say("")

    force_rmtree(DATA)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"报告已写入 {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
