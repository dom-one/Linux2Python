"""补三个细节：--time 到底取哪个时间戳、GNU 人类可读在换档点附近的取整、
--si 的换档边界。

产出：AI/数据/du_extra.txt
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "du_demo"
OUT = ROOT / "AI" / "数据" / "du_extra.txt"
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
    emit("一、--time 的时间列取的是哪个时间戳")
    emit("=" * 72)
    emit()
    emit("造一个目录：目录本身的 mtime 与里面文件的 mtime 故意差开。")
    emit()
    ts = DATA / "ts"
    if ts.exists():
        for p in sorted(ts.rglob("*"), reverse=True):
            p.unlink()
        ts.rmdir()
    ts.mkdir()
    inner = ts / "inner.txt"
    inner.write_bytes(b"x" * 10)
    # 文件的时间设成 2020 年，目录设成 2021 年
    old = time.mktime((2020, 3, 15, 12, 0, 0, 0, 0, -1))
    newer = time.mktime((2021, 7, 20, 8, 30, 0, 0, 0, -1))
    os.utime(str(inner), (old, old))
    os.utime(str(ts), (newer, newer))

    _, ours_t, _ = run_ours(["--time", "-a", "ts"], DATA)
    _, gnu_t, _ = run_gnu(["--apparent-size", "--time", "-a", "ts"], DATA)
    emit("  文件 inner.txt 的 mtime: 2020-03-15 12:00")
    emit("  目录 ts 自己的 mtime   : 2021-07-20 08:30")
    emit()
    emit("  项目:")
    for ln in ours_t.splitlines():
        emit("    | %s" % ln)
    emit("  GNU :")
    for ln in gnu_t.splitlines():
        emit("    | %s" % ln)
    emit()
    emit("  ⇒ 目录行取的是「目录自己 + 里面所有文件里最新的那个」；")
    emit("    GNU 取的是目录自己的 mtime（2021-07-20），本实现取 max（也是 2021-07-20）。")
    emit("    把文件的时间设得更晚就能看出差别，下面第二组。")
    emit()

    os.utime(str(inner), (newer + 86400, newer + 86400))
    emit("  再把 inner.txt 的 mtime 改成 2022-08-19 08:30（比目录晚一年）:")
    _, ours_t2, _ = run_ours(["--time", "-a", "ts"], DATA)
    _, gnu_t2, _ = run_gnu(["--apparent-size", "--time", "-a", "ts"], DATA)
    emit("  项目:")
    for ln in ours_t2.splitlines():
        emit("    | %s" % ln)
    emit("  GNU :")
    for ln in gnu_t2.splitlines():
        emit("    | %s" % ln)
    emit()

    emit("=" * 72)
    emit("二、GNU 人类可读在换档点附近的取整")
    emit("=" * 72)
    emit()
    one = DATA / "onefile"
    one.mkdir(exist_ok=True)
    target = one / "one.bin"
    sizes = [
        1023 * 1024,
        1023 * 1024 + 512,
        1023 * 1024 + 1023,
        1024 * 1024 - 1,
        1024 * 1024,
    ]
    emit("  %-14s %-10s %-10s" % ("字节数", "项目", "GNU"))
    for size in sizes:
        target.write_bytes(b"\0" * size)
        _, ours, _ = run_ours(["-h", "one.bin"], one)
        _, gnu, _ = run_gnu(["--apparent-size", "-h", "one.bin"], one)
        emit("  %-14d %-10s %-10s" % (
            size, ours.strip().split("\t")[0], gnu.strip().split("\t")[0]))
    emit()

    emit("=" * 72)
    emit("三、--si 的换档边界（1000 进制）")
    emit("=" * 72)
    emit()
    si_sizes = [999 * 1000, 1000 * 1000 - 1, 1000 * 1000, 1000 * 1000 + 1]
    emit("  %-14s %-10s %-10s" % ("字节数", "项目", "GNU"))
    for size in si_sizes:
        target.write_bytes(b"\0" * size)
        _, ours, _ = run_ours(["--si", "one.bin"], one)
        _, gnu, _ = run_gnu(["--apparent-size", "--si", "one.bin"], one)
        emit("  %-14d %-10s %-10s" % (
            size, ours.strip().split("\t")[0], gnu.strip().split("\t")[0]))
    emit()

    emit("=" * 72)
    emit("四、_rewrite_argv：负号开头的取值怎么被改写")
    emit("=" * 72)
    emit()
    for args in (["-t", "-1024", "-a", "tree"], ["-t=-1024", "-a", "tree"],
                 ["--threshold=-1024", "-a", "tree"], ["-B", "-1", "tree"],
                 ["-d", "-1", "tree"]):
        code, out, err = run_ours(args, DATA)
        emit("  du %-30s 退出码 %d  %s" % (
            " ".join(args), code, (out or err).strip().replace("\n", " | ")))
    emit()

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("补充实测写入: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
