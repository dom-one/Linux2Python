"""du 对目录联接（junction）的处理实测。

Windows 上 Python 的 os.symlink 需要管理员权限（实测 WinError 1314），
但 cmd 的 mklink /J 建目录联接不需要。目录联接对 Python 来说
S_ISLNK=False、S_ISDIR=True，所以容易被当成普通目录。

重点查三件事：
1. 联接的 stat 到底长什么样（st_mode / st_ino / st_dev）
2. du 会不会钻进联接里（会的话内容被算两遍）
3. 自引用联接会不会无限递归（tree.py 那边踩过这个坑）

产出：AI/数据/du_junction.txt
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "du_demo"
OUT = ROOT / "AI" / "数据" / "du_junction.txt"
GNU_DU = Path(r"E:\software\Git\Git\usr\bin\du.exe")

lines: list[str] = []


def emit(text: str = "") -> None:
    lines.append(text)


def run_ours(args: list[str], cwd: Path, timeout: int = 60) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "du", *args],
        cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def run_gnu(args: list[str], cwd: Path, timeout: int = 60) -> tuple[int, str, str]:
    proc = subprocess.run(
        [str(GNU_DU), *args], cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def make_junction(link: Path, target: Path) -> bool:
    """用 cmd 的 mklink /J 建目录联接（不需要管理员权限）。"""
    if link.exists():
        subprocess.run(["cmd", "/c", "rmdir", str(link)], capture_output=True)
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    return link.exists()


def main() -> None:
    if not DATA.is_dir():
        print("夹具不存在，先跑 _t900_make_du_fixture.py")
        return 1

    emit("=" * 72)
    emit("一、目录联接的 stat 长什么样")
    emit("=" * 72)
    emit()
    jdir = DATA / "junc"
    jdir.mkdir(exist_ok=True)
    link = jdir / "to_tree"
    target = DATA / "tree"
    if not make_junction(link, target):
        emit("  建不了联接，跳过")
        return 0

    lst = os.lstat(str(link))
    st = os.stat(str(link))
    tgt = os.stat(str(target))
    emit("  os.lstat(联接):")
    emit("    st_mode  = 0o%o" % lst.st_mode)
    emit("    S_ISLNK = %s   S_ISDIR = %s   S_ISREG = %s" % (
        stat.S_ISLNK(lst.st_mode), stat.S_ISDIR(lst.st_mode),
        stat.S_ISREG(lst.st_mode)))
    emit("    st_ino   = %d" % lst.st_ino)
    emit("    st_dev   = %d" % lst.st_dev)
    emit("    st_size  = %d" % lst.st_size)
    emit("  os.stat(联接)（跟随）:")
    emit("    st_ino   = %d   st_dev = %d" % (st.st_ino, st.st_dev))
    emit("  os.stat(目标):")
    emit("    st_ino   = %d   st_dev = %d" % (tgt.st_ino, tgt.st_dev))
    emit()
    emit("  ⇒ 联接的 lstat 与目标不同（inode 不同），去重表认不出它是同一个目录。")
    emit("  ⇒ S_ISLNK=False、S_ISDIR=True，Python 把它当普通目录。")
    emit()

    emit("=" * 72)
    emit("二、du 会不会钻进联接里")
    emit("=" * 72)
    emit()
    code, out, err = run_ours(["-a", "junc"], DATA)
    emit("  项目 du -a junc  退出码 %d" % code)
    for ln in out.splitlines():
        emit("    | %s" % ln)
    code, out, err = run_gnu(["--apparent-size", "-a", "junc"], DATA)
    emit("  GNU  du -a junc  退出码 %d" % code)
    for ln in out.splitlines():
        emit("    | %s" % ln)
    emit()
    emit("  ⇒ 项目把联接当目录钻进去了（内容算了一遍）；")
    emit("    GNU 把联接当符号链接（只报它自己占的那一块）。")
    emit()

    emit("  联接和目标同时作为操作数，看去重表认不认得出：")
    code, out, err = run_ours(["-s", "junc/to_tree", "tree"], DATA)
    emit("    项目 du -s junc/to_tree tree -> %s (退出码 %d)" % (
        out.strip().replace("\n", " | "), code))
    code, out, err = run_gnu(["--apparent-size", "-s", "junc/to_tree", "tree"], DATA)
    emit("    GNU  du -s junc/to_tree tree -> %s (退出码 %d)" % (
        out.strip().replace("\n", " | "), code))
    emit()

    emit("=" * 72)
    emit("三、自引用联接会不会无限递归")
    emit("=" * 72)
    emit()
    selfdir = DATA / "selfref"
    selfdir.mkdir(exist_ok=True)
    selflink = selfdir / "loop"
    if not make_junction(selflink, selfdir):
        emit("  建不了自引用联接")
    else:
        (selfdir / "f.txt").write_bytes(b"Q" * 100)
        emit("  自引用联接建好，跑 du -s selfref（带 60 秒超时）：")
        try:
            code, out, err = run_ours(["-s", "selfref"], DATA, timeout=60)
            emit("    项目 退出码 %d -> %s" % (code, out.strip()))
            if err.strip():
                emit("    项目 stderr: %s" % err.strip()[:400])
        except subprocess.TimeoutExpired:
            emit("    项目 超时（60 秒没退出）")
        try:
            code, out, err = run_gnu(["--apparent-size", "-s", "selfref"], DATA, timeout=60)
            emit("    GNU  退出码 %d -> %s" % (code, out.strip()))
            if err.strip():
                emit("    GNU  stderr: %s" % err.strip()[:400])
        except subprocess.TimeoutExpired:
            emit("    GNU  超时（60 秒没退出）")
        emit()

        emit("  钻进去看深度（du -a selfref 的行数与最深路径）：")
        try:
            code, out, err = run_ours(["-a", "selfref"], DATA, timeout=60)
            rows = out.splitlines()
            emit("    项目 共 %d 行，最深的一行：%s" % (len(rows), rows[-1] if rows else ""))
            if err.strip():
                emit("    项目 stderr: %s" % err.strip()[:400])
        except subprocess.TimeoutExpired:
            emit("    项目 超时")
        try:
            code, out, err = run_gnu(["--apparent-size", "-a", "selfref"], DATA, timeout=60)
            rows = out.splitlines()
            emit("    GNU  共 %d 行，最深的一行：%s" % (len(rows), rows[-1] if rows else ""))
            if err.strip():
                emit("    GNU  stderr: %s" % err.strip()[:400])
        except subprocess.TimeoutExpired:
            emit("    GNU  超时")
    emit()

    emit("=" * 72)
    emit("四、-x 在联接上的表现")
    emit("=" * 72)
    emit()
    code, out, err = run_ours(["-s", "-x", "junc"], DATA)
    emit("  项目 du -s -x junc -> %s (退出码 %d)" % (out.strip(), code))
    code, out, err = run_gnu(["--apparent-size", "-s", "-x", "junc"], DATA)
    emit("  GNU  du -s -x junc -> %s (退出码 %d)" % (out.strip(), code))
    emit()
    emit("  （联接与目标在同一卷，st_dev 相同，所以 -x 挡不住。）")
    emit()

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("联接实测写入: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
