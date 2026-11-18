"""tree 的边界情况探针：目录联接、-x 的卷标识、-h 的换算台阶。

这些点本轮没法靠 GNU tree 对拍（本机没装），所以单独实测，把结论钉死：

1. Windows 上 os.symlink 要管理员权限，但目录联接（junction）不要。
   联接在 stat 里长什么样？tree.py 用 S_ISLNK 判符号链接，
   所以要确认联接到底被当链接还是当目录。
2. -x 靠 st_dev 比对，README 说 Windows 的 st_dev 是卷标识，
   拿 C 盘和 E 盘各 stat 一次验证。
3. -h 的单位换算在 1024 / 1024^2 台阶附近的行为。
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = Path(ROOT) / "AI" / "数据" / "tree_edge"
LINK = DATA / "link_to_sub"
SIZES = DATA / "sizes"


def _run(argv: list[str], cwd: str = ROOT) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, "main.py", *argv],
        cwd=cwd,
        capture_output=True,
        timeout=60,
    )
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", errors="replace"),
        proc.stderr.decode("utf-8", errors="replace"),
    )


def _make_junction() -> None:
    """用 cmd 的 mklink /J 建目录联接（不需要管理员权限）。"""
    DATA.mkdir(parents=True, exist_ok=True)
    target = DATA / "target"
    target.mkdir(exist_ok=True)
    (target / "inside.txt").write_bytes(b"x\n")
    if LINK.exists():
        return
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(LINK), str(target)],
        capture_output=True,
        timeout=30,
    )
    print(f"mklink /J 退出码 {proc.returncode}：{proc.stdout.decode(errors='replace').strip()}")


def _probe_link() -> None:
    print("\n=== 1. 目录联接在 stat 里长什么样 ===")
    if not LINK.exists():
        print("  联接没建起来，跳过")
        return
    st = LINK.lstat()
    print(f"  lstat 模式 {stat.filemode(st.st_mode)}  S_ISLNK={stat.S_ISLNK(st.st_mode)}"
          f"  S_ISDIR={stat.S_ISDIR(st.st_mode)}")
    print(f"  os.path.islink={os.path.islink(LINK)}")
    try:
        print(f"  os.readlink={os.readlink(LINK)!r}")
    except OSError as exc:
        print(f"  os.readlink 失败：{exc}")
    print(f"  Python {sys.version.split()[0]}")

    print("\n  tree 默认（不开 -l）：")
    code, out, err = _run(["tree", str(DATA)])
    print(f"    退出码 {code}\n{out}    stderr: {err.strip()}")

    print("\n  tree -l（跟随指向目录的链接）：")
    code, out, err = _run(["tree", "-l", str(DATA)])
    print(f"    退出码 {code}\n{out}    stderr: {err.strip()}")


def _probe_dev() -> None:
    print("\n=== 2. -x 依赖的 st_dev ===")
    for path in (r"E:\1\NULL\Windows-to-Linux", r"C:\Windows"):
        try:
            st = os.stat(path)
            print(f"  {path}  st_dev={st.st_dev}")
        except OSError as exc:
            print(f"  {path}  stat 失败：{exc}")


def _probe_sizes() -> None:
    print("\n=== 3. -h 的换算台阶 ===")
    SIZES.mkdir(parents=True, exist_ok=True)
    cases = [0, 1, 1023, 1024, 1025, 2048, 1048575, 1048576, 1048577, 1572864]
    for size in cases:
        (SIZES / f"f{size}.bin").write_bytes(b"\0" * size)
    code, out, err = _run(["tree", "-h", str(SIZES)])
    print(f"    退出码 {code}  stderr: {err.strip()}")
    for line in out.splitlines():
        if "f" in line and ".bin" in line:
            print(f"    {line!r}")

    print("\n  同一批文件用 -s 看原始字节数：")
    code, out, err = _run(["tree", "-s", str(SIZES)])
    for line in out.splitlines():
        if ".bin" in line:
            print(f"    {line!r}")


def _probe_no_operand() -> None:
    print("\n=== 4. 不给操作数时列当前目录 ===")
    code, out, err = _run(["tree", "--noreport"], cwd=str(DATA))
    print(f"    退出码 {code}\n{out}    stderr: {err.strip()}")


if __name__ == "__main__":
    _make_junction()
    _probe_link()
    _probe_dev()
    _probe_sizes()
    _probe_no_operand()
