"""探针第九轮：-f 与 -i/-I/--interactive 的组合口径，以及应答解析。"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDBOX = HERE.parent / "数据" / "rm_probe9"
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

    # 无操作数时，-f 与 -i/-I/--interactive 的组合
    case("-f -i 无操作数", ["-f", "-i"], mkfile)
    case("-i -f 无操作数", ["-i", "-f"], mkfile)
    case("-f -I 无操作数", ["-f", "-I"], mkfile)
    case("-I -f 无操作数", ["-I", "-f"], mkfile)
    case("-f --interactive=never 无操作数", ["-f", "--interactive=never"], mkfile)
    case("--interactive=never -f 无操作数", ["--interactive=never", "-f"], mkfile)
    case("-f --interactive=always 无操作数", ["-f", "--interactive=always"], mkfile)
    case("--interactive=always -f 无操作数", ["--interactive=always", "-f"], mkfile)
    case("-f --interactive=once 无操作数", ["-f", "--interactive=once"], mkfile)

    # -f 之后再给 -i：不存在的文件还会不会被忽略
    case("-f -i 不存在", ["-f", "-i", "nope"], mkfile)
    case("-f --interactive=always 不存在", ["-f", "--interactive=always", "nope"], mkfile)
    case("-f --interactive=once 不存在", ["-f", "--interactive=once", "nope"], mkfile)

    # 应答解析
    for answer in ["y", "Y", "yes", "YES", "n", "N", "no", "", "zzz", " y", "y extra"]:
        case(f"应答 {answer!r}", ["-i", "a.txt"], mkfile, answer + "\n")

    # -i -r 对普通文件
    case("-i -r 普通文件", ["-i", "-r", "a.txt"], mkfile, "y\n")

    _force_rmtree(SANDBOX)
    print("\n### DONE")


def main_wrapper():
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        main()
    text = buffer.getvalue()
    out_path = HERE.parent / "数据" / "rm_probe9_out.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"### WROTE {out_path} ({len(text)} chars)")


if __name__ == "__main__":
    main_wrapper()
