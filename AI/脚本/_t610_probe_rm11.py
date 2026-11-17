"""探针第十一轮：逐个应答 -i -r，每答一次就快照目录树，弄清提示与删除的对应关系。"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDBOX = HERE.parent / "数据" / "rm_probe11"
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


def step(title, argv, setup, answers):
    """每次只喂一个应答，喂完就快照目录树。"""
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
        proc.stdin.write((answer + "\n").encode())
        proc.stdin.flush()
        time.sleep(0.35)
        print(f"  答 {index}: {answer!r}  此刻目录树 = {tree_state(root)}")
    try:
        proc.stdin.close()
    except OSError:
        pass
    out, err = proc.communicate(timeout=30)
    print(f"  rc   = {proc.returncode}")
    print(f"  out  = {out.decode('utf-8', 'replace')!r}")
    print(f"  err  = {err.decode('utf-8', 'replace')!r}")
    print(f"  终态 = {tree_state(root)}")


def main():
    SANDBOX.mkdir(parents=True, exist_ok=True)

    def mksub_only(root):
        d = root / "dir"
        (d / "sub").mkdir(parents=True)
        (d / "sub" / "f2.txt").write_text("y", encoding="utf-8")

    def mkflat(root):
        d = root / "dir"
        d.mkdir()
        (d / "f1.txt").write_text("x", encoding="utf-8")
        (d / "f2.txt").write_text("y", encoding="utf-8")

    step("只有sub: 全 y", ["-i", "-r", "dir"], mksub_only, ["y", "y", "y", "y", "y"])
    step("扁平: 全 y", ["-i", "-r", "dir"], mkflat, ["y", "y", "y", "y"])
    step("扁平: y y n y", ["-i", "-r", "dir"], mkflat, ["y", "y", "n", "y"])
    step("只有sub: y n", ["-i", "-r", "dir"], mksub_only, ["y", "n"])

    _force_rmtree(SANDBOX)
    print("\n### DONE")


def main_wrapper():
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        main()
    text = buffer.getvalue()
    out_path = HERE.parent / "数据" / "rm_probe11_out.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"### WROTE {out_path} ({len(text)} chars)")


if __name__ == "__main__":
    main_wrapper()
