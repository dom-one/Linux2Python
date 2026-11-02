"""差分对照：把本实现的 head 与 Git Bash 的 GNU head 逐字节比。

比法：

- stdout 逐字节比
- stderr 只比「有没有」（措辞是本项目自定的，不与 GNU 对齐）
- 退出码归一化：GNU 出错返回 1，本项目约定返回 2，都算「出错」

语料只用 ASCII / UTF-8 / 二进制三种，因为本实现会把文本解码成 UTF-8
再输出，GBK 语料与 GNU 的字节透传本来就不一样，那部分另测。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
ROOT = AI_DIR.parent

GNU_HEAD = r"C:\Program Files\Git\usr\bin\head.exe"
PYTHON = sys.executable


def locate_head() -> str:
    candidate = shutil.which("head")
    if candidate and "System32" not in candidate:
        return candidate
    return GNU_HEAD


def run_gnu(args: list[str], cwd: Path, stdin: bytes) -> tuple[int, bytes, bool]:
    proc = subprocess.run(
        [locate_head(), *args],
        cwd=str(cwd),
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.returncode, proc.stdout, bool(proc.stderr.strip())


def run_ours(args: list[str], cwd: Path, stdin: bytes) -> tuple[int, bytes, bool]:
    proc = subprocess.run(
        [PYTHON, str(ROOT / "main.py"), "head", *args],
        cwd=str(cwd),
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.returncode, proc.stdout, bool(proc.stderr.strip())


def build_corpus(root: Path) -> None:
    (root / "a.txt").write_bytes(b"l1\nl2\nl3\nl4\nl5\n")
    (root / "b.txt").write_bytes(b"x\n")
    (root / "c.txt").write_bytes(b"only\n")
    (root / "nonl.txt").write_bytes(b"p1\np2\np3")
    (root / "empty.txt").write_bytes(b"")
    (root / "blank.txt").write_bytes(b"b1\n\nb3\n")
    (root / "crlf.txt").write_bytes(b"c1\r\nc2\r\nc3\r\n")
    (root / "lonecr.txt").write_bytes(b"r1\rXX\n")
    (root / "z.bin").write_bytes(b"z1\x00z2\x00z3\x00")
    (root / "bin.dat").write_bytes(bytes(range(256)))
    (root / "utf8.txt").write_bytes("中文第一行\n第二行\n".encode("utf-8"))
    (root / "long.txt").write_bytes(b"".join(b"line%02d\n" % i for i in range(30)))
    (root / "sub").mkdir()
    (root / "sub" / "inner.txt").write_bytes(b"inner\n")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(tempfile.mkdtemp(prefix="diff_head_"))
    passed = 0
    failed = 0
    mismatches: list[str] = []

    try:
        build_corpus(root)

        cases: list[tuple[list[str], bytes]] = []
        files = ["a.txt", "b.txt", "c.txt", "nonl.txt", "empty.txt", "blank.txt",
                 "crlf.txt", "lonecr.txt", "z.bin", "bin.dat", "utf8.txt", "long.txt"]

        # 基本行数
        for f in files:
            cases.append(([f], b""))
            cases.append((["-n", "2", f], b""))
            cases.append((["-n", "0", f], b""))
            cases.append((["-n", "99", f], b""))
            cases.append((["-c", "5", f], b""))
            cases.append((["-c", "0", f], b""))
            cases.append((["-n", "3", "-c", "7", f], b""))
            cases.append((["-c", "7", "-n", "3", f], b""))

        # 正负号
        for f in ["a.txt", "nonl.txt", "c.txt", "empty.txt", "long.txt"]:
            for n in ["+0", "+1", "+3", "-0", "-1", "-2", "-3", "-99"]:
                cases.append((["-n", n, f], b""))
                cases.append((["-c", n, f], b""))

        # 多文件与标题
        multi = [
            ["a.txt", "b.txt"],
            ["a.txt", "b.txt", "c.txt"],
            ["-q", "a.txt", "b.txt"],
            ["-v", "a.txt"],
            ["-v", "a.txt", "b.txt"],
            ["-q", "a.txt"],
            ["-q", "-v", "a.txt", "b.txt"],
            ["-v", "-q", "a.txt", "b.txt"],
            ["a.txt", "nonl.txt", "b.txt"],
            ["a.txt", "missing.txt", "b.txt"],
            ["-v", "missing.txt"],
            ["missing.txt"],
            ["m1.txt", "m2.txt"],
            ["a.txt", "sub", "b.txt"],
            ["sub"],
            ["./a.txt", "b.txt"],
        ]
        for args in multi:
            cases.append((args, b""))

        # 标准输入
        for args in [[], ["-"], ["-", "b.txt"], ["b.txt", "-", "b.txt"],
                     ["-", "-"], ["-n", "2"], ["-c", "3"], ["-v"], ["-q", "-", "b.txt"]]:
            cases.append((args, b"s1\ns2\ns3\n"))

        # -z
        for args in [["-z", "z.bin"], ["-z", "-n", "2", "z.bin"], ["-z", "-c", "3", "z.bin"],
                     ["z.bin"], ["-z", "a.txt"], ["-z", "-n", "1", "z.bin", "a.txt"]]:
            cases.append((args, b""))

        # 紧凑写法与长选项
        for args in [["-2", "a.txt"], ["-0", "a.txt"], ["-n2", "a.txt"], ["-n-2", "a.txt"],
                     ["-c-2", "a.txt"], ["--lines=3", "a.txt"], ["--bytes=5", "a.txt"],
                     ["--lines=-2", "a.txt"], ["--bytes=-2", "a.txt"], ["--quiet", "a.txt", "b.txt"],
                     ["--silent", "a.txt", "b.txt"], ["--verbose", "a.txt"],
                     ["--zero-terminated", "z.bin"], ["--", "-n"], ["-n", "-2", "a.txt"],
                     ["-c", "-2", "a.txt"], ["-n", "+3", "a.txt"]]:
            cases.append((args, b""))

        # 乘数后缀
        for spec in ["1b", "1k", "1K", "1kB", "1KB", "1m", "1M", "1MB", "1KiB", "1MiB"]:
            cases.append((["-c", spec, "long.txt"], b""))
            cases.append((["-n", spec, "long.txt"], b""))

        for args, stdin in cases:
            g_code, g_out, g_err = run_gnu(args, root, stdin)
            o_code, o_out, o_err = run_ours(args, root, stdin)

            g_fail = g_code != 0
            o_fail = o_code != 0
            problems = []
            if g_out != o_out:
                problems.append(f"stdout 不同\n      GNU : {g_out!r}\n      本实现: {o_out!r}")
            if g_fail != o_fail:
                problems.append(f"失败与否不同 GNU={g_code} 本实现={o_code}")
            if g_err != o_err:
                problems.append(f"stderr 有无不同 GNU={g_err} 本实现={o_err}")

            if problems:
                failed += 1
                mismatches.append(f"  head {' '.join(args) or '(无)'}  stdin={stdin!r}\n    " + "\n    ".join(problems))
            else:
                passed += 1

        print("=" * 70)
        print(f"用例总数 {passed + failed}：一致 {passed}，不一致 {failed}")
        if mismatches:
            print("=" * 70)
            for item in mismatches:
                print(item)
        return 1 if failed else 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
