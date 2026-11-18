"""把 tree 教程要引用的每条命令真跑一遍，把输出录到 AI/数据/tree_capture.txt。

为什么要有这个脚本：教程里的预期输出必须逐字来自实跑，不能凭印象写。
本项目没有 GNU tree 可做差分对照（见 tests/test_tree.py 的说明），
所以唯一的基线就是本实现自己的实跑输出 + 源码里的规则。

用法:
    python AI/脚本/_t801_capture_tree_tut.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = Path(ROOT) / "AI" / "数据" / "tree_capture.txt"

DEMO = "AI/数据/tree_demo"

# (小标题, 参数列表, 工作目录)
CASES: list[tuple[str, list[str], str]] = [
    ("帮助", ["tree", "--help"], ROOT),
    ("默认树", ["tree", DEMO], ROOT),
    ("隐藏文件", ["tree", "-a", DEMO], ROOT),
    ("只列目录", ["tree", "-d", DEMO], ROOT),
    ("完整路径", ["tree", "-f", DEMO], ROOT),
    ("类型标记", ["tree", "-F", DEMO], ROOT),
    ("不画缩进线", ["tree", "-i", DEMO], ROOT),
    ("限制一层", ["tree", "-L", "1", DEMO], ROOT),
    ("限制两层", ["tree", "-L", "2", DEMO], ROOT),
    ("目录提前", ["tree", "--dirsfirst", DEMO], ROOT),
    ("反向", ["tree", "-r", DEMO], ROOT),
    ("按时间排序", ["tree", "-t", DEMO], ROOT),
    ("不排序", ["tree", "-U", DEMO], ROOT),
    ("大小列", ["tree", "-s", DEMO], ROOT),
    ("人类可读大小", ["tree", "-h", DEMO], ROOT),
    ("权限列", ["tree", "-p", DEMO], ROOT),
    ("修改时间", ["tree", "-D", DEMO], ROOT),
    ("忽略 txt", ["tree", "-I", "*.txt", DEMO], ROOT),
    ("忽略 sub 目录", ["tree", "-I", "sub", DEMO], ROOT),
    ("只留 txt", ["tree", "-P", "*.txt", DEMO], ROOT),
    ("只留 txt 且忽略大小写", ["tree", "-P", "*.TXT", "--ignore-case", DEMO], ROOT),
    ("ASCII 画线", ["tree", "--charset=ascii", DEMO], ROOT),
    ("不打统计行", ["tree", "--noreport", DEMO], ROOT),
    ("空目录", ["tree", DEMO + "/empty_dir"], ROOT),
    ("多个操作数", ["tree", DEMO + "/empty_dir", DEMO + "/sub"], ROOT),
    ("目录不存在", ["tree", "nope"], ROOT),
    ("操作数是文件", ["tree", DEMO + "/a.txt"], ROOT),
    ("层数为 0", ["tree", "-L", "0", DEMO], ROOT),
    ("字符集不认识", ["tree", "--charset=gbk", DEMO], ROOT),
    ("真实项目目录", ["tree", "w2l"], ROOT),
    ("真实项目目录带权限", ["tree", "-p", "w2l/commands"], ROOT),
]


def _run(argv: list[str], cwd: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, "main.py", *argv],
        cwd=cwd,
        capture_output=True,
        timeout=60,
    )
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", errors="replace"),
        proc.stderr.decode("utf-8", errors="replace"),
    )


def _mark(title: str) -> str:
    return f"\n{'=' * 78}\n== {title}\n{'=' * 78}"


def main() -> None:
    chunks: list[str] = []
    for title, argv, cwd in CASES:
        code, out, err = _run(argv, cwd)
        chunks.append(_mark(title))
        chunks.append(f"$ python main.py {' '.join(argv)}   (cwd={cwd})")
        chunks.append(f"退出码: {code}")
        chunks.append("--- stdout ---")
        chunks.append(out if out else "(空)")
        chunks.append("--- stderr ---")
        chunks.append(err if err else "(空)")
        # 非 ASCII 字符逐行给 repr，看得见 NBSP 这类不可见字符
        chunks.append("--- stdout 逐行 repr（只列含不可见字符的行）---")
        shown = False
        for line in out.splitlines():
            if any(ord(ch) > 127 for ch in line):
                chunks.append("  " + repr(line))
                shown = True
        if not shown:
            chunks.append("  (无)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(chunks) + "\n", encoding="utf-8")
    print(f"已写入 {OUT}（{OUT.stat().st_size} 字节，{len(CASES)} 个场景）")


if __name__ == "__main__":
    main()
