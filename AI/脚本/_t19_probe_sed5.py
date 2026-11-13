#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探清 GNU sed 的空匹配替换规则与 a/i/c 文本里的转义处理。"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "sed_probe5.txt"


def find_sed() -> str:
    return shutil.which("sed") or r"C:\Program Files\Git\usr\bin\sed.exe"


def main() -> int:
    sed = find_sed()
    lines: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="sedprobe5_"))

    def case(name: str, script: str, data: bytes = b"alpha\n") -> None:
        path = tmp / "s.sed"
        path.write_bytes(script.encode("utf-8"))
        proc = subprocess.run(
            [sed, "-f", "s.sed"],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(tmp),
        )
        lines.append(f"### {name}")
        lines.append(f"脚本={script!r} 输入={data!r}")
        lines.append(f"exit={proc.returncode} out={proc.stdout!r} err={proc.stderr!r}")
        lines.append("")

    # ---- 空匹配的全局替换 ----
    case("空匹配-点星全局", r"s/.*/X/g", b"alpha\n")
    case("空匹配-点星全局-空行", r"s/.*/X/g", b"\n")
    case("空匹配-x星全局", r"s/x*/X/g", b"ab\n")
    case("空匹配-行首全局", r"s/^/X/g", b"ab\n")
    case("空匹配-a星全局", r"s/a*/X/g", b"aa\n")
    case("空匹配-单词界全局", r"s/\b/X/g", b"ab cd\n")
    case("空匹配-只替换一次", r"s/.*/X/", b"alpha\n")
    case("空匹配-第二个", r"s/.*/X/2", b"alpha\n")

    # ---- a/i/c 文本里的转义 ----
    case("文本-反斜杠n", "1a\\one\\ntwo")
    case("文本-反斜杠t", "1a\\a\\tb")
    case("文本-反斜杠反斜杠", "1a\\a\\\\b")
    case("文本-多行形式", "1a\\\nline1\nline2\n")
    case("文本-多行形式带转义", "1a\\\nline1\\nline2\n")
    case("文本-单行形式带n", "1a one\\ntwo")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[result] 报告已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
