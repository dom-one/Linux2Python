#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""聚焦探针：查清两处与 GNU sed 4.9 的差异到底差在哪。

1. BRE 里行首的 `*`（`s/^*/X/`）：GNU 不报错，本实现报「无效的正则表达式」。
2. 范围终点的 `~`（`/bravo/,~2p`）：两边输出的行数不同。

用法：python AI/脚本/_t1002_probe_sed_focus.py
产物：AI/数据/sed_focus_report.txt
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "sed_focus_report.txt"
sys.path.insert(0, str(ROOT))

from w2l.commands.sed import run_sed  # noqa: E402

# 语料：bravo 出现三次，中间夹别的行
MULTI = b"bravo\ncharlie\nbravo\ndelta\nbravo\necho\n"
SIMPLE = b"alpha\nbravo\ncharlie\ndelta\necho\n"


def find_sed() -> str:
    return shutil.which("sed") or r"C:\Program Files\Git\usr\bin\sed.exe"


def both(sed: str, tmp: Path, script: str, options: list[str], fname: str) -> tuple[str, str, int, int]:
    """同一脚本跑两边，返回 (gnu 输出, 本实现输出, gnu 退出码, 本实现退出码)。"""
    sp = tmp / "s.sed"
    sp.write_bytes(script.encode("utf-8"))
    gnu = subprocess.run(
        [sed, *options, "-f", "s.sed", fname],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(tmp),
    )
    try:
        mine = run_sed([*options, script, fname], cwd=tmp)
        return (
            gnu.stdout.decode("utf-8", "replace"),
            mine[1],
            gnu.returncode,
            mine[0],
        )
    except Exception as exc:  # noqa: BLE001
        return (
            gnu.stdout.decode("utf-8", "replace"),
            f"<{type(exc).__name__}: {exc}>",
            gnu.returncode,
            -1,
        )


def main() -> int:
    sed = find_sed()
    tmp = Path(tempfile.mkdtemp(prefix="sedfocus_"))
    (tmp / "simple.txt").write_bytes(SIMPLE)
    (tmp / "multi.txt").write_bytes(MULTI)

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("第一处：BREL 行首的 *")
    lines.append("=" * 60)
    lines.append("语料 simple.txt: alpha/bravo/charlie/delta/echo")
    lines.append("")
    for script in ("s/^*/X/", "s/^*/X/", "s/*/X/", "s/*x/Y/", "s/a*/X/", "s/^*alpha/X/"):
        g, m, gc, mc = both(sed, tmp, script, [], "simple.txt")
        lines.append(f"脚本 {script!r}")
        lines.append(f"  GNU   exit={gc} out={g!r}")
        lines.append(f"  本实现 exit={mc} out={m!r}")
        lines.append("")

    lines.append("=" * 60)
    lines.append("第二处：范围终点的 ~ （语料 multi.txt）")
    lines.append("multi.txt: bravo/charlie/bravo/delta/bravo/echo")
    lines.append("行号：  1      2       3      4      5     6")
    lines.append("bravo 出现在第 1、3、5 行")
    lines.append("")
    for script in (
        "/bravo/,~1p",
        "/bravo/,~2p",
        "/bravo/,~3p",
        "/bravo/,~0p",
        "/bravo/,~1",
        "1,~2p",
        "1,~3p",
        "2,~2p",
    ):
        g, m, gc, mc = both(sed, tmp, script, ["-n"], "multi.txt")
        gnum = [i + 1 for i, ch in enumerate(g.splitlines())]
        mnum = [i + 1 for i, ch in enumerate(m.splitlines())]
        lines.append(f"脚本 {script!r}")
        lines.append(f"  GNU   exit={gc} 输出行号={gnum} 内容={g!r}")
        lines.append(f"  本实现 exit={mc} 输出行号={mnum} 内容={m!r}")
        lines.append("")

    lines.append("=" * 60)
    lines.append("第二处补充：simple.txt（bravo 只出现一次）")
    lines.append("simple.txt: alpha/bravo/charlie/delta/echo")
    lines.append("")
    for script in ("/bravo/,~1p", "/bravo/,~2p", "/bravo/,~3p", "/alpha/,~2p"):
        g, m, gc, mc = both(sed, tmp, script, ["-n"], "simple.txt")
        gnum = [i + 1 for i, ch in enumerate(g.splitlines())]
        mnum = [i + 1 for i, ch in enumerate(m.splitlines())]
        lines.append(f"脚本 {script!r}")
        lines.append(f"  GNU   exit={gc} 输出行号={gnum} 内容={g!r}")
        lines.append(f"  本实现 exit={mc} 输出行号={mnum} 内容={m!r}")
        lines.append("")

    lines.append("=" * 60)
    lines.append("第三处：first~step 作首地址（multi.txt）")
    lines.append("")
    for script in ("1~2p", "2~2p", "1~1p"):
        g, m, gc, mc = both(sed, tmp, script, ["-n"], "multi.txt")
        gnum = [i + 1 for i, ch in enumerate(g.splitlines())]
        mnum = [i + 1 for i, ch in enumerate(m.splitlines())]
        lines.append(f"脚本 {script!r}")
        lines.append(f"  GNU   exit={gc} 输出行号={gnum}")
        lines.append(f"  本实现 exit={mc} 输出行号={mnum}")
        lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("\n".join(lines))
    print(f"[result] 报告已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
