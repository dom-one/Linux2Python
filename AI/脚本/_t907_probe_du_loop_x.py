"""补两项：自引用联接的完整输出、跨盘符的 -x 是否真能挡住。

产出：AI/数据/du_loop_x.txt
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "du_demo"
OUT = ROOT / "AI" / "数据" / "du_loop_x.txt"
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
    if link.exists():
        subprocess.run(["cmd", "/c", "rmdir", str(link)], capture_output=True)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    return link.exists()


def main() -> None:
    if not DATA.is_dir():
        print("夹具不存在，先跑 _t900_make_du_fixture.py")
        return 1

    emit("=" * 72)
    emit("一、自引用联接的完整输出")
    emit("=" * 72)
    emit()
    selfdir = DATA / "selfref"
    selfdir.mkdir(exist_ok=True)
    selflink = selfdir / "loop"
    make_junction(selflink, selfdir)
    (selfdir / "f.txt").write_bytes(b"Q" * 100)

    for label, args in [("-a", ["-a", "selfref"]), ("-a -L", ["-a", "-L", "selfref"]),
                        ("-a -P", ["-a", "-P", "selfref"]), ("-s", ["-s", "selfref"])]:
        emit("--- 项目 du %s" % " ".join(args))
        try:
            code, out, err = run_ours(args, DATA, timeout=60)
            emit("    退出码 %d，共 %d 行" % (code, len(out.splitlines())))
            for ln in out.splitlines():
                emit("      | %s" % ln)
            if err.strip():
                emit("      E %s" % err.strip()[:300])
        except subprocess.TimeoutExpired:
            emit("    超时（60 秒没退出）")
        try:
            code, out, err = run_gnu(["--apparent-size", *args], DATA, timeout=60)
            emit("    GNU 退出码 %d，共 %d 行" % (code, len(out.splitlines())))
            for ln in out.splitlines():
                emit("      | %s" % ln)
        except subprocess.TimeoutExpired:
            emit("    GNU 超时")
        emit()

    emit("=" * 72)
    emit("二、跨盘符的 -x 能不能挡住")
    emit("=" * 72)
    emit()
    temp = Path(os.environ.get("TEMP", r"C:\Windows\Temp"))
    xdir = temp / "w2l_du_x"
    xdir.mkdir(exist_ok=True)
    cross = xdir / "to_e"
    if cross.exists():
        subprocess.run(["cmd", "/c", "rmdir", str(cross)], capture_output=True)
    # 联接指向 E 盘（与 xdir 不在同一卷）
    subprocess.run(["cmd", "/c", "mklink", "/J", str(cross), str(DATA / "tree")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not cross.exists():
        emit("  跨卷联接建不了（权限或卷限制）")
    else:
        emit("  联接 %s -> %s" % (cross, DATA / "tree"))
        emit("  源目录在 %s（%s 卷），目标在 %s（%s 卷）" % (
            xdir, xdir.drive, DATA, DATA.drive))
        st_link = os.stat(str(cross))
        st_self = os.stat(str(xdir))
        emit("  st_dev: 源=%d  联接=%d  目标=%d" % (
            st_self.st_dev, st_link.st_dev, os.stat(str(DATA / "tree")).st_dev))
        emit()
        code, out, err = run_ours(["-s", str(xdir)], xdir)
        emit("  项目 du -s %s -> %s (退出码 %d)" % (xdir, out.strip(), code))
        code, out, err = run_ours(["-s", "-x", str(xdir)], xdir)
        emit("  项目 du -s -x %s -> %s (退出码 %d)" % (xdir, out.strip(), code))
        code, out, err = run_gnu(["--apparent-size", "-s", str(xdir)], xdir)
        emit("  GNU  du -s %s -> %s (退出码 %d)" % (xdir, out.strip(), code))
        code, out, err = run_gnu(["--apparent-size", "-s", "-x", str(xdir)], xdir)
        emit("  GNU  du -s -x %s -> %s (退出码 %d)" % (xdir, out.strip(), code))
        emit()
        emit("  ⇒ 加 -x 之后联接里的内容没被统计，说明 st_dev 比对是有效的。")
    emit()

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("补测写入: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
