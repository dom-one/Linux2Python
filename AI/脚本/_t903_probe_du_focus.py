"""du 的三个专项实测：人类可读取整的档位边界、目录联接（junction）、
以及若干语义细节与 GNU 的对照。

产出：AI/数据/du_focus.txt
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "du_demo"
OUT = ROOT / "AI" / "数据" / "du_focus.txt"
GNU_DU = Path(r"E:\software\Git\Git\usr\bin\du.exe")

lines: list[str] = []


def emit(text: str = "") -> None:
    lines.append(text)


def run_ours(args: list[str], cwd: Path, timeout: int = 30) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "du", *args],
        cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def run_gnu(args: list[str], cwd: Path, timeout: int = 30) -> tuple[int, str, str]:
    proc = subprocess.run(
        [str(GNU_DU), *args], cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def main() -> None:
    if not DATA.is_dir():
        print("夹具不存在，先跑 _t900_make_du_fixture.py")
        return 1

    emit("=" * 72)
    emit("一、-h 人类可读的档位边界：项目 vs GNU")
    emit("=" * 72)
    emit()
    emit("造一批落在 999K ~ 1M 之间的文件，看两边各自选哪个单位。")
    emit()
    band = DATA / "band"
    band.mkdir(exist_ok=True)
    sizes = [999 * 1024, 1000 * 1024, 1000 * 1024 + 1, 1010 * 1024,
             1023 * 1024, 1023 * 1024 + 1023, 1024 * 1024 - 1, 1024 * 1024]
    for size in sizes:
        (band / ("b%d.bin" % size)).write_bytes(b"\0" * size)
    _, ours_a, _ = run_ours(["-a", "-h", "band"], DATA)
    _, gnu_a, _ = run_gnu(["--apparent-size", "-a", "-h", "band"], DATA)

    def parse(text: str) -> dict[str, str]:
        out = {}
        for ln in text.splitlines():
            size_text, _, path = ln.partition("\t")
            out[path] = size_text
        return out

    ours_map = parse(ours_a)
    gnu_map = parse(gnu_a)

    def sort_key(path: str) -> int:
        digits = "".join(ch for ch in path.rsplit("/", 1)[-1] if ch.isdigit())
        return int(digits) if digits else -1

    emit("  %-20s %-12s %-12s %s" % ("文件", "项目", "GNU", ""))
    for path in sorted(ours_map, key=sort_key):
        mark = "一致" if ours_map.get(path) == gnu_map.get(path) else "★不一致"
        emit("  %-20s %-12s %-12s %s" % (
            path, ours_map.get(path), gnu_map.get(path), mark))
    emit()

    emit("  结论：把字节数换算成 1024 进制后，商落在 [1000, 1024) 这一段时，")
    emit("        GNU 继续用 K（显示 1000K~1023K），本实现换成 M（显示 1.0M）。")
    emit()

    emit("=" * 72)
    emit("二、目录联接（junction）")
    emit("=" * 72)
    emit()
    emit("Windows 的 mklink /J 建目录联接不需要管理员权限，")
    emit("而 Python 的 os.symlink 需要（实测报 WinError 1314）。")
    emit()
    jdir = DATA / "junc"
    jdir.mkdir(exist_ok=True)
    target = DATA / "tree"
    link = jdir / "to_tree"
    if link.exists():
        # 上次跑留下的，先用 cmd 的 rmdir 删（联接不是普通目录）
        subprocess.run(["cmd", "/c", "rmdir", str(link)], capture_output=True)
    made = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    emit("  mklink /J 输出: %s" % (made.stdout.strip() or made.stderr.strip()))
    emit()
    if link.exists():
        code, out, err = run_ours(["-s", "junc"], DATA)
        emit("  项目 du -s junc  退出码 %d -> %s" % (code, out.strip()))
        code, out, err = run_ours(["-a", "junc"], DATA)
        emit("  项目 du -a junc  退出码 %d:" % code)
        for ln in out.splitlines():
            emit("    | %s" % ln)
        code, out, err = run_gnu(["--apparent-size", "-s", "junc"], DATA)
        emit("  GNU  du -s junc  退出码 %d -> %s" % (code, out.strip()))
        code, out, err = run_gnu(["--apparent-size", "-a", "junc"], DATA)
        emit("  GNU  du -a junc  退出码 %d:" % code)
        for ln in out.splitlines():
            emit("    | %s" % ln)
    emit()

    emit("=" * 72)
    emit("三、语义细节与 GNU 对照")
    emit("=" * 72)
    emit()
    checks = [
        ("-t 0（阈值为 0 是不过滤还是滤掉空条目）",
         ["-t", "0", "-a", "tree"], ["--apparent-size", "-t", "0", "-a", "tree"]),
        ("-s 与 -d 1 同时给",
         ["-s", "-d", "1", "tree"], ["--apparent-size", "-s", "-d", "1", "tree"]),
        ("-a 与 -d 0 同时给",
         ["-a", "-d", "0", "tree"], ["--apparent-size", "-a", "-d", "0", "tree"]),
        ("-a 与 -c 同时给",
         ["-a", "-c", "tree"], ["--apparent-size", "-a", "-c", "tree"]),
        ("-S 与 -a 同时给",
         ["-S", "-a", "tree"], ["--apparent-size", "-S", "-a", "tree"]),
        ("--time 与 -0 同时给",
         ["--time", "-0", "-s", "tree"], ["--apparent-size", "--time", "-0", "-s", "tree"]),
        ("-x 作用在文件操作数上",
         ["-x", "-s", "tree/a.txt"], ["--apparent-size", "-x", "-s", "tree/a.txt"]),
        ("-k 显式给 1K",
         ["-k", "-s", "tree"], ["--apparent-size", "-k", "-s", "tree"]),
        ("-m 显式给 1M",
         ["-m", "-s", "tree"], ["--apparent-size", "-m", "-s", "tree"]),
        ("-b 与 -h 同时给（后者赢）",
         ["-b", "-h", "-s", "tree"], ["--apparent-size", "-b", "-h", "-s", "tree"]),
    ]
    for title, ours_args, gnu_args in checks:
        o_code, o_out, o_err = run_ours(ours_args, DATA)
        g_code, g_out, g_err = run_gnu(gnu_args, DATA)
        same = (o_out == g_out and o_code == g_code)
        emit("--- %s" % title)
        emit("    项目: 退出码 %d  %s" % (o_code, o_out.strip().replace("\n", " | ")))
        if o_err.strip():
            emit("          stderr: %s" % o_err.strip())
        emit("    GNU : 退出码 %d  %s" % (g_code, g_out.strip().replace("\n", " | ")))
        if g_err.strip():
            emit("          stderr: %s" % g_err.strip())
        emit("    => %s" % ("逐字节一致" if same else "★有差异"))
        emit()

    emit("=" * 72)
    emit("四、--time 的时间列是哪个时间")
    emit("=" * 72)
    emit()
    emit("目录的时间戳取的是它下面最新的文件，还是目录自己？")
    emit()
    _, ours_t, _ = run_ours(["--time", "-a", "tree"], DATA)
    _, gnu_t, _ = run_gnu(["--apparent-size", "--time", "-a", "tree"], DATA)
    emit("  项目:")
    for ln in ours_t.splitlines():
        emit("    | %s" % ln)
    emit("  GNU :")
    for ln in gnu_t.splitlines():
        emit("    | %s" % ln)
    emit()

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("专项实测写入: %s" % OUT)
    print("共 %d 行" % len(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
