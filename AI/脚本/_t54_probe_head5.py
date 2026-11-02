"""探针第五轮：头部与出错文件的先后关系。

要回答三个问题：
1. 打开失败的文件会不会先打头部？
2. 中间失败的文件会不会占掉「空行分隔」的位置？
3. 多个失败文件时错误信息的顺序
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
DATA = AI_DIR / "数据"

GNU_HEAD = r"C:\Program Files\Git\usr\bin\head.exe"


def locate_head() -> str:
    candidate = shutil.which("head")
    if candidate and "System32" not in candidate:
        return candidate
    return GNU_HEAD


def show(title: str, args: list[str], cwd: Path, stdin: bytes = b"") -> None:
    proc = subprocess.run(
        [locate_head(), *args],
        cwd=str(cwd),
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    print(f"--- {title}")
    print(f"    argv   : head {' '.join(args)}")
    print(f"    exit   : {proc.returncode}")
    print(f"    stdout : {proc.stdout!r}")
    print(f"    stderr : {proc.stderr!r}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    DATA.mkdir(parents=True, exist_ok=True)

    root = Path(tempfile.mkdtemp(prefix="probe_head5_"))
    try:
        (root / "a.txt").write_bytes(b"l1\nl2\nl3\n")
        (root / "b.txt").write_bytes(b"x\n")
        (root / "sub").mkdir()

        print("=" * 70)
        print("Z1. 打不开的文件要不要头部")
        show("存在 + 不存在（默认带头）", ["a.txt", "missing.txt"], root)
        show("存在 + 不存在（-v）", ["-v", "a.txt", "missing.txt"], root)
        show("只有不存在的（-v）", ["-v", "missing.txt"], root)
        show("只有不存在的（默认，1 个文件）", ["missing.txt"], root)
        show("两个都不存在的", ["m1.txt", "m2.txt"], root)

        print("=" * 70)
        print("Z2. 中间失败的文件占不占空行分隔")
        show("a + 缺失 + b", ["a.txt", "missing.txt", "b.txt"], root)
        show("a + 目录 + b", ["a.txt", "sub", "b.txt"], root)

        print("=" * 70)
        print("Z3. 目录当文件")
        show("目录单独", ["sub"], root)
        show("目录 + 文件", ["sub", "a.txt"], root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
