"""探针：实测 GNU du 8.32（Git Bash /usr/bin/du）的输出结构与选项行为。

方法论（沿用前几轮教训）：
- 结果一律写进文件再读，不靠 bash 工具的终端显示判断（它会把连续空格吃掉）
- 每行输出用 repr() 记录，空白与制表符看得见
- 语料用 write_bytes 写，落盘的是真 LF 字节
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "du_probe"
OUT = DATA / "probe_out.txt"

GNU_DU = r"E:\software\Git\Git\usr\bin\du.exe"


def build_fixture() -> None:
    """造一棵已知大小的目录树。"""
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)
    tree = DATA / "tree"
    tree.mkdir()
    (tree / "a.txt").write_bytes(b"A" * 10)
    (tree / "b.txt").write_bytes(b"B" * 2048)
    sub = tree / "sub"
    sub.mkdir()
    (sub / "c.txt").write_bytes(b"C" * 100)
    deeper = sub / "deeper"
    deeper.mkdir()
    (deeper / "d.txt").write_bytes(b"D" * 5)
    (tree / "empty").mkdir()


def run_du(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """跑一次 GNU du，返回 (退出码, stdout, stderr)。"""
    proc = subprocess.run(
        [GNU_DU, *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def show(title: str, code: int, out: str, err: str) -> None:
    lines = []
    lines.append(f"### {title}")
    lines.append(f"exit={code}")
    for line in out.splitlines():
        lines.append(f"OUT {line!r}")
    if not out and not code:
        lines.append("OUT <empty>")
    for line in err.splitlines():
        lines.append(f"ERR {line!r}")
    if not err:
        lines.append("ERR <empty>")
    lines.append("")
    return lines


def main() -> int:
    build_fixture()
    tree = DATA / "tree"

    chunks: list[str] = []
    chunks.append(f"fixture: {tree}")
    chunks.append("")

    # --- 1. 默认输出结构 ---
    for args in (
        ["tree"],
        ["-a", "tree"],
        ["-s", "tree"],
        ["-c", "tree"],
        ["-c", "-s", "tree"],
        ["-b", "tree"],
        ["--apparent-size", "tree"],
        ["-h", "tree"],
        ["--si", "tree"],
        ["-k", "tree"],
        ["-m", "tree"],
        ["-B", "1", "tree"],
        ["-B", "512", "tree"],
        ["-d", "0", "tree"],
        ["-d", "1", "tree"],
        ["-d", "2", "tree"],
        ["-a", "-d", "1", "tree"],
        ["-x", "tree"],
        ["-L", "tree"],
        ["-P", "tree"],
        ["-l", "tree"],
        ["-S", "tree"],
        ["--time", "tree"],
        ["-t", "1K", "tree"],
        ["-t", "-1K", "tree"],
        ["-0", "tree"],
        ["tree", "tree"],
        ["a.txt"],
        ["tree/a.txt"],
        ["tree/sub"],
        ["tree", "a.txt"],
        ["-a", "tree/a.txt"],
    ):
        code, out, err = run_du(args, cwd=DATA)
        chunks.extend(show("du " + " ".join(args), code, out, err))

    # --- 2. 错误路径 ---
    for args in (
        ["nosuch"],
        ["-d", "x", "tree"],
        ["-t", "bogus", "tree"],
        ["-B", "bogus", "tree"],
        ["--max-depth=-1", "tree"],
    ):
        code, out, err = run_du(args, cwd=DATA)
        chunks.extend(show("du " + " ".join(args), code, out, err))

    # --- 3. 多个操作数的顺序 ---
    code, out, err = run_du(["-s", "tree", "tree/a.txt", "tree/sub"], cwd=DATA)
    chunks.extend(show("du -s tree tree/a.txt tree/sub", code, out, err))

    # --- 4. Windows 侧 stat 能拿到什么 ---
    chunks.append("### python stat on fixture")
    for rel in ("tree/a.txt", "tree/b.txt", "tree/sub", "tree/empty", "tree"):
        p = DATA / rel
        st = p.stat()
        chunks.append(
            f"{rel}: size={st.st_size} blocks={getattr(st, 'st_blocks', 'N/A')} "
            f"blksize={getattr(st, 'st_blksize', 'N/A')} dev={st.st_dev} ino={st.st_ino}"
        )
    chunks.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(chunks), encoding="utf-8")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
