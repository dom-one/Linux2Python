"""探针第三轮：用裸字节写文件，确认 head 的行/字节语义。

第一轮的 a.txt 等是用 write_text 写的，Python 在 Windows 上把 \\n 翻成了
\\r\\n，所以前两轮读到的其实是 CRLF 文件。这一轮全部用 write_bytes，
拿到真正的 LF 文件重新确认。
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


def run(args: list[str], cwd: Path, stdin: bytes = b"") -> tuple[int, bytes, bytes]:
    proc = subprocess.run(
        [locate_head(), *args],
        cwd=str(cwd),
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.returncode, proc.stdout, proc.stderr


def show(title: str, args: list[str], cwd: Path, stdin: bytes = b"") -> None:
    code, out, err = run(args, cwd, stdin)
    print(f"--- {title}")
    print(f"    argv   : head {' '.join(args)}")
    print(f"    exit   : {code}")
    print(f"    stdout : {out!r}")
    if err:
        print(f"    stderr : {err!r}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    DATA.mkdir(parents=True, exist_ok=True)

    root = Path(tempfile.mkdtemp(prefix="probe_head3_"))
    try:
        # 真·LF 文件
        (root / "lf.txt").write_bytes(b"l1\nl2\nl3\nl4\nl5\n")
        # 末行无换行
        (root / "nonl.txt").write_bytes(b"p1\np2\np3")
        # CRLF 文件
        (root / "crlf.txt").write_bytes(b"c1\r\nc2\r\nc3\r\n")
        # 正好 3 行、末行有换行
        (root / "three.txt").write_bytes(b"t1\nt2\nt3\n")
        # 空文件
        (root / "empty.txt").write_bytes(b"")
        # 只有 1 个换行
        (root / "oneln.txt").write_bytes(b"only\n")
        # 2000 字节，用于区分 1000 与 1024
        (root / "big.bin").write_bytes(b"X" * 2000)
        # NUL 分隔
        (root / "z.bin").write_bytes(b"z1\x00z2\x00z3\x00")
        # 空行
        (root / "blank.txt").write_bytes(b"b1\n\nb3\n")

        print("=" * 70)
        print("R. 真 LF 文件的行语义")
        show("默认 10 行", ["lf.txt"], root)
        show("-n 2", ["-n", "2", "lf.txt"], root)
        show("-n 0", ["-n", "0", "lf.txt"], root)
        show("-n 2 输出是否补 \\r", ["-n", "2", "lf.txt"], root)

        print("=" * 70)
        print("S. -n -N（除末 N 行）在 LF 文件上的精确表现")
        show("-n -2", ["-n", "-2", "lf.txt"], root)
        show("-n -2 末行无换行", ["-n", "-2", "nonl.txt"], root)
        show("-n -1 末行无换行", ["-n", "-1", "nonl.txt"], root)
        show("-n -1 三行有换行", ["-n", "-1", "three.txt"], root)
        show("-n -2 三行有换行", ["-n", "-2", "three.txt"], root)
        show("-n -1 单行", ["-n", "-1", "oneln.txt"], root)
        show("-n -1 空文件", ["-n", "-1", "empty.txt"], root)

        print("=" * 70)
        print("T. -c -N（除末 N 字节）")
        show("-c -2", ["-c", "-2", "lf.txt"], root)
        show("-c -2 末行无换行", ["-c", "-2", "nonl.txt"], root)
        show("-c 3", ["-c", "3", "lf.txt"], root)
        show("-c 3 末行无换行", ["-c", "3", "nonl.txt"], root)

        print("=" * 70)
        print("U. 乘数后缀：区分 1000 与 1024")
        show("-c 1k（应为 1000 字节）", ["-c", "1k", "big.bin"], root)
        show("-c 1K（应为 1024 字节）", ["-c", "1K", "big.bin"], root)
        show("-c 1kb", ["-c", "1kb", "big.bin"], root)
        show("-c 1KiB", ["-c", "1KiB", "big.bin"], root)
        show("-c 1b（应为 512 字节）", ["-c", "1b", "big.bin"], root)
        show("-c 1M", ["-c", "1M", "big.bin"], root)

        print("=" * 70)
        print("V. -z 零分隔")
        show("-z 默认", ["-z", "z.bin"], root)
        show("-z -n 2", ["-z", "-n", "2", "z.bin"], root)
        show("-z -c 3", ["-z", "-c", "3", "z.bin"], root)
        show("不加 -z 读 z.bin", ["z.bin"], root)

        print("=" * 70)
        print("W. 空行与 CRLF")
        show("含空行", ["blank.txt"], root)
        show("CRLF 文件 -n 2", ["-n", "2", "crlf.txt"], root)
        show("CRLF 文件 -c 5", ["-c", "5", "crlf.txt"], root)

        print("=" * 70)
        print("X. 头部细节")
        show("路径带 ./ 前缀", ["./lf.txt"], root)
        show("两文件用 ./ 路径", ["./lf.txt", "three.txt"], root)
        show("stdin 带 -v", ["-v"], root, stdin=b"s1\ns2\n")

        print("=" * 70)
        print("Y. 大数与特殊值")
        show("-n 999999999", ["-n", "999999999", "lf.txt"], root)
        show("-c 999999999", ["-c", "999999999", "lf.txt"], root)
        show("-n +2147483648", ["-n", "+2147483648", "lf.txt"], root)
        show("-n -0", ["-n", "-0", "lf.txt"], root)
        show("-n -1 空文件", ["-n", "-1", "empty.txt"], root)
        show("-c -1 空文件", ["-c", "-1", "empty.txt"], root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
