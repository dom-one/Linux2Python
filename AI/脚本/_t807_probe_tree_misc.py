"""探针七：剩下几个小语义点。

1. 操作数带结尾斜杠时，根目录那一行怎么打。
2. -f 配合 "." 操作数时的路径形态（源码注释说会变成 "./子目录/文件"）。
3. 统计行在出错时还打不打。
4. -x 对「根目录是文件」与「多操作数」的表现。
5. 根目录操作数是 "." 与 "./" 的区别。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = Path(os.path.dirname(os.path.dirname(HERE)))
DEMO = "AI/数据/tree_demo"


def _run(argv: list[str], cwd: str = str(ROOT)) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), *argv],
        cwd=cwd,
        capture_output=True,
        timeout=60,
    )
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", errors="replace"),
        proc.stderr.decode("utf-8", errors="replace"),
    )


def show(title: str, argv: list[str], cwd: str = str(ROOT)) -> None:
    code, out, err = _run(argv, cwd)
    print(f"\n--- {title} ---")
    print(f"$ python main.py {' '.join(argv)}   (cwd={cwd})")
    print(f"退出码 {code}")
    print(out.rstrip() if out else "(stdout 空)")
    if err.strip():
        print(f"stderr: {err.strip()}")


def main() -> None:
    show("1. 操作数带结尾斜杠", ["tree", DEMO + "/", "--noreport"])
    show("2. -f 配 '.' 操作数", ["tree", "-f", ".", "--noreport"], cwd=str(ROOT / "AI" / "数据" / "tree_demo"))
    show("3. 出错时统计行还打不打", ["tree", "nope"])
    show("4. -x 配多操作数", ["tree", "-x", DEMO, DEMO + "/sub"])
    show("5. 操作数是 '.'", ["tree", ".", "--noreport", "-L", "1"], cwd=str(ROOT / "AI" / "数据" / "tree_demo"))
    show("6. 操作数是 './'", ["tree", "./", "--noreport", "-L", "1"], cwd=str(ROOT / "AI" / "数据" / "tree_demo"))
    show("7. 绝对路径", ["tree", str(ROOT / "AI" / "数据" / "tree_demo" / "sub"), "--noreport"])
    show("8. -d 与 -P 同用", ["tree", "-d", "-P", "*.txt", DEMO])
    show("9. -i 与 -f 同用", ["tree", "-i", "-f", DEMO])


if __name__ == "__main__":
    main()
