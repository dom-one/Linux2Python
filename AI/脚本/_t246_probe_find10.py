"""探针 10：两处环境细节。

1) 目录的 st_size：GNU find 的 -size 0 命中根目录，说明 MSYS 侧看到的目录大小是 0；
   Python 的 os.lstat 可能给出非 0 的值。逐个目录打印两边的数值。
2) cmd /c 的输出编码：Windows 控制台默认 GBK，MSYS 的 echo 输出 UTF-8。
   对比 cmd /c echo 与 cmd /c "chcp 65001 & echo" 的字节。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "_data_find10"
GNU_FIND = shutil.which("find") or r"E:\software\Git\Git\usr\bin\find.exe"
GNU_STAT = r"E:\software\Git\Git\usr\bin\stat.exe"


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    tree = OUT_DIR / "tree"
    tree.mkdir()
    (tree / "sub").mkdir()
    (tree / "a.txt").write_bytes(b"x\n")

    lines: list[str] = ["### 目录的 st_size"]
    for path in (tree, tree / "sub", OUT_DIR):
        st = os.lstat(path)
        lines.append(f"Python lstat {path} -> st_size={st.st_size}")
        proc = subprocess.run(
            [GNU_STAT, "-c", "%s %n", path.as_posix()],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        lines.append(f"MSYS  stat       {path} -> {proc.stdout.strip()}")
    lines.append("")

    lines.append("### cmd /c echo 的输出字节（含中文路径）")
    target = (tree / "a.txt").as_posix()
    for label, argv in (
        ("cmd /c echo", ["cmd", "/c", "echo", target]),
        ("cmd /c chcp65001 & echo", ["cmd", "/c", f"chcp 65001>nul & echo {target}"]),
        ("cmd /c echo（list2cmdline 引用）", ["cmd", "/c", subprocess.list2cmdline(["echo", target])]),
    ):
        proc = subprocess.run(argv, capture_output=True)
        lines.append(f"{label}:")
        lines.append(f"  returncode={proc.returncode}")
        lines.append(f"  stdout bytes={proc.stdout!r}")
        lines.append(f"  试着按 UTF-8 解码: {proc.stdout.decode('utf-8', 'replace').strip()!r}")
    lines.append("")

    lines.append("### MSYS echo 的输出字节（作为对照）")
    proc = subprocess.run(
        [r"E:\software\Git\Git\usr\bin\echo.exe", target],
        capture_output=True,
    )
    lines.append(f"  stdout bytes={proc.stdout!r}")
    lines.append("")

    lines.append("### GNU find -size 0 命中哪些")
    proc = subprocess.run([GNU_FIND, tree.as_posix(), "-size", "0"], capture_output=True, text=True)
    lines.append(proc.stdout)

    (OUT_DIR / "probe10.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"probe10 写入 {OUT_DIR / 'probe10.txt'}")


if __name__ == "__main__":
    main()
