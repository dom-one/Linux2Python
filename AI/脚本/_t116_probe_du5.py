"""探针 5：确认 --si 的 1000 进制单位阶梯、IEC 的 T/P 档，以及 -h 与 --si 的先后顺序规则。

注意：--si 与 -h 都设置「人类可读」，GNU 里后者（命令行上更靠后的那个）生效。
所以要单独测 SI，不能写成 `--si -h`（-h 在后面会覆盖掉 --si 的 1000 进制）。
"""

from __future__ import annotations

import ctypes
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "du_probe5"
OUT = DATA / "probe_out.txt"

GNU_DU = r"E:\software\Git\Git\usr\bin\du.exe"


def make_sparse(path: Path, size: int) -> None:
    if size == 0:
        path.write_bytes(b"")
        return
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateFileW(str(path), 0x40000000, 0, None, 2, 0x80, None)
    if handle == -1 or handle == 0xFFFFFFFFFFFFFFFF:
        raise OSError(f"CreateFileW 失败: {path}")
    try:
        distance = ctypes.c_longlong(size)
        kernel32.SetFilePointerEx(handle, distance, None, 0)
        kernel32.SetEndOfFile(handle)
    finally:
        kernel32.CloseHandle(handle)


def run_du(args: list[str]) -> str:
    proc = subprocess.run(
        [GNU_DU, *args],
        cwd=str(DATA),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = proc.stdout.strip()
    return out if out else f"<empty rc={proc.returncode} err={proc.stderr.strip()!r}>"


def main() -> int:
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)

    lines: list[str] = []

    # --- SI 阶梯：--si 必须单独出现（-h 会覆盖它）---
    lines.append("### --si 阶梯（命令：du --si --apparent-size <file>）")
    for size in (999, 1000, 1001, 1024, 1025, 999999, 10**6, 10**6 + 1,
                 10**9, 10**12, 10**15):
        f = DATA / f"s{size}.bin"
        make_sparse(f, size)
        si = run_du(["--si", "--apparent-size", f.name]).split("\t")[0]
        iec = run_du(["-h", "--apparent-size", f.name]).split("\t")[0]
        lines.append(f"{size}\tsi={si}\tiec={iec}")
    lines.append("")

    # --- IEC 的 T/P 档 ---
    lines.append("### IEC T/P 档")
    for size in (10**12, 2 * 10**12, 10**15, 10**18):
        f = DATA / f"i{size}.bin"
        make_sparse(f, size)
        lines.append(f"{size}\tiec={run_du(['-h', '--apparent-size', f.name]).split(chr(9))[0]}")
    lines.append("")

    # --- -h 与 --si 的先后顺序 ---
    lines.append("### -h / --si 顺序")
    f = DATA / "ord.bin"
    make_sparse(f, 1536)
    for args in (
        ["--si", "-h", f.name],
        ["-h", "--si", f.name],
        ["--si", "--apparent-size", f.name],
        ["-h", "--apparent-size", f.name],
    ):
        lines.append(f"du {' '.join(args)} -> {run_du(args).split(chr(9))[0]}")
    lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
