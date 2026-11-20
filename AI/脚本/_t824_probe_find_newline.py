"""探针：确认 find 管道输出的换行符现状，以及 Windows 侧的 exec 目标可用性。

用法: python AI/脚本/_t824_probe_find_newline.py
产出: AI/数据/find_fix/newline.txt
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
BASE = AI_DIR / "数据" / "find_fix"
ROOT = AI_DIR.parent


def main() -> int:
    BASE.mkdir(parents=True, exist_ok=True)
    tree = BASE / "tree9"
    tree.mkdir(parents=True, exist_ok=True)
    (tree / "a.txt").write_bytes(b"alpha\n")

    lines: list[str] = ["# 由 _t824_probe_find_newline.py 生成，勿手改"]

    # 1. 本项目 find 走管道时的原始字节
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "find", ".", "-name", "*.txt"],
        cwd=tree,
        capture_output=True,
    )
    lines.append(f"[本项目 find 管道输出] stdout 原始字节 = {proc.stdout!r}")
    lines.append(f"  含 CR: {b'\\r' in proc.stdout}  含 LF: {b'\\n' in proc.stdout}")

    # 2. GNU find 走管道时的原始字节（经 bash，避开 MSYS 改写 argv）
    script = BASE / "_t824_gnu.sh"
    script.write_text(
        f"cd '{tree.as_posix()}'\n/usr/bin/find . -name '*.txt'\n",
        encoding="utf-8",
    )
    bash = shutil.which("bash") or r"E:\software\Git\Git\bin\bash.exe"
    proc2 = subprocess.run([bash, str(script)], capture_output=True)
    lines.append(f"[GNU find 管道输出] stdout 原始字节 = {proc2.stdout!r}")
    lines.append(f"  含 CR: {b'\\r' in proc2.stdout}  含 LF: {b'\\n' in proc2.stdout}")

    # 3. Windows 侧的 exec 目标是否存在（决定差分脚本用哪个命令）
    for name in ("printf", "echo", "cat", "python", "python3"):
        path = shutil.which(name)
        lines.append(f"which {name} = {path}")

    (BASE / "newline.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
