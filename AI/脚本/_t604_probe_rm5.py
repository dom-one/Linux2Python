"""探针第五轮：-I 的提示条件、-d 的提示与报错、拒绝 descend 之后的行为。"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDBOX = HERE.parent / "数据" / "rm_probe5"
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

    def mk4files(root):
        for name in ("a.txt", "b.txt", "c.txt", "d.txt"):
            (root / name).write_text(name, encoding="utf-8")

    def mkfull(root):
        d = root / "dir"
        (d / "sub").mkdir(parents=True)
        (d / "f1.txt").write_text("x", encoding="utf-8")
        (d / "sub" / "f2.txt").write_text("y", encoding="utf-8")

    def mkempty(root):
        (root / "empty").mkdir()

    # -I 的提示条件
    case("-I -r 4个文件", ["-I", "-r", "a.txt", "b.txt", "c.txt", "d.txt"], mk4files, "y\n")
    case("-I -r 0个目录(1文件)", ["-I", "-r", "a.txt"], mkfile, "y\n")
    case("-I -r 答 n", ["-I", "-r", "dir"], mkfull, "n\n")

    # -d 的提示与报错
    case("-i -d 非空目录", ["-i", "-d", "dir"], mkfull, "y\n")
    case("-dv 非空目录", ["-d", "-v", "dir"], mkfull)
    case("-f -d 非空目录", ["-f", "-d", "dir"], mkfull)
    case("-i -d 空目录(答 n)", ["-i", "-d", "empty"], mkempty, "n\n")

    # 拒绝 descend 之后
    case("-i -r 拒绝 descend sub", ["-i", "-r", "dir"], mkfull, "y\nn\ny\ny\ny\nn\n")
    case("-i -r 拒绝删除顶层目录", ["-i", "-r", "dir"], mkfull, "y\ny\ny\ny\ny\nn\n")
    case("-i -r 拒绝删除普通文件", ["-i", "-r", "dir"], mkfull, "y\nn\ny\ny\ny\ny\n")

    # -v 的目录措辞
    case("-v -d 空目录", ["-v", "-d", "empty"], mkempty)
    case("-v -r 目录", ["-v", "-r", "dir"], mkfull)

    # 递归里的只读子目录
    def mkro_subdir(root):
        d = root / "dir"
        (d / "sub").mkdir(parents=True)
        (d / "sub" / "f.txt").write_text("x", encoding="utf-8")
        os.chmod(d / "sub", 0o555)

    case("-r 删含只读子目录", ["-r", "dir"], mkro_subdir)

    _force_rmtree(SANDBOX)
    print("\n### DONE")


def main_wrapper():
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        main()
    text = buffer.getvalue()
    out_path = HERE.parent / "数据" / "rm_probe5_out.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"### WROTE {out_path} ({len(text)} chars)")


if __name__ == "__main__":
    main_wrapper()
