#!/usr/bin/env python
"""把被改写脚本翻成 CRLF 的文件改回 LF（仓库约定：源码与文档一律 LF）。

起因：用 Python 按行删函数时，open(..., "w") 在 Windows 上把 "\\n" 写成了
"\\r\\n"，5 个指令文件整文件翻转，git diff 变成全文件重写。

做法：按字节把 CRLF 还原成 LF，再核对每个文件的 CRLF 计数为 0。
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

TARGETS = [
    "w2l/commands/awk_lite.py",
    "w2l/commands/head.py",
    "w2l/commands/sed.py",
    "w2l/commands/tail.py",
    "w2l/commands/wc.py",
]


def main() -> int:
    for name in TARGETS:
        path = ROOT / name
        data = path.read_bytes()
        before = data.count(b"\r\n")
        fixed = data.replace(b"\r\n", b"\n")
        path.write_bytes(fixed)
        after = fixed.count(b"\r\n")
        print(f"{name}: CRLF {before} -> {after}")
        if after:
            raise SystemExit(f"{name} 仍有 CRLF，检查一下")
    print("全部还原为 LF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
