"""核实 teach/26 第 3 节里关于「自引用联接在 -x 下」那句话是否准确。

产出：打印结果即可（不落盘）
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "du_demo"


def run_ours(args: list[str], cwd: Path, timeout: int = 60) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "du", *args],
        cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    selfdir = DATA / "selfref"
    selfdir.mkdir(exist_ok=True)
    selflink = selfdir / "loop"
    if selflink.exists():
        subprocess.run(["cmd", "/c", "rmdir", str(selflink)], capture_output=True)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(selflink), str(selfdir)],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not selflink.exists():
        print("建不了自引用联接")
        return 1
    (selfdir / "f.txt").write_bytes(b"Q" * 100)

    print("自引用联接（E: 卷），各种选项的输出：")
    for args in (["-a", "selfref"], ["-a", "-x", "selfref"], ["-s", "selfref"],
                 ["-s", "-x", "selfref"]):
        code, out, err = run_ours(args, DATA)
        print("  du %-20s 退出码 %d，%d 行" % (
            " ".join(args), code, len(out.splitlines())))
        for ln in out.splitlines():
            print("      | %s" % ln)
        if err.strip():
            print("      E %s" % err.strip()[:200])

    print()
    lst = os.lstat(str(selflink))
    print("联接自己的 lstat st_ino = %d（稳定，_claim 靠它挡住第二次遇到）" % lst.st_ino)
    return 0


if __name__ == "__main__":
    sys.exit(main())
