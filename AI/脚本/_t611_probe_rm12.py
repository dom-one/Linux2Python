"""探针第十二轮：拒绝 descend 之后是「整个操作中止」还是「只跳过这一个参数」。"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDBOX = HERE.parent / "数据" / "rm_probe12"
GNU_RM = r"E:\software\Git\Git\usr\bin\rm.exe"


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


def fresh(name):
    root = SANDBOX / name
    if root.exists():
        _force_rmtree(root)
    root.mkdir(parents=True)
    return root


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
    proc = subprocess.run(
        [GNU_RM, *argv],
        cwd=str(root),
        input=stdin_text.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    print("=" * 74)
    print(f"[{title}] argv={argv} stdin={stdin_text!r}")
    print(f"  rc   = {proc.returncode}")
    print(f"  out  = {proc.stdout.decode('utf-8', 'replace')!r}")
    print(f"  err  = {proc.stderr.decode('utf-8', 'replace')!r}")
    print(f"  left = {tree_state(root)}")


def step(title, argv, setup, answers):
    root = fresh("c")
    setup(root)
    proc = subprocess.Popen(
        [GNU_RM, *argv],
        cwd=str(root),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    print("=" * 74)
    print(f"[{title}] argv={argv}")
    for index, answer in enumerate(answers, start=1):
        try:
            proc.stdin.write((answer + "\n").encode())
            proc.stdin.flush()
        except OSError:
            print(f"  答 {index}: {answer!r}  <- 进程已退出，管道关闭")
            break
        time.sleep(0.35)
        print(f"  答 {index}: {answer!r}  此刻目录树 = {tree_state(root)}")
    try:
        proc.stdin.close()
    except OSError:
        pass
    out, err = proc.communicate(timeout=30)
    print(f"  rc   = {proc.returncode}")
    print(f"  err  = {err.decode('utf-8', 'replace')!r}")
    print(f"  终态 = {tree_state(root)}")


def main():
    SANDBOX.mkdir(parents=True, exist_ok=True)

    def mk_two_args(root):
        a = root / "dirA"
        (a / "sub").mkdir(parents=True)
        (a / "sub" / "f.txt").write_text("x", encoding="utf-8")
        b = root / "dirB"
        b.mkdir()
        (b / "g.txt").write_text("y", encoding="utf-8")

    def mk_sub_only(root):
        d = root / "dir"
        (d / "sub").mkdir(parents=True)
        (d / "sub" / "f2.txt").write_text("y", encoding="utf-8")

    # 拒绝第一个参数的 descend，第二个参数还会不会继续
    step("两个参数: 拒绝 dirA/sub 的 descend", ["-i", "-r", "dirA", "dirB"], mk_two_args,
         ["y", "n", "y", "y", "y", "y", "y", "y"])

    # 拒绝顶层 descend 之后还有没有别的提示
    step("拒绝顶层 descend", ["-i", "-r", "dir"], mk_sub_only, ["n", "y", "y", "y"])

    # -d 与 -i：空目录被拒后有没有别的
    case("-i -d 空目录 拒", ["-i", "-d", "empty", "other.txt"],
         lambda r: ((r / "empty").mkdir(), (r / "other.txt").write_text("z", encoding="utf-8")),
         "n\ny\n")

    # -i 拒绝普通文件后是否还继续提示别的文件
    case("-i 两个文件 拒第一个", ["-i", "a.txt", "b.txt"],
         lambda r: ((r / "a.txt").write_text("a", encoding="utf-8")),
         "n\ny\n")

    _force_rmtree(SANDBOX)
    print("\n### DONE")


def main_wrapper():
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        main()
    text = buffer.getvalue()
    out_path = HERE.parent / "数据" / "rm_probe12_out.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"### WROTE {out_path} ({len(text)} chars)")


if __name__ == "__main__":
    main_wrapper()
