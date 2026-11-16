"""探针：把 w2l 的 tail 与 Git Bash 的 GNU tail 逐条对拍。

用法:
    python AI/脚本/_t600_probe_tail.py

做法:
- 在临时目录造一批夹具（普通文件、无换行结尾、空行、CRLF、NUL 分隔、GBK、二进制）
- 每条用例同时跑「本项目 tail」与「GNU tail」，把两边输出按 repr 打印
- 结果写进 AI/数据/tail_probe.json，供写教程时直接取用

注意：夹具的 mtime 不参与比较，只比输出内容。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASH = r"E:\software\Git\Git\bin\bash.exe"
GNU_TAIL = r"E:\software\Git\Git\usr\bin\tail.exe"


def make_fixtures(base: str) -> dict:
    files = {
        "a.txt": b"l1\nl2\nl3\nl4\nl5\n",
        "b.txt": b"x\n",
        "nonl.txt": b"p1\np2\np3",
        "empty.txt": b"",
        "blank.txt": b"b1\n\nb3\n",
        "crlf.txt": b"c1\r\nc2\r\nc3\r\n",
        "zeros.bin": b"z1\x00z2\x00z3\x00",
        "bin.dat": bytes(range(256)),
        "many.txt": b"".join(b"n%03d\n" % i for i in range(600)),
        "big.txt": b"X" * 2000,
    }
    for name, data in files.items():
        with open(os.path.join(base, name), "wb") as fh:
            fh.write(data)
    # GBK 中文夹具
    with open(os.path.join(base, "gbk.txt"), "wb") as fh:
        fh.write("日志第一行\n日志第二行\n".encode("gb18030"))
    os.mkdir(os.path.join(base, "sub"))
    return files


def run_project(args: list[str], cwd: str, stdin_bytes: bytes = b"") -> tuple[int, bytes]:
    proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, "main.py"), "tail"] + args,
        cwd=cwd,
        input=stdin_bytes,
        capture_output=True,
    )
    return proc.returncode, proc.stdout + b"|STDERR|" + proc.stderr


def run_gnu(args: list[str], cwd: str, stdin_bytes: bytes = b"") -> tuple[int, bytes]:
    proc = subprocess.run(
        [GNU_TAIL] + args,
        cwd=cwd,
        input=stdin_bytes,
        capture_output=True,
    )
    return proc.returncode, proc.stdout + b"|STDERR|" + proc.stderr


CASES = [
    ["a.txt"],
    ["-n", "2", "a.txt"],
    ["-n", "-2", "a.txt"],
    ["-n", "+2", "a.txt"],
    ["-n", "0", "a.txt"],
    ["-n", "+0", "a.txt"],
    ["-n", "+99", "a.txt"],
    ["-n", "+2", "nonl.txt"],
    ["-c", "5", "a.txt"],
    ["-c", "+5", "a.txt"],
    ["-c", "0", "a.txt"],
    ["-c", "+0", "a.txt"],
    ["-c", "+2", "nonl.txt"],
    ["-c", "999", "a.txt"],
    ["-c", "7", "-n", "2", "a.txt"],
    ["-n", "2", "-c", "7", "a.txt"],
    ["-2", "a.txt"],
    ["--lines=2", "a.txt"],
    ["--bytes=5", "a.txt"],
    ["--lines=+2", "a.txt"],
    ["-c", "1b", "big.txt"],
    ["-c", "1k", "big.txt"],
    ["-c", "1kB", "big.txt"],
    ["-c", "1KiB", "big.txt"],
    ["-n", "1b", "many.txt"],
    ["a.txt", "b.txt"],
    ["-q", "a.txt", "b.txt"],
    ["-v", "a.txt"],
    ["-q", "-v", "a.txt", "b.txt"],
    ["-v", "-q", "a.txt", "b.txt"],
    ["-n", "2", "blank.txt"],
    ["-n", "2", "crlf.txt"],
    ["-n", "2", "empty.txt"],
    ["nonl.txt"],
    ["zeros.bin"],
    ["-z", "-n", "2", "zeros.bin"],
    ["-z", "-n", "2", "a.txt"],
    ["nope.txt"],
    ["-v", "a.txt", "nope.txt"],
    ["a.txt", "sub", "b.txt"],
    ["-v", "sub"],
    ["gbk.txt"],
    ["-n", "1", "gbk.txt"],
    ["bin.dat"],
    ["a.txt", "-n", "2"],
]

STDIN_CASES = [
    ([], b"from stdin\n"),
    (["-"], b"from stdin\n"),
    (["-n", "2"], b"s1\ns2\ns3\ns4\n"),
    (["-n", "+2"], b"s1\ns2\ns3\ns4\n"),
    (["-n", "+2"], b"s1\ns2\ns3"),
    (["-c", "5"], b"abcdefghij"),
    (["-c", "+5"], b"abcdefghij"),
    (["-n", "0"], b"s1\ns2\n"),
    (["-n", "+0"], b"s1\ns2\n"),
]


def main() -> int:
    base = tempfile.mkdtemp(prefix="tailprobe")
    try:
        make_fixtures(base)
        results = []
        for args in CASES:
            rc_p, out_p = run_project(args, base)
            rc_g, out_g = run_gnu(args, base)
            results.append(
                {
                    "kind": "file",
                    "args": args,
                    "project": {"rc": rc_p, "out": out_p.decode("utf-8", "replace")},
                    "gnu": {"rc": rc_g, "out": out_g.decode("utf-8", "replace")},
                    "same": out_p == out_g,
                }
            )
        for args, data in STDIN_CASES:
            rc_p, out_p = run_project(args, base, data)
            rc_g, out_g = run_gnu(args, base, data)
            results.append(
                {
                    "kind": "stdin",
                    "args": args,
                    "stdin": data.decode("utf-8", "replace"),
                    "project": {"rc": rc_p, "out": out_p.decode("utf-8", "replace")},
                    "gnu": {"rc": rc_g, "out": out_g.decode("utf-8", "replace")},
                    "same": out_p == out_g,
                }
            )
        outdir = os.path.join(ROOT, "AI", "数据")
        os.makedirs(outdir, exist_ok=True)
        outpath = os.path.join(outdir, "tail_probe.json")
        with open(outpath, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=2)

        diff = 0
        for item in results:
            mark = "同" if item["same"] else "差"
            if not item["same"]:
                diff += 1
            print("[%s] %s" % (mark, " ".join(item["args"]) or "(无参数)"))
            if not item["same"]:
                print("   本项目 rc=%s %r" % (item["project"]["rc"], item["project"]["out"]))
                print("   GNU   rc=%s %r" % (item["gnu"]["rc"], item["gnu"]["out"]))
        print("---")
        print("用例 %d，输出不同 %d" % (len(results), diff))
        print("结果文件：%s" % outpath)
        return 0
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
