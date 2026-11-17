"""探针第十轮：-i -r 的提示序列（拒绝 descend 之后还会不会继续）。"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDBOX = HERE.parent / "数据" / "rm_probe10"
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
    prompts = err.count("? ")
    print("=" * 70)
    print(f"[{title}] argv={argv} stdin={stdin_text!r}")
    print(f"  rc      = {code}")
    print(f"  提示数  = {prompts}")
    print(f"  out     = {out!r}")
    print(f"  err     = {err!r}")
    print(f"  left    = {tree_state(root)}")


def main():
    SANDBOX.mkdir(parents=True, exist_ok=True)

    def mksub_only(root):
        d = root / "dir"
        (d / "sub").mkdir(parents=True)
        (d / "sub" / "f2.txt").write_text("y", encoding="utf-8")

    def mkfull(root):
        d = root / "dir"
        (d / "sub").mkdir(parents=True)
        (d / "f1.txt").write_text("x", encoding="utf-8")
        (d / "sub" / "f2.txt").write_text("y", encoding="utf-8")

    def mkflat(root):
        d = root / "dir"
        d.mkdir()
        (d / "f1.txt").write_text("x", encoding="utf-8")
        (d / "f2.txt").write_text("y", encoding="utf-8")

    # 拒绝 descend 之后还会不会继续提示
    case("只有sub: descend dir=y, descend sub=n", ["-i", "-r", "dir"], mksub_only, "y\nn\nn\nn\n")
    case("只有sub: descend dir=y, descend sub=y", ["-i", "-r", "dir"], mksub_only, "y\ny\ny\ny\n")
    case("完整: y,y,n,n,n,n", ["-i", "-r", "dir"], mkfull, "y\ny\nn\nn\nn\nn\n")
    case("完整: y,n,y,n,n,n,n", ["-i", "-r", "dir"], mkfull, "y\nn\ny\nn\nn\nn\n")
    case("扁平: y,y,n,y", ["-i", "-r", "dir"], mkflat, "y\ny\nn\ny\n")
    case("扁平: y,y,y", ["-i", "-r", "dir"], mkflat, "y\ny\ny\n")
    case("扁平: y,y,y,y,y", ["-i", "-r", "dir"], mkflat, "y\ny\ny\ny\ny\n")

    # -i 不带 -r 删目录
    case("-i 删目录(无-r)", ["-i", "dir"], mksub_only, "y\ny\ny\n")

    # -d 与 -i：非空目录
    case("-i -d 非空目录", ["-i", "-d", "dir"], mkfull, "y\ny\n")

    _force_rmtree(SANDBOX)
    print("\n### DONE")


def main_wrapper():
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        main()
    text = buffer.getvalue()
    out_path = HERE.parent / "数据" / "rm_probe10_out.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"### WROTE {out_path} ({len(text)} chars)")


if __name__ == "__main__":
    main_wrapper()
