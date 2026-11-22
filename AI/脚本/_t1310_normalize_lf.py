#!/usr/bin/env python
"""把本轮碰过的文件统一回 LF 换行（仓库约定是 LF）。

用法：
    python AI/脚本/_t1310_normalize_lf.py

背景：Python 的 `Path.write_text` 在 Windows 上默认 newline=None，
写的时候把 '\\n' 翻译成 os.linesep（CRLF），于是本轮用脚本改过的
AI/教程进度.md 整个文件从 LF 变成了 CRLF，git 里显示成「每一行都改了」。
本脚本把这些文件统一回 LF。

只处理本轮动过的文件，不碰仓库其他文件。
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

TARGETS = [
    ROOT / "AI" / "教程进度.md",
    ROOT / "teach" / "00-项目总览与阅读顺序.md",
    ROOT / "teach" / "28-w2l-commands-awk_lite.py-字段投影与解析边界.md",
] + sorted((ROOT / "AI" / "脚本").glob("_t130*.py"))


def count_endings(data: bytes) -> tuple[int, int]:
    crlf = data.count(b"\r\n")
    lone_lf = data.count(b"\n") - crlf
    lone_cr = data.count(b"\r") - crlf
    return crlf, lone_lf + lone_cr


def main() -> int:
    changed = []
    for path in TARGETS:
        if not path.exists():
            print(f"跳过（不存在）：{path}")
            continue
        raw = path.read_bytes()
        crlf, other = count_endings(raw)
        if crlf == 0:
            print(f"OK  已是 LF：{path.relative_to(ROOT)}")
            continue
        fixed = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        path.write_bytes(fixed)
        changed.append(path)
        print(
            f"改  {path.relative_to(ROOT)}：CRLF {crlf} 处 -> LF，"
            f"其他换行 {other} 处，{len(raw)} -> {len(fixed)} 字节"
        )

    print()
    print(f"共改 {len(changed)} 个文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
