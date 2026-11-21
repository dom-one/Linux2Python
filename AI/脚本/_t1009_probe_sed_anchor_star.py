#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针：GNU BRE 里锚点后面跟 `*` 的确切语义，以及本实现的反应。

上一轮只测了「本实现报错」，没查清 GNU 到底把它当什么。
这一轮用内容各不相同的行反推匹配到了什么。

用法：python AI/脚本/_t1009_probe_sed_anchor_star.py
产物：AI/数据/sed_anchor_star_report.txt
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "sed_anchor_star_report.txt"
sys.path.insert(0, str(ROOT))

from w2l.commands.sed import run_sed  # noqa: E402

# 每行内容唯一，能从输出反推匹配了哪一段
DATA = b"lead\n*star\nmid*dle\ntail*\nx*y\n\n"
# 单独的对照：只有锚点与字面星号
DATA2 = b"*a\nb*\n"


def find_sed() -> str:
    return shutil.which("sed") or r"C:\Program Files\Git\usr\bin\sed.exe"


def gnu(sed, tmp, script, fname, options=()):
    sp = tmp / "s.sed"
    sp.write_bytes(script.encode("utf-8"))
    return subprocess.run(
        [sed, *options, "-f", "s.sed", fname],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(tmp),
    )


def mine(script, fname, cwd, options=()):
    try:
        code, out, err = run_sed([*options, script, fname], cwd=cwd)
        return code, out, err
    except Exception as exc:  # noqa: BLE001
        return -1, "", f"{type(exc).__name__}: {exc}"


def main() -> int:
    sed = find_sed()
    tmp = Path(tempfile.mkdtemp(prefix="sedanchor_"))
    (tmp / "s1.txt").write_bytes(DATA)
    (tmp / "s2.txt").write_bytes(DATA2)

    L: list[str] = []
    L.append("语料 s1.txt（每行内容唯一）:")
    for i, line in enumerate(DATA.decode("utf-8").split("\n")[:-1], 1):
        L.append(f"  第 {i} 行: {line!r}")
    L.append("")
    L.append("语料 s2.txt: '*a' / 'b*'")
    L.append("")

    for fname, cases in (
        ("s1.txt", ("s/^*/X/", "s/$*/X/", "s/a^*/X/", "s/^*a/X/",
                    "s/^*/X/g", "s/$*/X/g", "s/*/X/", "s/^*/X/;s/$/Y/")),
        ("s2.txt", ("s/^*/X/", "s/$*/X/", "s/^*/X/g")),
    ):
        L.append("=" * 70)
        L.append(f"语料 {fname}")
        L.append("=" * 70)
        for script in cases:
            g = gnu(sed, tmp, script, fname)
            mc, mo, me = mine(script, fname, tmp)
            L.append(f"脚本={script!r}")
            L.append(f"  GNU   exit={g.returncode} out={g.stdout.decode('utf-8', 'replace')!r}")
            if g.stderr:
                L.append(f"  GNU   err={g.stderr.decode('utf-8', 'replace').strip()!r}")
            L.append(f"  本实现 exit={mc} out={mo!r}")
            if me:
                L.append(f"  本实现 stderr={me!r}")
            L.append("")

    OUT.write_text("\n".join(L), encoding="utf-8", newline="\n")
    print("\n".join(L))
    print(f"[result] 报告已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
