"""探针 3：核实 GNU awk 的两个细节——多字符 FS 当正则、目录当文件用的退出码。

只读探查，不改项目源码。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "awk_probe"

AWK = shutil.which("awk") or shutil.which("gawk")
PYTHON = sys.executable


def run(cmd: list[str], cwd: Path) -> tuple[int, bytes, bytes]:
    proc = subprocess.run(
        cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    tmp = DATA / "fixture3"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    (tmp / "abcdef.txt").write_text("abcdef\n", encoding="utf-8")
    (tmp / "subdir").mkdir()

    print("--- 多字符 FS：GNU 按正则 ---")
    rc, out, err = run([AWK, "-F", "..", "{print $2}", "abcdef.txt"], tmp)
    print("rc=", rc, "out=", repr(out.decode()), "err=", repr(err.decode()[:120]))

    print("--- 多字符 FS：本实现按字面串 ---")
    rc, out, err = run(
        [PYTHON, str(ROOT / "main.py"), "awk-lite", "-F", "..", "{print $2}", "abcdef.txt"],
        tmp,
    )
    print("rc=", rc, "out=", repr(out.decode()), "err=", repr(err.decode()[:120]))

    print("--- 目录当文件用：GNU ---")
    rc, out, err = run([AWK, "{print $1}", "subdir"], tmp)
    print("rc=", rc, "out=", repr(out.decode()), "err=", repr(err.decode()[:160]))

    print("--- 目录当文件用：本实现 ---")
    rc, out, err = run(
        [PYTHON, str(ROOT / "main.py"), "awk-lite", "{print $1}", "subdir"], tmp
    )
    print("rc=", rc, "out=", repr(out.decode()), "err=", repr(err.decode()[:160]))

    shutil.rmtree(tmp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
