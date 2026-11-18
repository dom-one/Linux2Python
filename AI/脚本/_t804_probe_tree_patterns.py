"""探针四：-P 与 -I 的通配符语义细节。

要钉死的四条：

1. -P 命中的是「目录」时，它下面的内容全部列出（pattern_active 机制）。
2. -P 命中的是「根目录」时，整棵树全部列出。
3. -P 只筛文件，目录照旧列出。
4. 通配符的候选集：名字、完整路径、路径的任意后缀；
   '*' 不跨 '/'、'**' 跨 '/'、'?' 匹配一个字符、'|' 分隔候选。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DEMO = Path(ROOT) / "AI" / "数据" / "tree_demo"


def _run(argv: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, "main.py", *argv],
        cwd=ROOT,
        capture_output=True,
        timeout=60,
    )
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", errors="replace"),
        proc.stderr.decode("utf-8", errors="replace"),
    )


def show(title: str, argv: list[str]) -> None:
    code, out, err = _run(argv)
    print(f"\n--- {title} ---")
    print(f"$ python main.py {' '.join(argv)}")
    print(f"退出码 {code}")
    print(out.rstrip())
    if err.strip():
        print(f"stderr: {err.strip()}")


def main() -> None:
    demo = "AI/数据/tree_demo"

    show("1. -P 命中目录（sub）→ 它下面全部列出", ["tree", "-P", "sub", demo])
    show("2. -P 命中根目录名（tree_demo）→ 整棵树全部列出", ["tree", "-P", "tree_demo", demo])
    show("3. -P 只筛文件，目录照旧列出", ["tree", "-P", "*.md", demo])
    show("4. -I 用路径后缀匹配", ["tree", "-I", "sub/deep.txt", demo])
    show("5. -I 用 '**' 跨斜杠", ["tree", "-I", "sub/**", demo])
    show("6. -P 用 '**' 跨斜杠", ["tree", "-P", "**/deep.txt", demo])
    show("7. '|' 分隔多个候选", ["tree", "-I", "*.txt|*.md", demo])
    show("8. '?' 匹配一个字符", ["tree", "-P", "?.txt", demo])
    show("9. 字符类与取反", ["tree", "-P", "[!a]*.txt", demo])
    show("10. 目录名带斜杠表示只匹配目录", ["tree", "-I", "sub/", demo])
    show("11. 不给操作数（列当前目录）", ["tree", "--noreport"])
    show("12. -x 跨卷", ["tree", "-x", demo])


if __name__ == "__main__":
    main()
