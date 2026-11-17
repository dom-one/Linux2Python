"""探针第四轮：-I 提示的计数口径、'.'/'..' 守卫的适用范围、-d 与 -r 组合。"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDBOX = HERE.parent / "数据" / "rm_probe4"
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
    print(f"[{title}] argv={argv} stdin={stdin_text!r}")
    print(f"  rc    = {code}")
    print(f"  out   = {out!r}")
    print(f"  err   = {err!r}")
    print(f"  left  = {tree_state(root)}")


def main():
    SANDBOX.mkdir(parents=True, exist_ok=True)

    def mkfile(root):
        (root / "a.txt").write_text("hello\n", encoding="utf-8")

    def mk3files(root):
        for name in ("a.txt", "b.txt", "c.txt"):
            (root / name).write_text(name, encoding="utf-8")

    def mk4files(root):
        for name in ("a.txt", "b.txt", "c.txt", "d.txt"):
            (root / name).write_text(name, encoding="utf-8")

    def mkfile_and_dir(root):
        (root / "a.txt").write_text("hello\n", encoding="utf-8")
        (root / "dir").mkdir()

    def mksub(root):
        d = root / "sub"
        d.mkdir()
        (d / "f.txt").write_text("x", encoding="utf-8")

    def mkfull(root):
        d = root / "dir"
        (d / "sub").mkdir(parents=True)
        (d / "f1.txt").write_text("x", encoding="utf-8")
        (d / "sub" / "f2.txt").write_text("y", encoding="utf-8")

    # -I 计数口径
    case("-I 3个文件", ["-I", "a.txt", "b.txt", "c.txt"], mk3files, "y\n")
    case("-I 4个文件", ["-I", "a.txt", "b.txt", "c.txt", "d.txt"], mk4files, "y\n")
    case("-I -r 1个文件(无目录)", ["-I", "-r", "a.txt"], mkfile, "y\n")
    case("-I -r 3个文件(无目录)", ["-I", "-r", "a.txt", "b.txt", "c.txt"], mk3files, "y\n")
    case("-I -r 文件+目录", ["-I", "-r", "a.txt", "dir"], mkfile_and_dir, "y\n")
    case("-I -r 目录+文件", ["-I", "-r", "dir", "a.txt"], mkfile_and_dir, "y\n")
    case("-I 4个(3文件1目录)", ["-I", "a.txt", "b.txt", "c.txt", "dir"], mkfile_and_dir, "y\n")
    case("-I -r 1目录2文件", ["-I", "-r", "dir", "a.txt", "b.txt"], mkfile_and_dir, "y\n")

    # '.' '..' 守卫范围
    case("-r 删 sub/.", ["-r", "sub/."], mksub)
    case("-r 删 sub/..", ["-r", "sub/.."], mksub)
    case("-r 删 ./", ["-r", "./"], mkfile)
    case("-r 删 ../", ["-r", "../"], mkfile)
    case("-rv 删 .", ["-r", "-v", "."], mkfile)

    # -d 与 -r 组合
    case("-d -r 删非空目录", ["-d", "-r", "dir"], mkfull)
    case("-r -d 删非空目录", ["-r", "-d", "dir"], mkfull)

    # -i 拒绝 descend 之后父目录还在
    case("-i -r 拒绝 descend(嵌套)", ["-i", "-r", "dir"], mkfull, "y\nn\ny\ny\ny\n")

    # -i 对顶层目录（非递归）
    case("-i 删目录(无-r)", ["-i", "dir"], mkfile_and_dir, "y\n")

    # -v 与 -i 同时
    case("-i -v 删文件", ["-i", "-v", "a.txt"], mkfile, "y\n")

    _force_rmtree(SANDBOX)
    print("\n### DONE")


def main_wrapper():
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        main()
    text = buffer.getvalue()
    out_path = HERE.parent / "数据" / "rm_probe4_out.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"### WROTE {out_path} ({len(text)} chars)")


if __name__ == "__main__":
    main_wrapper()
