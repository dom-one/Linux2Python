"""探针第七轮：--interactive 的三种取值、-f 与 -i 的组合次序。"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDBOX = HERE.parent / "数据" / "rm_probe7"
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

    def mkempty(root):
        (root / "empty").mkdir()

    def mkfull(root):
        d = root / "dir"
        (d / "sub").mkdir(parents=True)
        (d / "f1.txt").write_text("x", encoding="utf-8")
        (d / "sub" / "f2.txt").write_text("y", encoding="utf-8")

    case("--interactive=never 删不存在的", ["--interactive=never", "nope"], mkfile)
    case("--interactive=once 4个文件", ["--interactive=once", "a.txt", "b.txt", "c.txt", "d.txt"], mk4files, "y\n")
    case("--interactive=once 3个文件", ["--interactive=once", "a.txt", "b.txt", "c.txt"], mk4files, "y\n")
    case("--interactive=once -r", ["--interactive=once", "-r", "dir"], mkfull, "y\n")
    case("--interactive=always 删目录(无-r)", ["--interactive=always", "dir"], mkfull, "y\n")
    case("-f -i 删不存在的", ["-f", "-i", "nope"], mkfile)
    case("-i -f 删不存在的", ["-i", "-f", "nope"], mkfile)
    case("-I -f 4个文件", ["-I", "-f", "a.txt", "b.txt", "c.txt", "d.txt"], mk4files, "")
    case("-f -I 4个文件", ["-f", "-I", "a.txt", "b.txt", "c.txt", "d.txt"], mk4files, "")
    case("-d 空目录 + -i -I", ["-d", "-i", "-I", "empty"], mkempty, "y\n")
    case("-r -v 删只读目录里的只读文件", ["-r", "-v", "dir"], mkfull)
    case("-f 删空目录(无-d无-r)", ["-f", "empty"], mkempty)
    case("-i 删只读文件", ["-i", "a.txt"], mkfile, "y\n")

    _force_rmtree(SANDBOX)
    print("\n### DONE")


def main_wrapper():
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        main()
    text = buffer.getvalue()
    out_path = HERE.parent / "数据" / "rm_probe7_out.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"### WROTE {out_path} ({len(text)} chars)")


if __name__ == "__main__":
    main_wrapper()
