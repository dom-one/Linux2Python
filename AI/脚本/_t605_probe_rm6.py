"""探针第六轮：'.'/'..' 守卫的判定口径，以及 -d 与点路径、--help/-h 的行为。"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDBOX = HERE.parent / "数据" / "rm_probe6"
GNU_RM = r"E:\software\Git\Git\usr\bin\rm.exe"


def run(argv, cwd, stdin_text=""):
    proc = subprocess.run(
        [GNU_RM, *argv],
        cwd=str(cwd),
        input=stdin_text.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", "replace"),
        proc.stderr.decode("utf-8", "replace"),
    )


def fresh(name):
    root = SANDBOX / name
    if root.exists():
        _force_rmtree(root)
    root.mkdir(parents=True)
    return root


def _force_rmtree(root):
    def onerror(func, path, exc):
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass
        try:
            func(path)
        except OSError:
            pass

    shutil.rmtree(root, ignore_errors=False, onerror=onerror)


def tree_state(root):
    items = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            items.append("F " + str(Path(dirpath, name).relative_to(root)).replace("\\", "/"))
        for name in sorted(dirnames):
            items.append("D " + str(Path(dirpath, name).relative_to(root)).replace("\\", "/"))
    return items


def case(title, argv, setup=None, stdin_text=""):
    root = fresh("c")
    if setup:
        setup(root)
    code, out, err = run(argv, root, stdin_text)
    print("=" * 70)
    print(f"[{title}] argv={argv}")
    print(f"  rc    = {code}")
    print(f"  out   = {out!r}")
    print(f"  err   = {err!r}")
    print(f"  left  = {tree_state(root)}")


def main():
    SANDBOX.mkdir(parents=True, exist_ok=True)

    def mkfile(root):
        (root / "a.txt").write_text("hello\n", encoding="utf-8")

    def mksub(root):
        d = root / "sub"
        d.mkdir()
        (d / "f.txt").write_text("x", encoding="utf-8")

    def mkboth(root):
        (root / "a.txt").write_text("hello\n", encoding="utf-8")
        d = root / "sub"
        d.mkdir()
        (d / "f.txt").write_text("x", encoding="utf-8")

    # '.'/'..' 守卫的判定口径
    case("-r sub/./.", ["-r", "sub/./."], mksub)
    case("-r ./sub/.", ["-r", "./sub/."], mksub)
    case("-r a/../sub", ["-r", "a/../sub"], mkboth)
    case("-r sub/../sub", ["-r", "sub/../sub"], mksub)
    case("-d .", ["-d", "."], mkfile)
    case("-d ..", ["-d", ".."], mkfile)
    case("-d ./", ["-d", "./"], mkfile)
    case("-r .", ["-r", "."], mkfile)
    case("-r ..", ["-r", ".."], mkfile)
    case("-rf ./", ["-r", "-f", "./"], mkfile)
    case("-v -r sub/.", ["-v", "-r", "sub/."], mksub)

    # -h 与 --help
    case("-h", ["-h"], mkfile)
    case("--help 截断", ["--help"], mkfile)

    # --interactive=never 无操作数
    case("--interactive=never 无操作数", ["--interactive=never"], mkfile)

    # 空字符串操作数
    case("空操作数 + -f", ["-f", ""], mkfile)

    # 带尾斜杠的普通文件
    case("带尾斜杠的文件", ["a.txt/"], mkfile)

    # 目标是不存在的路径的父目录
    case("删不存在路径的父目录", ["-r", "nodir/"], mkfile)

    _force_rmtree(SANDBOX)
    print("\n### DONE")


def main_wrapper():
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        main()
    text = buffer.getvalue()
    out_path = HERE.parent / "数据" / "rm_probe6_out.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"### WROTE {out_path} ({len(text)} chars)")


if __name__ == "__main__":
    main_wrapper()
