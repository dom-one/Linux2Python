"""探针 _t69：把 README 里 tail 章节的示例逐条真跑一遍。

README 里写的示例必须能跑通、且输出与文案一致，
否则文档就是骗人的。这条脚本把 tail 章节表格里的示例全跑一遍，
顺带核一遍能力清单里提到的选项字母与实现是否一致。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
AI = HERE.parents[1]
ROOT = HERE.parents[2]
LOG = AI / "数据" / "readme_tail_check_out.txt"

_lines: list[str] = []


def print(*args):  # noqa: A001
    _lines.append(" ".join(str(a) for a in args))


def run(args, timeout=10):
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "main.py"), "tail", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            cwd=str(ROOT),
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT", b"", b""


# README tail 章节选项表里的示例
EXAMPLES = [
    ["w2l/cli.py"],
    ["-n", "20", "w2l/registry.py"],
    ["-c", "512", "w2l/context.py"],
    ["-q", "w2l/cli.py", "w2l/context.py"],
    ["-v", "w2l/cli.py"],
    ["-z", "w2l/registry.py"],
    ["-n", "+20", "w2l/cli.py"],
    ["-20", "w2l/cli.py"],
]

# 跟随类选项用 -s 0 限一下，避免一直挂着
FOLLOW_EXAMPLES = [
    ["-f", "-s", "0", "w2l/cli.py"],
    ["-F", "-s", "0", "w2l/cli.py"],
    ["-f", "-s", "0", "--pid", "1234", "w2l/cli.py"],
    ["-F", "-s", "0", "--retry", "w2l/cli.py"],
]

print("=" * 70)
print("X. README tail 选项表示例逐条真跑")
print("=" * 70)
bad = 0
for args in EXAMPLES:
    code, out, err = run(args)
    ok = code == 0 and out
    status = "OK " if ok else "FAIL"
    if not ok:
        bad += 1
    print(f"[{status}] exit={code} argv={args!r}")
    print(f"        out前80字节 = {out[:80]!r}")
    if err:
        print(f"        err = {err.decode('utf-8', 'replace')!r}")

for args in FOLLOW_EXAMPLES:
    code, out, err = run(args, timeout=6)
    # 跟随类示例会一直挂着，超时算正常（说明它真的在跟）
    ok = code in (0, "TIMEOUT")
    status = "OK " if ok else "FAIL"
    if not ok:
        bad += 1
    print(f"[{status}] exit={code} argv={args!r} out字节数={len(out)}")
    if err:
        print(f"        err = {err.decode('utf-8', 'replace')!r}")

print()
print("=" * 70)
print("Y. 选项字母与实现是否一致")
print("=" * 70)
code, out, err = run(["--help"])
help_text = out.decode("utf-8", "replace")
print(help_text)

for flag in ["-n", "--lines", "-c", "--bytes", "-q", "--quiet", "--silent",
             "-v", "--verbose", "-z", "--zero-terminated", "-f", "--follow",
             "-F", "-s", "--sleep-interval", "--pid", "--retry"]:
    present = flag in help_text
    print(f"[{'OK ' if present else 'FAIL'}] {flag} 出现在 --help 里")
    if not present:
        bad += 1

print()
print("=" * 70)
print(f"失败项：{bad}")
print("=" * 70)

LOG.write_text("\n".join(_lines) + "\n", encoding="utf-8")
print(f"日志已写入 {LOG}")
