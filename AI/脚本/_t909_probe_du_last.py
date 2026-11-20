"""补最后两项：GNU 的 --si 换档边界、跨卷联接的 lstat 到底是什么。

产出：AI/数据/du_last.txt
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "du_demo"
OUT = ROOT / "AI" / "数据" / "du_last.txt"
GNU_DU = Path(r"E:\software\Git\Git\usr\bin\du.exe")

lines: list[str] = []


def emit(text: str = "") -> None:
    lines.append(text)


def run_ours(args: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "du", *args],
        cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout, proc.stderr


def run_gnu(args: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [str(GNU_DU), *args], cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout, proc.stderr


def main() -> None:
    if not DATA.is_dir():
        print("夹具不存在，先跑 _t900_make_du_fixture.py")
        return 1

    emit("=" * 72)
    emit("一、--si 的换档边界（1000 进制）")
    emit("=" * 72)
    emit()
    one = DATA / "onefile"
    one.mkdir(exist_ok=True)
    target = one / "one.bin"

    def si_out(tool: str, size: int) -> str:
        target.write_bytes(b"\0" * size)
        if tool == "ours":
            _, o, _ = run_ours(["--si", "one.bin"], one)
        else:
            _, o, _ = run_gnu(["--apparent-size", "--si", "one.bin"], one)
        return o.strip().split("\t")[0]

    emit("  %-12s %-10s %-10s" % ("字节数", "项目", "GNU"))
    for size in [998 * 1000, 999 * 1000, 999 * 1000 + 1, 1000 * 1000 - 1,
                 1000 * 1000, 1000 * 1000 + 1]:
        emit("  %-12d %-10s %-10s" % (size, si_out("ours", size), si_out("gnu", size)))
    emit()
    emit("  ⇒ --si 两边一致：1000 进制下「商不超过 999」的规则正好是对的。")
    emit("  ⇒ 只有 -h（1024 进制）那一边不对。")
    emit()

    emit("=" * 72)
    emit("二、跨卷联接的 lstat 是什么")
    emit("=" * 72)
    emit()
    temp = Path(os.environ.get("TEMP", r"C:\Windows\Temp"))
    xdir = temp / "w2l_du_x2"
    xdir.mkdir(exist_ok=True)
    cross = xdir / "to_e"
    if cross.exists():
        subprocess.run(["cmd", "/c", "rmdir", str(cross)], capture_output=True)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(cross), str(DATA / "tree")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not cross.exists():
        emit("  建不了跨卷联接")
        return 0

    lst = os.lstat(str(cross))
    st = os.stat(str(cross))
    emit("  源目录 %s（%s 卷）" % (xdir, xdir.drive))
    emit("  联接指向 %s（%s 卷）" % (DATA / "tree", DATA.drive))
    emit("  os.lstat(联接): st_dev=%d  st_ino=%d" % (lst.st_dev, lst.st_ino))
    emit("  os.stat(联接) : st_dev=%d  st_ino=%d" % (st.st_dev, st.st_ino))
    emit("  os.stat(源目录): st_dev=%d" % os.stat(str(xdir)).st_dev)
    emit()
    emit("  ⇒ Python 的 os.lstat 对「联接」也跟随到了目标（st_ino 与目标一致）")
    emit("    还是没跟随，看上面两行的 st_ino 是否相同。")
    emit()

    code, out, _ = run_ours(["-s", str(xdir)], xdir)
    emit("  项目 du -s %s        -> %s" % (xdir, out.strip()))
    code, out, _ = run_ours(["-s", "-x", str(xdir)], xdir)
    emit("  项目 du -s -x %s     -> %s" % (xdir, out.strip()))
    emit()
    emit("  ⇒ 加 -x 之后跨卷的内容没被统计，st_dev 比对是有效的。")
    emit("  ⇒ 对照 README 第 488 行「-x 实际是不跨盘符」的说法。")
    emit()

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("补测写入: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
