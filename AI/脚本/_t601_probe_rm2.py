"""探针第二轮：GNU rm 的交互提示文案、-r -v 打印顺序、-f/-i 边界。"""

from __future__ import annotations

import io
import contextlib
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDBOX = HERE.parent / "数据" / "rm_probe2"
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
    print(f"  rc   = {code}")
    print(f"  out  = {out!r}")
    print(f"  err  = {err!r}")
    print(f"  left = {tree_state(root)}")


def main():
    SANDBOX.mkdir(parents=True, exist_ok=True)

    def mkfile(root):
        (root / "a.txt").write_text("hello\n", encoding="utf-8")

    def mkempty(root):
        (root / "empty").mkdir()

    def mkfull(root):
        d = root / "dir"
        (d / "sub").mkdir(parents=True)
        (d / "f1.txt").write_text("x", encoding="utf-8")
        (d / "sub" / "f2.txt").write_text("y", encoding="utf-8")

    def mkro_dir(root):
        d = root / "rodir"
        d.mkdir()
        p = d / "ro.txt"
        p.write_text("ro", encoding="utf-8")
        os.chmod(p, 0o444)

    def mkfour(root):
        for name in ("a.txt", "b.txt", "c.txt", "d.txt"):
            (root / name).write_text(name, encoding="utf-8")

    def mkmixed(root):
        # 一个目录里既有文件也有子目录，看 -r -v 的打印顺序
        d = root / "m"
        d.mkdir()
        (d / "f_a.txt").write_text("a", encoding="utf-8")
        (d / "f_b.txt").write_text("b", encoding="utf-8")
        (d / "zsub").mkdir()
        (d / "zsub" / "deep.txt").write_text("d", encoding="utf-8")
        (d / "asub").mkdir()
        (d / "asub" / "deep2.txt").write_text("d2", encoding="utf-8")

    def mkdeep(root):
        d = root / "a" / "b" / "c"
        d.mkdir(parents=True)
        (d / "deep.txt").write_text("q", encoding="utf-8")
        (d / "mid.txt").write_text("m", encoding="utf-8")

    # -f / -i 与无操作数
    case("-f 无操作数", ["-f"])
    case("-i 无操作数", ["-i"])
    case("-- 无操作数", ["--"])

    # 提示文案
    case("-i 删目录(无-r)", ["-i", "dir"], mkfull, "y\n")
    case("-i 递归删目录", ["-i", "-r", "dir"], mkfull, "y\n")
    case("-I 递归删目录", ["-I", "-r", "dir"], mkfull, "y\n")
    case("-I 删4个文件", ["-I", "a.txt", "b.txt", "c.txt", "d.txt"], mkfour, "y\n")
    case("-I 删3个文件", ["-I", "a.txt", "b.txt", "c.txt"], mkfour, "y\n")
    case("-I 递归删目录(答 n)", ["-I", "-r", "dir"], mkfull, "n\n")
    case("-i 递归删目录(答 n)", ["-i", "-r", "dir"], mkfull, "n\n")
    case("--interactive=never", ["--interactive=never", "a.txt"], mkfile)
    case("--interactive=once 4文件", ["--interactive=once", "a.txt", "b.txt", "c.txt", "d.txt"], mkfour, "y\n")
    case("--interactive=always", ["--interactive=always", "a.txt"], mkfile, "y\n")

    # -d 与 -v 组合
    case("-dv 删空目录", ["-d", "-v", "empty"], mkempty)
    case("-dv 删文件", ["-d", "-v", "a.txt"], mkfile)
    case("-v 删目录(无-r)", ["-v", "dir"], mkfull)

    # -r -v 顺序
    case("-rv 混合目录", ["-r", "-v", "m"], mkmixed)
    case("-rv 多层目录", ["-r", "-v", "a"], mkdeep)

    # 只读
    case("-r 删含只读文件的目录", ["-r", "rodir"], mkro_dir)
    case("-rf 删含只读文件的目录", ["-r", "-f", "rodir"], mkro_dir)

    # 其它
    case("-r 删 .", ["-r", "."], mkfile)
    case("-rf 删 ..", ["-r", "-f", ".."], mkfile)
    case("-v -r 同给 文件", ["-v", "-r", "a.txt"], mkfile)
    case("--one-file-system", ["--one-file-system", "-r", "dir"], mkfull)
    case("--no-preserve-root", ["--no-preserve-root", "/"], mkfile)
    case("--preserve-root=all", ["--preserve-root=all", "/"], mkfile)
    case("重复同一个文件", ["a.txt", "a.txt"], mkfile)
    case("-f 重复同一个文件", ["-f", "a.txt", "a.txt"], mkfile)

    # Windows 侧：os.unlink 对只读文件的行为
    root = fresh("win")
    p = root / "ro.txt"
    p.write_text("ro", encoding="utf-8")
    os.chmod(p, 0o444)
    try:
        os.unlink(p)
        print("=" * 70)
        print("[Windows] os.unlink 只读文件: 成功")
    except OSError as exc:
        print("=" * 70)
        print(f"[Windows] os.unlink 只读文件: 失败 errno={exc.errno} {exc.strerror}")

    # Windows 侧：rmtree 遇到只读文件
    root = fresh("win2")
    d = root / "rodir"
    d.mkdir()
    p = d / "ro.txt"
    p.write_text("ro", encoding="utf-8")
    os.chmod(p, 0o444)
    try:
        shutil.rmtree(root)
        print("[Windows] shutil.rmtree 含只读文件: 成功")
    except OSError as exc:
        print(f"[Windows] shutil.rmtree 含只读文件: 失败 errno={exc.errno} {exc.strerror}")

    _force_rmtree(SANDBOX)
    print("\n### DONE")


def main_wrapper():
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        main()
    text = buffer.getvalue()
    out_path = HERE.parent / "数据" / "rm_probe2_out.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"### WROTE {out_path} ({len(text)} chars)")


if __name__ == "__main__":
    main_wrapper()
