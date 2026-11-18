"""chmod 与 GNU 的差分对照。

做法：造两份一模一样的夹具，一份给 GNU 的 chmod，一份给本项目的 chmod，
然后逐项比对：

- 标准输出（-v 的那几行）要逐字节一致
- 标准错误：只比「有没有错」（本项目用中文文案，GNU 用英文）
- 退出码：只比「成功 / 失败」（本项目出错返回 2，GNU 返回 1）
- 每个文件最后的只读状态要一致（这是 Windows 上唯一能落盘的权限位）

结果写进 AI/数据/chmod_diff_report.txt。
"""

from __future__ import annotations

import io
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
ROOT = AI_DIR.parent
BASE = AI_DIR / "数据" / "chmod_diff"
REPORT = AI_DIR / "数据" / "chmod_diff_report.txt"

sys.path.insert(0, str(ROOT))

from w2l.commands.chmod import build_parser  # noqa: E402
from w2l.commands.chmod import chmod  # noqa: E402
from w2l.context import RunContext  # noqa: E402

lines: list[str] = []
mismatches = 0


def say(text: str = "") -> None:
    lines.append(text)


def wipe(path: Path) -> None:
    if not path.exists():
        return
    for item in path.rglob("*"):
        try:
            os.chmod(item, stat.S_IREAD | stat.S_IWRITE)
        except OSError:
            pass
    try:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    except OSError:
        pass
    shutil.rmtree(path, ignore_errors=True)


def build_fixture(root: Path, readonly: tuple[str, ...] = ()) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.txt").write_text("alpha\n", encoding="utf-8")
    (root / "b.txt").write_text("beta\n", encoding="utf-8")
    sub = root / "sub"
    sub.mkdir()
    (sub / "inner.txt").write_text("inner\n", encoding="utf-8")
    deep = sub / "deep"
    deep.mkdir()
    (deep / "leaf.txt").write_text("leaf\n", encoding="utf-8")
    for name in readonly:
        os.chmod(root / name, stat.S_IREAD)


def run_gnu(args: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["chmod", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_ours(args: list[str], cwd: Path) -> tuple[int, str, str]:
    namespace = build_parser().parse_args(list(args))
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(cwd=cwd, stdout=out, stderr=err, stdin=io.StringIO(""))
    code = chmod(namespace, ctx)
    return code, out.getvalue(), err.getvalue()


def readonly_state(root: Path) -> dict[str, bool]:
    """每个文件是不是只读（True = 只读）。"""
    state: dict[str, bool] = {}
    for item in sorted(root.rglob("*")):
        if item.is_dir():
            continue
        mode = os.stat(item).st_mode
        state[item.relative_to(root).as_posix()] = not (mode & stat.S_IWRITE)
    return state


def scenario(
    label: str,
    args: list[str],
    readonly: tuple[str, ...] = (),
    recursive: bool = False,
) -> None:
    global mismatches
    gnu_dir = BASE / "gnu" / label.replace(" ", "_").replace("/", "_")
    our_dir = BASE / "our" / label.replace(" ", "_").replace("/", "_")
    wipe(gnu_dir)
    wipe(our_dir)
    build_fixture(gnu_dir, readonly)
    build_fixture(our_dir, readonly)

    gcode, gout, gerr = run_gnu(args, gnu_dir)
    ocode, oout, oerr = run_ours(args, our_dir)

    problems: list[str] = []
    if recursive:
        if sorted(gout.splitlines()) != sorted(oout.splitlines()):
            problems.append(f"stdout 不一致（按集合比）\n    GNU: {gout!r}\n    本项目: {oout!r}")
    elif gout != oout:
        problems.append(f"stdout 不一致\n    GNU: {gout!r}\n    本项目: {oout!r}")
    if bool(gerr.strip()) != bool(oerr.strip()):
        problems.append(f"有无错误不一致\n    GNU: {gerr.strip()!r}\n    本项目: {oerr.strip()!r}")
    if (gcode == 0) != (ocode == 0):
        problems.append(f"成败不一致\n    GNU rc={gcode} 本项目 rc={ocode}")
    gstate = readonly_state(gnu_dir)
    ostate = readonly_state(our_dir)
    if gstate != ostate:
        problems.append(f"只读状态不一致\n    GNU: {gstate}\n    本项目: {ostate}")

    if problems:
        mismatches += 1
        say(f"--- 不一致: {label}  ($ chmod {' '.join(args)})")
        for problem in problems:
            say(f"    {problem}")
    else:
        say(f"--- 一致: {label}  ($ chmod {' '.join(args)})")
    say("")


def main() -> int:
    wipe(BASE)
    say("=== chmod 差分对照 ===")
    say("")

    cases = [
        ("八进制-可写文件", ["644", "a.txt"], (), False),
        ("八进制-设只读", ["444", "a.txt"], (), False),
        ("八进制-属主可写", ["600", "a.txt"], (), False),
        ("八进制-全零", ["000", "a.txt"], (), False),
        ("八进制-755", ["755", "a.txt"], (), False),
        ("八进制-777", ["777", "a.txt"], (), False),
        ("八进制-前导零", ["0644", "a.txt"], (), False),
        ("八进制-一位", ["7", "a.txt"], (), False),
        ("八进制-只有other可执行", ["001", "a.txt"], (), False),
        ("八进制-只有other可写", ["002", "a.txt"], (), False),
        ("八进制-只有other全权", ["007", "a.txt"], (), False),
        ("八进制-只有owner可写", ["020", "a.txt"], (), False),
        ("八进制-只有owner可读", ["040", "a.txt"], (), False),
        ("八进制-只有group可写", ["060", "a.txt"], (), False),
        ("八进制-前导零三位", ["0700", "a.txt"], (), False),
        ("只读文件-改成可写", ["644", "a.txt"], ("a.txt",), False),
        ("只读文件-保持只读", ["444", "a.txt"], ("a.txt",), False),
        ("只读文件-改成600", ["600", "a.txt"], ("a.txt",), False),
        ("符号-u减w", ["u-w", "a.txt"], (), False),
        ("符号-a减w", ["a-w", "a.txt"], (), False),
        ("符号-u加w", ["u+w", "a.txt"], (), False),
        ("符号-a加w", ["a+w", "a.txt"], (), False),
        ("符号-u加x", ["u+x", "a.txt"], (), False),
        ("符号-a加x", ["a+x", "a.txt"], (), False),
        ("符号-a加X", ["a+X", "a.txt"], (), False),
        ("符号-只读文件加X", ["a+X", "a.txt"], ("a.txt",), False),
        ("符号-u加s", ["u+s", "a.txt"], (), False),
        ("符号-g加s", ["g+s", "a.txt"], (), False),
        ("符号-加t", ["+t", "a.txt"], (), False),
        ("符号-a加s", ["a+s", "a.txt"], (), False),
        ("符号-g等于u", ["g=u", "a.txt"], (), False),
        ("符号-u等于g", ["u=g", "a.txt"], (), False),
        ("符号-o等于g", ["o=g", "a.txt"], (), False),
        ("符号-组合子句", ["u+rw,go-w", "a.txt"], (), False),
        ("符号-先减后加", ["a-w,u+w", "a.txt"], (), False),
        ("符号-复制写法无效果", ["u+g", "a.txt"], (), False),
        ("符号-g等于u且o清空", ["g=u,o=", "a.txt"], (), False),
        ("符号-o清空", ["o=", "a.txt"], (), False),
        ("符号-u清空", ["u=", "a.txt"], (), False),
        ("符号-a清空", ["a=", "a.txt"], (), False),
        ("符号-u空加号", ["u+", "a.txt"], (), False),
        ("符号-空权限组合", ["u+r,g=", "a.txt"], (), False),
        ("符号-结尾逗号非法", ["u+r,", "a.txt"], (), False),
        ("目录-改成644", ["644", "sub"], (), False),
        ("目录-改成400", ["400", "sub"], (), False),
        ("目录-改成755", ["755", "sub"], (), False),
        ("verbose-没变化", ["-v", "644", "a.txt"], (), False),
        ("verbose-有变化", ["-v", "444", "a.txt"], (), False),
        ("verbose-只读文件", ["-v", "644", "a.txt"], ("a.txt",), False),
        ("changes-只报变化的", ["-c", "444", "a.txt", "b.txt"], (), False),
        ("verbose加changes", ["-v", "-c", "444", "a.txt"], (), False),
        ("verbose-多文件", ["-v", "644", "a.txt", "b.txt"], (), False),
        ("verbose-缺失文件", ["-v", "644", "missing.txt"], (), False),
        ("verbose-缺失文件跟在前一个后面", ["-v", "444", "a.txt", "missing.txt"], (), False),
        ("verbose-缺失文件跟只读文件后面", ["-v", "644", "a.txt", "b.txt", "missing.txt"], ("b.txt",), False),
        ("verbose-缺失文件跟在目录后面", ["-v", "755", "sub", "missing.txt"], (), False),
        ("缺失文件", ["644", "missing.txt"], (), False),
        ("silent-缺失文件", ["-f", "644", "missing.txt"], (), False),
        ("reference-只读参照", ["--reference=a.txt", "b.txt"], ("a.txt",), False),
        ("reference-可写参照", ["--reference=a.txt", "b.txt"], (), False),
        ("递归-700", ["-R", "700", "sub"], (), True),
        ("递归-444", ["-R", "444", "sub"], (), True),
        ("递归-verbose", ["-v", "-R", "700", "sub"], (), True),
        ("递归-单文件", ["-R", "644", "a.txt"], (), False),
        ("多个操作数", ["644", "a.txt", "b.txt"], (), False),
    ]

    for label, args, readonly, recursive in cases:
        scenario(label, args, readonly, recursive)

    say(f"=== 共 {len(cases)} 组，不一致 {mismatches} 组 ===")
    wipe(BASE)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"报告已写入 {REPORT}")
    return 0 if mismatches == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
