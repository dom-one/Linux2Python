"""探针 7：补齐实现前最后几个待定口径。

1. -h 打开时阈值的比较单位（块还是字节）
2. 操作数带尾斜杠时显示路径长什么样
3. -c 的 total 行在 -h 下是什么格式
4. -s 与 -a 同时给是不是报错
5. -d 负数、-B 0 等非法值的报错文案与退出码
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "du_probe7"
OUT = DATA / "probe_out.txt"

GNU_DU = r"E:\software\Git\Git\usr\bin\du.exe"


def run_du(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        [GNU_DU, *args],
        cwd=str(DATA),
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
    tree = DATA / "tree"
    tree.mkdir()
    (tree / "a.txt").write_bytes(b"x" * 10)
    (tree / "b.txt").write_bytes(b"y" * 2048)
    (tree / "sub").mkdir()
    (tree / "sub" / "c.txt").write_bytes(b"z" * 100)

    lines: list[str] = []

    cases = [
        ["-t", "1K", "-a", "tree"],
        ["-h", "-t", "1K", "-a", "tree"],
        ["-b", "-t", "1K", "-a", "tree"],
        ["--apparent-size", "-t", "1K", "-a", "tree"],
        ["-h", "--apparent-size", "-t", "1K", "-a", "tree"],
        ["tree/"],
        ["-s", "tree/"],
        ["./tree"],
        ["-c", "-h", "tree"],
        ["-c", "--si", "--apparent-size", "tree"],
        ["-s", "-a", "tree"],
        ["-d", "-1", "tree"],
        ["-B", "0", "tree"],
        ["-B", "-1", "tree"],
        ["-t", "0", "tree"],
        ["-t", "1M", "-a", "tree"],
        ["--time", "-s", "tree"],
        ["-0", "-s", "tree"],
        ["-a", "-c", "tree"],
    ]
    for args in cases:
        code, out, err = run_du(args)
        lines.append(f"### du {' '.join(args)}  exit={code}")
        for line in out.splitlines():
            lines.append(f"OUT {line!r}")
        if out and not out.endswith("\n"):
            lines.append("OUT <no trailing newline>")
        for line in err.splitlines():
            lines.append(f"ERR {line!r}")
        lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
