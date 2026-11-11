"""采集 teach/00 索引页要用的真实数字。

索引页里的目录树写着每个文件的行数、每个测试文件的用例数，
那些数字是写死的, 源码一变就过期。这一轮把真实值全部采一遍,
用来更新索引页。

用法:
    python AI/脚本/_t331_collect_teach00_facts.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "teach00_facts.txt")

TEST_ID = re.compile(r"^tests[\\/][^\s:]+:\s*(\d+)\s*$")


def count_tests(path: str) -> int:
    """数一个测试文件里有多少个用例(pytest --collect-only)。

    pytest 8 的 -q --collect-only 直接打印 "tests/xxx.py: 23" 这样的计数,
    不是用例 id 列表, 所以按这个格式解析。
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", path],
        cwd=ROOT, capture_output=True,
    )
    text = proc.stdout.decode("utf-8", errors="replace")
    for line in text.splitlines():
        match = TEST_ID.match(line.strip())
        if match:
            return int(match.group(1))
    return -1


def main() -> None:
    lines: list[str] = []

    lines.append("### 源码行数")
    srcs = []
    for name in sorted(os.listdir(os.path.join(ROOT, "w2l", "commands"))):
        if name.endswith(".py"):
            srcs.append(os.path.join("w2l", "commands", name))
    for name in sorted(os.listdir(os.path.join(ROOT, "w2l"))):
        if name.endswith(".py"):
            srcs.append(os.path.join("w2l", name))
    srcs.append("main.py")
    for rel in srcs:
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "main.py"), "wc", "-l", rel],
            cwd=ROOT, capture_output=True,
        )
        lines.append("  %s -> %s" % (rel, proc.stdout.decode("utf-8").strip()))

    lines.append("")
    lines.append("### 测试用例数")
    for name in sorted(os.listdir(os.path.join(ROOT, "tests"))):
        if name.startswith("test_") and name.endswith(".py"):
            rel = os.path.join("tests", name)
            lines.append("  %s -> %d" % (rel, count_tests(rel)))

    lines.append("")
    lines.append("### 全量测试")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest"], cwd=ROOT, capture_output=True,
    )
    lines.append("  " + proc.stdout.decode("utf-8", errors="replace").strip().splitlines()[-1])

    lines.append("")
    lines.append("### python main.py 的真实输出")
    proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, "main.py")], cwd=ROOT, capture_output=True,
    )
    lines.append("  退出码 %d" % proc.returncode)
    for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
        lines.append("  |%s|" % line)

    lines.append("")
    lines.append("### teach/ 目录现有篇目")
    for name in sorted(os.listdir(os.path.join(ROOT, "teach"))):
        if name.endswith(".md"):
            lines.append("  " + name)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("写入 %s" % OUT)
    print()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
