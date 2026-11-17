"""探针第三轮：-i/-I 的完整提示序列、-I 单复数、失败时的 -v 行为。"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDBOX = HERE.parent / "数据" / "rm_probe3"
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
    print(f"  stdin = {stdin_text!r}")
    print(f"  rc    = {code}")
    print(f"  out   = {out!r}")
    print(f"  err   = {err!r}")
    print(f"  left  = {tree_state(root)}")


def main():
    SANDBOX.mkdir(parents=True, exist_ok=True)

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

    def mkempty(root):
        (root / "empty").mkdir()

    def mkfile(root):
        (root / "a.txt").write_text("hello\n", encoding="utf-8")

    def mk2dirs(root):
        (root / "d1").mkdir()
        (root / "d2").mkdir()

    def mk3files(root):
        for name in ("a.txt", "b.txt", "c.txt"):
            (root / name).write_text(name, encoding="utf-8")

    # -i -r 完整提示序列
    case("-i -r 全答 y (扁平)", ["-i", "-r", "dir"], mkflat, "y\ny\ny\ny\ny\ny\n")
    case("-i -r 全答 y (嵌套)", ["-i", "-r", "dir"], mkfull, "y\n" * 10)
    case("-i -r -v 全答 y", ["-i", "-r", "-v", "dir"], mkflat, "y\n" * 10)
    case("-i -d 空目录", ["-i", "-d", "empty"], mkempty, "y\n")
    case("-i 删文件答 Y", ["-i", "a.txt"], mkfile, "Y\n")
    case("-i 删文件答 yes", ["-i", "a.txt"], mkfile, "yes\n")
    case("-i 删文件答乱字符", ["-i", "a.txt"], mkfile, "zzz\n")

    # -I 单复数
    case("-I 2个目录", ["-I", "d1", "d2"], mk2dirs, "y\n")
    case("-I 1个目录", ["-I", "d1"], mk2dirs, "y\n")
    case("-I 4个目录+文件", ["-I", "d1", "d2", "a.txt", "b.txt"], mk2dirs, "y\n")
    case("-I -r 2个目录", ["-I", "-r", "d1", "d2"], mk2dirs, "y\n")
    case("-I 递归删非空目录", ["-I", "-r", "dir"], mkfull, "y\n")

    # -f 与错误
    case("-f 删不存在的 + 存在的", ["-f", "nope", "a.txt"], mkfile)
    case("-v 多个 有的失败", ["-v", "a.txt", "nope"], mkfile)
    case("-fv 多个 有的失败", ["-f", "-v", "a.txt", "nope"], mkfile)

    # -f 与 -i 同时给
    case("-f -i 删文件", ["-f", "-i", "a.txt"], mkfile, "")
    case("-i -f 删文件", ["-i", "-f", "a.txt"], mkfile, "")

    # 重复目录
    case("重复同一个目录", ["-r", "dir", "dir"], mkflat)

    _force_rmtree(SANDBOX)
    print("\n### DONE")


def main_wrapper():
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        main()
    text = buffer.getvalue()
    out_path = HERE.parent / "数据" / "rm_probe3_out.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"### WROTE {out_path} ({len(text)} chars)")


if __name__ == "__main__":
    main_wrapper()
