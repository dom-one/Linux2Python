"""探针第二轮：补齐 GNU head 的边角行为。

关注：MSYS 换行翻译、多文件空行位置、乘数后缀、-q/-v 同开、长选项、
stdin 重复出现等。
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

GNU_CAT = r"C:\Program Files\Git\usr\bin\cat.exe"
GNU_HEAD = r"C:\Program Files\Git\usr\bin\head.exe"


def locate(name: str, fallback: str) -> str:
    candidate = shutil.which(name)
    if candidate and "System32" not in candidate:
        return candidate
    return fallback


def run(exe: str, args: list[str], cwd: Path, stdin: bytes = b"") -> tuple[int, bytes, bytes]:
    proc = subprocess.run(
        [exe, *args],
        cwd=str(cwd),
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.returncode, proc.stdout, proc.stderr


def show(title: str, args: list[str], cwd: Path, stdin: bytes = b"", exe: str | None = None) -> None:
    exe = exe or locate("head", GNU_HEAD)
    code, out, err = run(exe, args, cwd, stdin)
    print(f"--- {title}")
    print(f"    argv   : {Path(exe).name} {' '.join(args)}")
    print(f"    exit   : {code}")
    print(f"    stdout : {out!r}")
    if err:
        print(f"    stderr : {err!r}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    DATA.mkdir(parents=True, exist_ok=True)

    root = Path(tempfile.mkdtemp(prefix="probe_head2_"))
    try:
        (root / "a.txt").write_text("l1\nl2\nl3\nl4\nl5\n", encoding="utf-8")
        (root / "b.txt").write_text("x\n", encoding="utf-8")
        (root / "nonl.txt").write_text("p1\np2\np3", encoding="utf-8")
        (root / "lone_cr.txt").write_bytes(b"r1\rXX\n")
        (root / "crlf.txt").write_bytes(b"c1\r\nc2\r\n")
        (root / "big.txt").write_bytes(b"0123456789" * 20)

        print("=" * 70)
        print("J. MSYS 是否翻译换行（对比 cat 与 head 读同一个 LF 文件）")
        show("cat 读 LF 文件", ["a.txt"], root, exe=locate("cat", GNU_CAT))
        show("head 读 LF 文件", ["a.txt"], root)
        show("cat 读 lone CR 文件", ["lone_cr.txt"], root, exe=locate("cat", GNU_CAT))
        show("head 读 lone CR 文件", ["lone_cr.txt"], root)
        show("cat 读 CRLF 文件", ["crlf.txt"], root, exe=locate("cat", GNU_CAT))

        print("=" * 70)
        print("K. 多文件头部空行位置")
        show("三文件带头", ["a.txt", "b.txt", "nonl.txt"], root)
        show("末行无换行的文件放在中间", ["a.txt", "nonl.txt", "b.txt"], root)
        show("单文件 -v 后接另一文件", ["-v", "a.txt", "b.txt"], root)

        print("=" * 70)
        print("L. -q 与 -v 同开")
        show("-q -v 两文件", ["-q", "-v", "a.txt", "b.txt"], root)
        show("-v -q 两文件", ["-v", "-q", "a.txt", "b.txt"], root)

        print("=" * 70)
        print("M. 乘数后缀")
        show("-c 1K", ["-c", "1K", "big.txt"], root)
        show("-c 1k", ["-c", "1k", "big.txt"], root)
        show("-c 1b", ["-c", "1b", "big.txt"], root)
        show("-c 10", ["-c", "10", "big.txt"], root)
        show("-c 1KiB", ["-c", "1KiB", "big.txt"], root)

        print("=" * 70)
        print("N. 长选项")
        show("--lines=2", ["--lines=2", "a.txt"], root)
        show("--bytes=5", ["--bytes=5", "a.txt"], root)
        show("--lines=-2", ["--lines=-2", "a.txt"], root)
        show("--bytes=-2", ["--bytes=-2", "a.txt"], root)
        show("--quiet", ["--quiet", "a.txt", "b.txt"], root)
        show("--silent", ["--silent", "a.txt", "b.txt"], root)
        show("--verbose", ["--verbose", "a.txt"], root)
        show("--zero-terminated", ["--zero-terminated", "a.txt"], root)

        print("=" * 70)
        print("O. stdin 细节")
        show("stdin 配 -n 2", ["-n", "2"], root, stdin=b"s1\ns2\ns3\n")
        show("stdin 配 -c 3", ["-c", "3"], root, stdin=b"s1\ns2\ns3\n")
        show("两个 - 操作数", ["-", "-"], root, stdin=b"s1\ns2\n")
        show("stdin 在两文件中间", ["b.txt", "-", "b.txt"], root, stdin=b"s1\ns2\n")

        print("=" * 70)
        print("P. 空文件与 0 的边界")
        show("-n 0 两文件", ["-n", "0", "a.txt", "b.txt"], root)
        show("-c 0 两文件", ["-c", "0", "a.txt", "b.txt"], root)

        print("=" * 70)
        print("Q. 数字变体")
        show("-n 007", ["-n", "007", "a.txt"], root)
        show("-n ' 3'", ["-n", " 3", "a.txt"], root)
        show("-n 3.5", ["-n", "3.5", "a.txt"], root)
        show("-n ''", ["-n", "", "a.txt"], root)
        show("-c 1e3", ["-c", "1e3", "big.txt"], root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
