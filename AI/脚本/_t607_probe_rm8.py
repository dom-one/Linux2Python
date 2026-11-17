"""探针第八轮：-f/-i/-I/--interactive 的组合语义，以及拒绝 descend 之后的行为。"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDBOX = HERE.parent / "数据" / "rm_probe8"
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

    # force 与 interactive 的组合语义
    case("-f --interactive=never 不存在", ["-f", "--interactive=never", "nope"], mkfile)
    case("--interactive=never -f 不存在", ["--interactive=never", "-f", "nope"], mkfile)
    case("-f -I 不存在", ["-f", "-I", "nope"], mkfile)
    case("-I -f 不存在", ["-I", "-f", "nope"], mkfile)
    case("-f --interactive=once 4文件", ["-f", "--interactive=once", "a.txt", "b.txt", "c.txt", "d.txt"], mk4files, "y\n")
    case("--interactive=once -f 4文件", ["--interactive=once", "-f", "a.txt", "b.txt", "c.txt", "d.txt"], mk4files, "y\n")
    case("-f --interactive=always 文件", ["-f", "--interactive=always", "a.txt"], mkfile, "y\n")
    case("--interactive=always -f 文件", ["--interactive=always", "-f", "a.txt"], mkfile, "y\n")
    case("-f -i 文件", ["-f", "-i", "a.txt"], mkfile, "y\n")
    case("-i -f 文件", ["-i", "-f", "a.txt"], mkfile, "y\n")

    # 拒绝 descend 之后：那棵子树还会不会问 remove directory
    case("-i -r 拒绝 descend sub", ["-i", "-r", "dir"], mkfull, "y\nn\nn\nn\nn\n")
    case("-i -r 拒绝 descend 顶层", ["-i", "-r", "dir"], mkfull, "n\nn\nn\nn\nn\n")

    # -i 下 -d 空目录与非空目录
    case("-i -d 空目录(答 y)", ["-i", "-d", "empty"], lambda r: (r / "empty").mkdir(), "y\n")

    # -v 的标签：路径带 ./ 前缀
    case("-v -r ./dir", ["-v", "-r", "./dir"], mkfull)
    case("-v 删 ./a.txt", ["-v", "./a.txt"], mkfile)

    _force_rmtree(SANDBOX)
    print("\n### DONE")


def main_wrapper():
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        main()
    text = buffer.getvalue()
    out_path = HERE.parent / "数据" / "rm_probe8_out.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"### WROTE {out_path} ({len(text)} chars)")


if __name__ == "__main__":
    main_wrapper()
