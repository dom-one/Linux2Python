"""探针 6：补齐三件事——T 档单位字母、多操作数里有缺失时的行为、目录读不了时的行为。

T 档要 1TB 稀疏文件：ctypes 的 SetFilePointerEx 在本盘失败，改用 fsutil
（fsutil 是控制台程序走 ANSI 代码页，所以路径必须全 ASCII，放在临时目录里）。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "du_probe6"
OUT = DATA / "probe_out.txt"

GNU_DU = r"E:\software\Git\Git\usr\bin\du.exe"


def run_du(args: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [GNU_DU, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)

    lines: list[str] = []

    # --- 1. T 档 ---
    tmp = Path(tempfile.gettempdir()) / "du_probe6_ascii"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    for size in (10**12, 2 * 10**12, 10**15):
        target = tmp / f"big{size}.bin"
        proc = subprocess.run(
            ["fsutil", "file", "createnew", str(target), str(size)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        actual = target.stat().st_size if target.exists() else -1
        lines.append(f"### fsutil createnew {size} -> actual={actual} err={proc.stderr.strip()!r}")
        if actual != size:
            continue
        for args in (["-h", "--apparent-size"], ["--si", "--apparent-size"], ["-b"]):
            code, out, err = run_du([*args, target.name], tmp)
            lines.append(f"du {' '.join(args)} exit={code} out={out.strip()!r} err={err.strip()!r}")
        lines.append("")
    shutil.rmtree(tmp, ignore_errors=True)

    # --- 2. 多操作数里有缺失 ---
    (DATA / "real.txt").write_bytes(b"hello")
    (DATA / "realdir").mkdir()
    (DATA / "realdir" / "inner.txt").write_bytes(b"x" * 50)
    for args in (
        ["real.txt", "nosuch"],
        ["nosuch", "real.txt"],
        ["nosuch1", "nosuch2"],
        ["-s", "real.txt", "nosuch"],
    ):
        code, out, err = run_du(args, DATA)
        lines.append(f"### du {' '.join(args)} exit={code}")
        for line in out.splitlines():
            lines.append(f"OUT {line!r}")
        for line in err.splitlines():
            lines.append(f"ERR {line!r}")
        lines.append("")

    # --- 3. 目录读不了 ---
    blocked = DATA / "blocked"
    blocked.mkdir()
    (blocked / "inside.txt").write_bytes(b"y" * 10)
    lines.append(f"### 目录权限（Windows 上没法造不可读目录，跳过）blocked={blocked}")
    lines.append("")

    # --- 4. 空操作数 ---
    code, out, err = run_du([], DATA)
    lines.append(f"### du（无操作数）exit={code} out={out.strip()!r} err={err.strip()!r}")
    lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
