"""探针 _t63：摸清 GNU tail 的行为基准。

用 Git Bash 自带的 GNU tail（coreutils 8.32）跑一批参数组合，
把标准输出按字节 repr 出来，好逐条对照实现。

语料一律用 write_bytes 写，拿到的是真 LF 文件；Python 文本模式在
Windows 上会把 "\\n" 翻成 "\\r\\n"，那测的就不是同一件事了。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
AI = HERE.parents[1]
DATA = AI / "数据" / "tail_probe"
DATA.mkdir(parents=True, exist_ok=True)

# 探针输出自己落盘，避免 shell 重定向的路径映射问题。
LOG = AI / "数据" / "tail_probe_out.txt"
_lines: list[str] = []


def emit(text: str = "") -> None:
    _lines.append(text)


_orig_print = print


def print(*args, **kwargs):  # noqa: A001 - 覆盖内置 print 做输出收集
    emit(" ".join(str(a) for a in args))


def flush_log() -> None:
    LOG.write_text("\n".join(_lines) + "\n", encoding="utf-8")

GNU_TAIL = shutil.which("tail")
if GNU_TAIL is None:
    raise SystemExit("找不到 GNU tail")


def run(args, stdin=b"", cwd=None):
    proc = subprocess.run(
        [GNU_TAIL, *args],
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd or DATA),
    )
    return proc.returncode, proc.stdout, proc.stderr


def show(title, args, stdin=b"", cwd=None):
    code, out, err = run(args, stdin=stdin, cwd=cwd)
    print(f"--- {title}")
    print(f"    argv = {args!r} stdin={stdin!r}")
    print(f"    exit = {code}")
    print(f"    out  = {out!r}")
    print(f"    err  = {err!r}")


# ---- 语料 ----
(DATA / "a.txt").write_bytes(b"line1\nline2\nline3\nline4\nline5\n")
(DATA / "b.txt").write_bytes(b"B1\nB2\nB3\n")
(DATA / "noeol.txt").write_bytes(b"x\ny\nno-newline-tail")
(DATA / "empty.txt").write_bytes(b"")
(DATA / "crlf.txt").write_bytes(b"r1\r\nr2\r\nr3\r\n")
(DATA / "nul.txt").write_bytes(b"z1\x00z2\x00z3\x00")
(DATA / "mixed.txt").write_bytes(b"m1\nm2\nm3")

print("=" * 70)
print("A. -n 行数语义")
print("=" * 70)
show("默认 10 行（文件只有 5 行）", ["a.txt"])
show("-n 2", ["-n", "2", "a.txt"])
show("-n 0", ["-n", "0", "a.txt"])
show("-n -2", ["-n", "-2", "a.txt"])
show("-n 99（超过行数）", ["-n", "99", "a.txt"])
show("-n +2（从第 2 行开始）", ["-n", "+2", "a.txt"])
show("-n +0", ["-n", "+0", "a.txt"])
show("-n +1", ["-n", "+1", "a.txt"])
show("-n +99（超过行数）", ["-n", "+99", "a.txt"])
show("-n +2 遇末行无换行", ["-n", "+2", "noeol.txt"])
show("默认 遇末行无换行", ["noeol.txt"])
show("-n 2 遇末行无换行", ["-n", "2", "noeol.txt"])

print()
print("=" * 70)
print("B. -c 字节语义")
print("=" * 70)
show("-c 5", ["-c", "5", "a.txt"])
show("-c 0", ["-c", "0", "a.txt"])
show("-c -5", ["-c", "-5", "a.txt"])
show("-c +5（从第 5 字节开始）", ["-c", "+5", "a.txt"])
show("-c +0", ["-c", "+0", "a.txt"])
show("-c +1", ["-c", "+1", "a.txt"])
show("-c +99（超过字节数）", ["-c", "+99", "a.txt"])
show("-c 5 遇末行无换行", ["-c", "5", "noeol.txt"])

print()
print("=" * 70)
print("C. 乘数后缀")
print("=" * 70)
show("-c 1b", ["-c", "1b", "a.txt"])
show("-c 1k", ["-c", "1k", "a.txt"])
show("-c 1K", ["-c", "1K", "a.txt"])
show("-c 1kB", ["-c", "1kB", "a.txt"])
show("-c 1KiB", ["-c", "1KiB", "a.txt"])
show("-n 1k（-n 支持后缀吗）", ["-n", "1k", "a.txt"])
show("-n 1b", ["-n", "1b", "a.txt"])
show("-c 1Z", ["-c", "1Z", "a.txt"])
show("-c 1Y", ["-c", "1Y", "a.txt"])
show("-c 1kb（非法组合）", ["-c", "1kb", "a.txt"])
show("-c 1B", ["-c", "1B", "a.txt"])
show("-c abc（非法）", ["-c", "abc", "a.txt"])
show("-c ''（非法）", ["-c", "", "a.txt"])
show("-c 1.5（非法）", ["-c", "1.5", "a.txt"])
show("-c +1k", ["-c", "+1k", "a.txt"])

print()
print("=" * 70)
print("D. -n 与 -c 同时给")
print("=" * 70)
show("-n 2 -c 5", ["-n", "2", "-c", "5", "a.txt"])
show("-c 5 -n 2", ["-c", "5", "-n", "2", "a.txt"])
show("-n 2 -n 3", ["-n", "2", "-n", "3", "a.txt"])

print()
print("=" * 70)
print("E. 标题格式")
print("=" * 70)
show("多文件", ["a.txt", "b.txt"])
show("多文件 -q", ["-q", "a.txt", "b.txt"])
show("多文件 -v", ["-v", "a.txt", "b.txt"])
show("单文件", ["a.txt"])
show("单文件 -v", ["-v", "a.txt"])
show("多文件 -q -v", ["-q", "-v", "a.txt", "b.txt"])
show("多文件 -v -q", ["-v", "-q", "a.txt", "b.txt"])
show("三文件（看空行位置）", ["a.txt", "b.txt", "mixed.txt"])
show("空文件参与多文件", ["a.txt", "empty.txt"])
show("标准输入参与多文件", ["a.txt", "-"], stdin=b"from-stdin\n")

print()
print("=" * 70)
print("F. 错误路径")
print("=" * 70)
show("不存在的文件", ["nosuch.txt"])
show("不存在的文件 + 正常文件", ["nosuch.txt", "a.txt"])
show("目录当文件", ["."])
show("目录 + 正常文件", [".", "a.txt"])
show("无操作数读 stdin", [], stdin=b"s1\ns2\n")
show("只有 -", ["-"], stdin=b"s1\ns2\n")
show("两个 -", ["-", "-"], stdin=b"s1\ns2\n")

print()
print("=" * 70)
print("G. -z NUL 分隔")
print("=" * 70)
show("-z 默认行数", ["-z", "nul.txt"])
show("-z -n 2", ["-z", "-n", "2", "nul.txt"])
show("-z -c 5", ["-z", "-c", "5", "nul.txt"])
show("-z 普通换行文件", ["-z", "a.txt"])
show("-z -n +2", ["-z", "-n", "+2", "nul.txt"])

print()
print("=" * 70)
print("H. 其他")
print("=" * 70)
show("CRLF 文件 -n 2", ["-n", "2", "crlf.txt"])
show("CRLF 文件 -c 8", ["-c", "8", "crlf.txt"])
show("空文件", ["empty.txt"])
show("空文件 -n 5", ["-n", "5", "empty.txt"])
show("空文件 -c 5", ["-c", "5", "empty.txt"])
show("紧凑 -2", ["-2", "a.txt"])
show("紧凑 -2 是否等于 -n 2", ["-2", "a.txt"])
show("--lines=2", ["--lines=2", "a.txt"])
show("--bytes=5", ["--bytes=5", "a.txt"])
show("-n +2 读 stdin", ["-n", "+2"], stdin=b"s1\ns2\ns3\n")
show("-- 之后是文件名", ["--", "a.txt"])

print()
print("完成。")
flush_log()
_orig_print(f"日志已写入 {LOG}")
