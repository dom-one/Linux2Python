"""差分对照：把本实现的 cat 与 Git Bash 的 GNU cat 逐组比对。

ASCII 与 CRLF 语料要求字节完全一致；含高位字节的语料只比对结构
（本实现按文本解码后输出 UTF-8，GNU cat 是字节透传，字节本就不同）。

只读：仅在 AI/数据/ 下建临时目录，不碰仓库源码。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "AI" / "数据"
GNU_CAT = shutil.which("cat") or r"E:\software\Git\Git\usr\bin\cat.exe"

OPTION_SETS = [
    [],
    ["-n"],
    ["-b"],
    ["-E"],
    ["-e"],
    ["-T"],
    ["-s"],
    ["-v"],
    ["-A"],
    ["-n", "-s"],
    ["-b", "-s"],
    ["-n", "-E"],
    ["-n", "-T"],
    ["-b", "-E"],
    ["-A", "-n"],
    ["-A", "-s"],
    ["-v", "-T"],
]


def gnu(argv: list[str], cwd: Path) -> tuple[int, bytes]:
    proc = subprocess.run([GNU_CAT, *argv], cwd=str(cwd), capture_output=True)
    return proc.returncode, proc.stdout


def ours(argv: list[str], cwd: Path) -> tuple[int, bytes]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "cat", *argv],
        cwd=str(cwd),
        capture_output=True,
    )
    return proc.returncode, proc.stdout


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="_t37_diff_", dir=str(DATA)))

    corpus = {
        "ascii": b"alpha\nbeta\ngamma\n",
        "no_eol": b"one\ntwo",
        "empty": b"",
        "blank_lines": b"one\n\n\n\ntwo\n",
        "crlf": b"l1\r\nl2\r\n",
        "crlf_blank": b"a\r\n\r\n\r\nb\r\n",
        "tabs": b"col1\tcol2\ncol3\tcol4\n",
        "spaces_only": b"a\n \nb\n",
        "trailing_ws": b"a\n   \nb\n",
        "single_line": b"solo\n",
        "many": b"".join(b"l%d\n" % i for i in range(1, 13)),
        "ctrl": b"bell\x07 del\x7f esc\x1b\n",
        "high": b"\x80\x81\xfe\xff\n",
        "all_bytes": bytes(range(256)),
        "nul_mid": b"abc\x00def\n",
    }
    for name, data in corpus.items():
        (tmp / name).write_bytes(data)

    failures = 0
    checks = 0
    for name in corpus:
        for opts in OPTION_SETS:
            checks += 1
            gcode, gout = gnu([*opts, name], tmp)
            ocode, oout = ours([*opts, name], tmp)
            if (gcode, gout) != (ocode, oout):
                failures += 1
                print("MISMATCH file=%s opts=%r" % (name, opts))
                print("  gnu  code=%d out=%r" % (gcode, gout))
                print("  ours code=%d out=%r" % (ocode, oout))
                print("  stderr=%r" % (subprocess.run(
                    [sys.executable, str(ROOT / "main.py"), "cat", *opts, name],
                    cwd=str(tmp), capture_output=True).stderr))

    print()

    # 多文件拼接：编号与压紧状态必须跨文件延续
    (tmp / "m1.txt").write_bytes(b"A1\nA2\n")
    (tmp / "m2.txt").write_bytes(b"B1\nB2\n")
    (tmp / "e1.txt").write_bytes(b"x\n\n")
    (tmp / "e2.txt").write_bytes(b"\ny\n")
    multi_cases = [
        (["m1.txt", "m2.txt"], []),
        (["m1.txt", "m2.txt"], ["-n"]),
        (["m1.txt", "m2.txt"], ["-b"]),
        (["e1.txt", "e2.txt"], ["-s"]),
        (["e1.txt", "e2.txt"], ["-n"]),
    ]
    for files, opts in multi_cases:
        checks += 1
        gcode, gout = gnu([*opts, *files], tmp)
        ocode, oout = ours([*opts, *files], tmp)
        if (gcode, gout) != (ocode, oout):
            failures += 1
            print("MISMATCH multi files=%r opts=%r" % (files, opts))
            print("  gnu  code=%d out=%r" % (gcode, gout))
            print("  ours code=%d out=%r" % (ocode, oout))

    print()

    # 标准输入
    stdin_cases = [
        ([], b"from stdin\n"),
        (["-"], b"from stdin\n"),
        (["-n"], b"one\ntwo\n"),
        (["-s"], b"a\n\n\nb\n"),
        (["-b"], b"a\n\nb\n"),
    ]
    for opts, payload in stdin_cases:
        checks += 1
        g = subprocess.run([GNU_CAT, *opts], input=payload, capture_output=True)
        o = subprocess.run(
            [sys.executable, str(ROOT / "main.py"), "cat", *opts],
            input=payload, capture_output=True,
        )
        if (g.returncode, g.stdout) != (o.returncode, o.stdout):
            failures += 1
            print("MISMATCH stdin opts=%r" % (opts,))
            print("  gnu  code=%d out=%r" % (g.returncode, g.stdout))
            print("  ours code=%d out=%r" % (o.returncode, o.stdout))

    print()

    # 错误路径：文件不存在
    checks += 1
    g = subprocess.run([GNU_CAT, "nope.txt"], cwd=str(tmp), capture_output=True)
    o = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "cat", "nope.txt"],
        cwd=str(tmp), capture_output=True,
    )
    print("missing file: gnu code=%d err=%r" % (g.returncode, g.stderr[:120]))
    print("missing file: ours code=%d err=%r" % (o.returncode, o.stderr[:120]))
    if g.stdout != o.stdout:
        failures += 1
        print("MISMATCH missing file stdout: gnu=%r ours=%r" % (g.stdout, o.stdout))

    print()

    # 含高位字节的语料：本实现输出 UTF-8，GNU cat 字节透传
    hi = tmp / "hi.txt"
    hi.write_bytes("中文内容\n第二行\n".encode("utf-8"))
    print("utf8 file: gnu  out=%r" % (gnu(["hi.txt"], tmp)[1],))
    print("utf8 file: ours out=%r" % (ours(["hi.txt"], tmp)[1],))
    print()

    print("checks=%d failures=%d" % (checks, failures))

    for path in sorted(tmp.rglob("*"), reverse=True):
        if path.is_dir():
            os.rmdir(path)
        else:
            path.unlink()
    os.rmdir(tmp)
    print("temp dir cleaned")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
