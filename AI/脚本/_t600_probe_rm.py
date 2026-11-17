"""探针：实测 GNU rm 8.32 的行为基线。

所有夹具都建在 AI/数据/rm_probe/ 沙箱里，脚本自己清理。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDBOX = HERE.parent / "数据" / "rm_probe"
GNU_RM = r"E:\software\Git\Git\usr\bin\rm.exe"

if not os.path.exists(GNU_RM):
    GNU_RM = r"C:\Program Files\Git\usr\bin\rm.exe"
    if not os.path.exists(GNU_RM):
        raise SystemExit("找不到 GNU rm")


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
    """列出沙箱里的东西，标出目录与文件。"""
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
    print(f"  rc   = {code}")
    print(f"  out  = {out!r}")
    print(f"  err  = {err!r}")
    print(f"  left = {tree_state(root)}")


_OUT_LINES: list[str] = []


def emit(text: str = "") -> None:
    _OUT_LINES.append(text)
    print(text)


def main():
    SANDBOX.mkdir(parents=True, exist_ok=True)

    # 版本与帮助
    proc = subprocess.run([GNU_RM, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("### VERSION")
    print(proc.stdout.decode("utf-8", "replace"))
    proc = subprocess.run([GNU_RM, "--help"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("### HELP")
    print(proc.stdout.decode("utf-8", "replace"))
    proc = subprocess.run([GNU_RM, "--help"], stderr=subprocess.PIPE)
    print("### HELP rc =", proc.returncode)

    def mkfile(root):
        (root / "a.txt").write_text("hello\n", encoding="utf-8")

    def mkempty(root):
        (root / "empty").mkdir()

    def mkfull(root):
        d = root / "dir"
        (d / "sub").mkdir(parents=True)
        (d / "f1.txt").write_text("x", encoding="utf-8")
        (d / "sub" / "f2.txt").write_text("y", encoding="utf-8")

    def mkreadonly(root):
        p = root / "ro.txt"
        p.write_text("ro", encoding="utf-8")
        os.chmod(p, 0o444)

    def mkro_dir(root):
        d = root / "rodir"
        d.mkdir()
        p = d / "ro.txt"
        p.write_text("ro", encoding="utf-8")
        os.chmod(p, 0o444)

    def mkmulti(root):
        for name in ("a.txt", "b.txt", "c.txt"):
            (root / name).write_text(name, encoding="utf-8")

    def mkdash(root):
        (root / "-file").write_text("dash", encoding="utf-8")

    case("无操作数", [])
    case("删文件", ["a.txt"], mkfile)
    case("删不存在的文件", ["nope.txt"], mkfile)
    case("删目录(无-r)", ["dir"], mkfull)
    case("删空目录(无-r)", ["empty"], mkempty)
    case("-f 删不存在的文件", ["-f", "nope.txt"], mkfile)
    case("-f 删目录(无-r)", ["-f", "dir"], mkfull)
    case("-r 删目录", ["-r", "dir"], mkfull)
    case("-r 删文件", ["-r", "a.txt"], mkfile)
    case("-v 删文件", ["-v", "a.txt"], mkfile)
    case("-v 删不存在的文件", ["-v", "nope.txt"], mkfile)
    case("-rv 删目录", ["-r", "-v", "dir"], mkfull)
    case("-rv 删目录(单个子文件)", ["-r", "-v", "dir"], lambda r: (r / "dir").mkdir() or (r / "dir" / "f.txt").write_text("z", encoding="utf-8"))
    case("-d 删空目录", ["-d", "empty"], mkempty)
    case("-d 删非空目录", ["-d", "dir"], mkfull)
    case("-d 删文件", ["-d", "a.txt"], mkfile)
    case("-i 删文件(答 y)", ["-i", "a.txt"], mkfile, "y\n")
    case("-i 删文件(答 n)", ["-i", "a.txt"], mkfile, "n\n")
    case("-i 删文件(空输入)", ["-i", "a.txt"], mkfile, "\n")
    case("-i 删多个文件(全 y)", ["-i", "a.txt", "b.txt", "c.txt"], mkmulti, "y\ny\ny\n")
    case("-i 删不存在文件", ["-i", "nope.txt"], mkfile, "y\n")
    case("-if 删不存在文件", ["-i", "-f", "nope.txt"], mkfile, "")
    case("-I 删多个文件", ["-I", "a.txt", "b.txt"], mkmulti, "y\n")
    case("多个文件其中一个不存在", ["a.txt", "nope.txt", "b.txt"], mkmulti)
    case("-v 多个文件", ["-v", "a.txt", "b.txt"], mkmulti)
    case("-- 分隔", ["--", "-file"], mkdash)
    case("-rf 目录", ["-r", "-f", "dir"], mkfull)
    case("删只读文件", ["ro.txt"], mkreadonly)
    case("-f 删只读文件", ["-f", "ro.txt"], mkreadonly)
    case("-r 删含只读文件的目录", ["-r", "dir"], mkro_dir)
    case("路径带斜杠", ["empty/"], mkempty)
    case("删 . 与 ..", ["."], mkfile)
    case("--preserve-root 删 /", ["--preserve-root", "/"])
    case("不存在的选项", ["--no-such-option", "a.txt"], mkfile)
    case("空操作数", [""], mkfile)

    # 只读文件的 stat 情况
    root = fresh("ro")
    mkreadonly(root)
    st = os.stat(root / "ro.txt")
    print("=" * 70)
    print("[只读文件的 stat] mode =", oct(st.st_mode))
    print("  isdir =", os.path.isdir(root / "ro.txt"))

    # 递归删除后父目录还剩什么
    root = fresh("deep")
    d = root / "a" / "b" / "c"
    d.mkdir(parents=True)
    (d / "deep.txt").write_text("q", encoding="utf-8")
    code, out, err = run(["-r", "a"], root)
    print("=" * 70)
    print(f"[递归删多层] rc={code} out={out!r} err={err!r} left={tree_state(root)}")

    # rm 多个参数，第二个不存在：第一个删了吗
    root = fresh("multi")
    mkmulti(root)
    code, out, err = run(["a.txt", "nope", "c.txt"], root)
    print("=" * 70)
    print(f"[多参数部分失败] rc={code} out={out!r} err={err!r} left={tree_state(root)}")

    _force_rmtree(SANDBOX)
    print("\n### DONE")


def main_wrapper():
    """把探针输出同时写到 AI/数据/rm_probe_out.txt（中文目录不能用 shell 重定向）。"""
    import io
    import contextlib

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        main()
    text = buffer.getvalue()
    out_path = HERE.parent / "数据" / "rm_probe_out.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"### WROTE {out_path} ({len(text)} chars)")


if __name__ == "__main__":
    main_wrapper()
