#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复核探针：把「锚点后面的 *」这一处单独重跑一遍，逐字节看输出。

上一轮探针里 `s/$*/X/` 的结果看起来与 `s/^*/X/` 不对称
（一个是把行首的 * 换掉，一个是给每行前面加 X），
这条要单独确认，不能靠印象写进教程。

用法：python AI/脚本/_t1005_probe_sed_star.py
产物：AI/数据/sed_star_report.txt
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "sed_star_report.txt"
sys.path.insert(0, str(ROOT))

from w2l.commands.sed import run_sed  # noqa: E402

STAR = b"a*b\nplain\n*lead\n"
DOLLAR = b"plain\nstar$\nend$\n"


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
    tmp = Path(tempfile.mkdtemp(prefix="sedstar_"))
    (tmp / "star.txt").write_bytes(STAR)
    (tmp / "dollar.txt").write_bytes(DOLLAR)

    L: list[str] = []
    L.append("语料 star.txt: a*b / plain / *lead")
    L.append("语料 dollar.txt: plain / star$ / end$")
    L.append("")

    for fname, cases in (
        ("star.txt", ("s/^/Y/", "s/$/Z/", "s/^*/X/", "s/$*/X/", "s/^*/X/g",
                      "s/$*/X/g", "s/^\\*/X/", "s/\\*$/X/")),
        ("dollar.txt", ("s/^/Y/", "s/$/Z/", "s/$*/X/", "s/^*/X/",
                        "s/^*/X/g", "s/$*/X/g")),
    ):
        L.append("=" * 70)
        L.append(f"语料 {fname}")
        L.append("=" * 70)
        for script in cases:
            g = gnu(sed, tmp, script, fname)
            mc, mo, me = mine(script, fname, tmp)
            L.append(f"脚本={script!r}")
            L.append(f"  GNU   exit={g.returncode} out_bytes={g.stdout!r}")
            if g.stderr:
                L.append(f"  GNU   err={g.stderr.decode('utf-8','replace').strip()!r}")
            L.append(f"  本实现 exit={mc} out={mo.encode('utf-8')!r}")
            if me:
                L.append(f"  本实现 stderr={me!r}")
            L.append("")

    L.append("=" * 70)
    L.append("同一批脚本在 -r (ERE) 下")
    L.append("=" * 70)
    for script in ("s/^/Y/", "s/^*/X/", "s/$*/X/", "s/\\*$/X/"):
        g = gnu(sed, tmp, script, "star.txt", ("-r",))
        mc, mo, me = mine(script, "star.txt", tmp, ("-r",))
        L.append(f"脚本={script!r}")
        L.append(f"  GNU   exit={g.returncode} out_bytes={g.stdout!r}")
        if g.stderr:
            L.append(f"  GNU   err={g.stderr.decode('utf-8','replace').strip()!r}")
        L.append(f"  本实现 exit={mc} out={mo.encode('utf-8')!r}")
        if me:
            L.append(f"  本实现 stderr={me!r}")
        L.append("")

    OUT.write_text("\n".join(L), encoding="utf-8", newline="\n")
    print("\n".join(L))
    print(f"[result] 报告已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
