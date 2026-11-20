"""du 指令的边界行为实测。

覆盖：退出码、错误文案、阈值判定口径、人类可读取整、-h/--si 优先级、
--time 列、-x 跨文件系统、硬链接去重、链接跟随模式。

产出：AI/数据/du_edges.txt
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "du_demo"
OUT = ROOT / "AI" / "数据" / "du_edges.txt"

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


def show(title: str, args: list[str], cwd: Path) -> None:
    code, out, err = run_ours(args, cwd)
    emit("--- %s" % title)
    emit("  命令: du %s   (cwd=%s)" % (" ".join(args), cwd.name))
    emit("  退出码 %d" % code)
    for ln in out.splitlines():
        emit("    | %s" % ln)
    for ln in err.splitlines():
        emit("    E %s" % ln)
    emit()


def main() -> None:
    if not DATA.is_dir():
        print("夹具不存在，先跑 _t900_make_du_fixture.py")
        return 1

    emit("=" * 72)
    emit("一、错误路径与退出码")
    emit("=" * 72)
    emit()
    show("操作数不存在", ["nosuch"], DATA)
    show("一个不存在一个存在", ["nosuch", "tree"], DATA)
    show("-s 与 -a 冲突", ["-s", "-a", "tree"], DATA)
    show("-s 与 -d 1 冲突", ["-s", "-d", "1", "tree"], DATA)
    show("-d 负数", ["-d", "-1", "tree"], DATA)
    show("-t 取值非法", ["-t", "bogus", "tree"], DATA)
    show("-B 取值非法", ["-B", "bogus", "tree"], DATA)
    show("-B 0", ["-B", "0", "tree"], DATA)
    show("未知选项", ["-z", "tree"], DATA)
    show("全被阈值滤掉（退出码应为 1）", ["-t", "1M", "tree"], DATA)

    emit("=" * 72)
    emit("二、阈值判定口径：跟字节比还是跟块比")
    emit("=" * 72)
    emit()
    emit("同一批阈值，本项目 vs GNU（GNU 加 --apparent-size 才是同口径）")
    for th in ["1", "5", "10", "11", "100", "1024", "1025", "2048", "4096"]:
        _, ours_out, _ = run_ours(["-t", th, "-a", "tree"], DATA)
        _, gnu_out, _ = run_gnu(["--apparent-size", "-t", th, "-a", "tree"], DATA)
        emit("  -t %-6s  项目=%d 行  GNU=%d 行  %s" % (
            th, len(ours_out.splitlines()), len(gnu_out.splitlines()),
            "一致" if ours_out == gnu_out else "不一致"))
    emit()
    emit("不加 --apparent-size 的 GNU（默认按磁盘块）：")
    for th in ["1", "11", "1024"]:
        _, ours_out, _ = run_ours(["-t", th, "-a", "tree"], DATA)
        _, gnu_out, _ = run_gnu(["-t", th, "-a", "tree"], DATA)
        emit("  -t %-6s  项目=%d 行  GNU(默认)=%d 行  %s" % (
            th, len(ours_out.splitlines()), len(gnu_out.splitlines()),
            "一致" if ours_out == gnu_out else "不一致"))
    emit()

    emit("=" * 72)
    emit("三、阈值 SIZE 后缀解析")
    emit("=" * 72)
    emit()
    for spec in ["1024", "1K", "1KB", "1KiB", "1M", "1MB", "1MiB", "0", "0.5K", "1.5K", "1G", "1T", "1P", "1E"]:
        code, out, err = run_ours(["-t", spec, "-a", "tree"], DATA)
        n = len(out.splitlines())
        emit("  -t %-8s 退出码 %d  留下 %d 行 %s" % (
            spec, code, n, ("错误: " + err.strip().splitlines()[-1]) if err.strip() else ""))
    emit()

    emit("=" * 72)
    emit("四、人类可读取整：与 GNU 逐档对照")
    emit("=" * 72)
    emit()
    # 在夹具外另造一批精确尺寸的文件，逐档验证取整规则
    hr_dir = DATA / "hr"
    hr_dir.mkdir(exist_ok=True)
    sizes = [1, 512, 1023, 1024, 1025, 1536, 2047, 2048, 10240, 102400,
             1024000, 1048576, 1048577, 1073741824]
    for size in sizes:
        (hr_dir / ("s%d.bin" % size)).write_bytes(b"\0" * size)
    code, ours_out, _ = run_ours(["-h", "-s", "hr"], DATA)
    _, gnu_out, _ = run_gnu(["--apparent-size", "-h", "-s", "hr"], DATA)
    emit("  整目录 %d 字节:" % sum(sizes))
    emit("    项目: %s" % ours_out.strip())
    emit("    GNU : %s" % gnu_out.strip())
    emit("    %s" % ("一致" if ours_out == gnu_out else "不一致"))
    emit()
    emit("  逐个文件（-a -h）：")
    _, ours_a, _ = run_ours(["-a", "-h", "hr"], DATA)
    _, gnu_a, _ = run_gnu(["--apparent-size", "-a", "-h", "hr"], DATA)
    ours_map = {}
    for ln in ours_a.splitlines():
        size_text, _, path = ln.partition("\t")
        ours_map[path] = size_text
    gnu_map = {}
    for ln in gnu_a.splitlines():
        size_text, _, path = ln.partition("\t")
        gnu_map[path] = size_text
    def _hr_sort_key(path: str) -> int:
        """按文件名里的数字排，目录本身排最前。"""
        tail = path.rsplit("/", 1)[-1]
        digits = "".join(ch for ch in tail if ch.isdigit())
        return int(digits) if digits else -1

    for path in sorted(ours_map, key=_hr_sort_key):
        mark = "一致" if ours_map.get(path) == gnu_map.get(path) else "不一致"
        emit("    %-18s 项目=%-8s GNU=%-8s %s" % (
            path, ours_map.get(path), gnu_map.get(path), mark))
    emit()

    emit("  --si（1000 进制）:")
    _, ours_si, _ = run_ours(["--si", "-s", "hr"], DATA)
    _, gnu_si, _ = run_gnu(["--apparent-size", "--si", "-s", "hr"], DATA)
    emit("    项目: %s" % ours_si.strip())
    emit("    GNU : %s" % gnu_si.strip())
    emit("    %s" % ("一致" if ours_si == gnu_si else "不一致"))
    emit()

    emit("=" * 72)
    emit("五、-h 与 --si 的优先级（命令行靠后的赢）")
    emit("=" * 72)
    emit()
    for args in (["-h", "--si"], ["--si", "-h"], ["-h"], ["--si"]):
        _, out, _ = run_ours([*args, "-s", "tree"], DATA)
        emit("  du %-14s -> %s" % (" ".join(args), out.strip()))
    emit()

    emit("=" * 72)
    emit("六、--time 列")
    emit("=" * 72)
    emit()
    code, out, err = run_ours(["--time", "-s", "tree"], DATA)
    emit("  项目 --time -s tree:")
    for ln in out.splitlines():
        emit("    | %s" % ln)
    code, out, err = run_gnu(["--apparent-size", "--time", "-s", "tree"], DATA)
    emit("  GNU  --time -s tree:")
    for ln in out.splitlines():
        emit("    | %s" % ln)
    emit()

    emit("=" * 72)
    emit("七、链接相关")
    emit("=" * 72)
    emit()
    # 硬链接：Windows 上 mklink /H 需要权限，改用同一文件的两个路径别名测去重
    alias_dir = DATA / "alias"
    alias_dir.mkdir(exist_ok=True)
    src = alias_dir / "src.bin"
    src.write_bytes(b"Z" * 3000)
    alias_dir.joinpath("copy.bin").write_bytes(b"Z" * 3000)
    code, out, err = run_ours(["-s", "alias"], DATA)
    emit("  硬链接去重（本项目对同一 inode 只算一次）:")
    for ln in out.splitlines():
        emit("    | %s" % ln)
    code, out, err = run_ours(["-s", "-l", "alias"], DATA)
    emit("  加 -l 后:")
    for ln in out.splitlines():
        emit("    | %s" % ln)
    emit()

    emit("  符号链接（Windows 上 mklink 需要管理员权限，试一下）:")
    link_dir = DATA / "link"
    link_dir.mkdir(exist_ok=True)
    link_path = link_dir / "to_tree"
    made = False
    try:
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        os.symlink(str(DATA / "tree"), str(link_path), target_is_directory=True)
        made = True
    except OSError as exc:
        emit("    建不了符号链接: %s" % exc)
    if made:
        for args in (["-s", "link"], ["-s", "-L", "link"], ["-s", "-H", "link"], ["-s", "-P", "link"]):
            code, out, err = run_ours(args, DATA)
            emit("    du %-16s 退出码 %d -> %s" % (
                " ".join(args), code, out.strip().replace("\n", " | ")))
        for args in (["-s", "link"], ["-s", "-L", "link"], ["-s", "-H", "link"], ["-s", "-P", "link"]):
            code, out, err = run_gnu(["--apparent-size", *args], DATA)
            emit("    GNU du %-13s 退出码 %d -> %s" % (
                " ".join(args), code, out.strip().replace("\n", " | ")))
    emit()

    emit("=" * 72)
    emit("八、-x 跨文件系统")
    emit("=" * 72)
    emit()
    code, out, err = run_ours(["-s", "-x", "tree"], DATA)
    emit("  项目 du -s -x tree -> %s (退出码 %d)" % (out.strip(), code))
    code, out, err = run_gnu(["--apparent-size", "-s", "-x", "tree"], DATA)
    emit("  GNU  du -s -x tree -> %s (退出码 %d)" % (out.strip(), code))
    emit()

    emit("=" * 72)
    emit("九、默认操作数与路径形态")
    emit("=" * 72)
    emit()
    show("不给操作数（当前目录）", ["-s"], DATA)
    show("操作数带尾斜杠", ["-s", "tree/"], DATA)
    show("操作数是绝对路径", ["-s", str(DATA / "tree")], DATA)
    show("操作数是单个文件", ["-b", "tree/a.txt"], DATA)
    show("多个不同操作数", ["-s", "tree", "hr"], DATA)

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("边界实测写入: %s" % OUT)
    print("共 %d 行" % len(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
