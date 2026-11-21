#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""聚焦探针（三）：把两处差异的语义钉死。

1. 范围终点的 `~`：每行内容唯一，直接从输出反推覆盖了源文件哪几行。
2. BRE 里 `*` 跟在锚点（^ $）后面时 GNU 当字面量，本实现报错。

用法：python AI/脚本/_t1004_probe_sed_tilde.py
产物：AI/数据/sed_tilde_report.txt
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "sed_tilde_report.txt"
sys.path.insert(0, str(ROOT))

from w2l.commands.sed import run_sed  # noqa: E402

# 每行唯一：L1..L8，其中 L2/L4/L6 含 X
LINES = [f"L{i}" + ("X" if i in (2, 4, 6) else "") for i in range(1, 9)]
DATA = ("\n".join(LINES) + "\n").encode("utf-8")

# 含字面量 * 的语料，用来观察 GNU 怎么处理锚点后的 *
STAR = b"a*b\nplain\n*lead\n"


def find_sed() -> str:
    return shutil.which("sed") or r"C:\Program Files\Git\usr\bin\sed.exe"


def gnu(sed, tmp, script, options, fname):
    sp = tmp / "s.sed"
    sp.write_bytes(script.encode("utf-8"))
    return subprocess.run(
        [sed, *options, "-f", "s.sed", fname],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(tmp),
    )


def mine(script, options, fname, cwd):
    try:
        code, out, err = run_sed([*options, script, fname], cwd=cwd)
        return code, out, err
    except Exception as exc:  # noqa: BLE001
        return -1, "", f"{type(exc).__name__}: {exc}"


def main() -> int:
    sed = find_sed()
    tmp = Path(tempfile.mkdtemp(prefix="sedtilde_"))
    (tmp / "u.txt").write_bytes(DATA)
    (tmp / "star.txt").write_bytes(STAR)

    L: list[str] = []
    L.append("语料 u.txt 每行内容: " + " ".join(LINES))
    L.append("含 X 的行是 L2 / L4 / L6")
    L.append("")

    L.append("=" * 70)
    L.append("一、起点是正则时：/X/,~N")
    L.append("=" * 70)
    for step in range(0, 5):
        script = f"/X/,~{step}p"
        g = gnu(sed, tmp, script, ["-n"], "u.txt")
        mc, mo, me = mine(script, ["-n"], "u.txt", tmp)
        L.append(f"脚本={script!r}")
        L.append(f"  GNU   覆盖行={g.stdout.decode('utf-8','replace').split()}")
        L.append(f"  本实现 覆盖行={mo.split()}")
        if me:
            L.append(f"  本实现 stderr={me!r}")
        L.append("")

    L.append("=" * 70)
    L.append("二、起点是行号时：N,~M")
    L.append("=" * 70)
    for start in (1, 2, 3):
        for step in (1, 2, 3):
            script = f"{start},~{step}p"
            g = gnu(sed, tmp, script, ["-n"], "u.txt")
            mc, mo, me = mine(script, ["-n"], "u.txt", tmp)
            L.append(f"脚本={script!r}")
            L.append(f"  GNU   覆盖行={g.stdout.decode('utf-8','replace').split()}")
            L.append(f"  本实现 覆盖行={mo.split()}")
            if me:
                L.append(f"  本实现 stderr={me!r}")
            L.append("")

    L.append("=" * 70)
    L.append("三、起点正则 + 终点正则（对照，验证 ~ 的特殊性）")
    L.append("=" * 70)
    for script in ("/X/,/X/p", "/X/,/L7/p"):
        g = gnu(sed, tmp, script, ["-n"], "u.txt")
        mc, mo, me = mine(script, ["-n"], "u.txt", tmp)
        L.append(f"脚本={script!r}")
        L.append(f"  GNU   覆盖行={g.stdout.decode('utf-8','replace').split()}")
        L.append(f"  本实现 覆盖行={mo.split()}")
        L.append("")

    L.append("=" * 70)
    L.append("四、锚点后面的 * （语料 star.txt: a*b / plain / *lead）")
    L.append("=" * 70)
    for script in ("s/^*/X/", "s/$*/X/", "s/^*/X/g", "s/*/X/", "s/^\\*/X/",
                   "s/\\(^*\\)/X/", "s/^\\{0\\}*X/"):
        g = gnu(sed, tmp, script, [], "star.txt")
        mc, mo, me = mine(script, [], "star.txt", tmp)
        L.append(f"脚本={script!r}")
        L.append(f"  GNU   exit={g.returncode} out={g.stdout.decode('utf-8','replace')!r}"
                 + (f" err={g.stderr.decode('utf-8','replace').strip()!r}" if g.stderr else ""))
        L.append(f"  本实现 exit={mc} out={mo!r}")
        if me:
            L.append(f"  本实现 stderr={me!r}")
        L.append("")

    L.append("=" * 70)
    L.append("五、ERE 模式下同样的锚点 + *")
    L.append("=" * 70)
    for script in ("s/^*/X/", "s/$*/X/"):
        g = gnu(sed, tmp, script, ["-r"], "star.txt")
        mc, mo, me = mine(script, ["-r"], "star.txt", tmp)
        L.append(f"脚本={script!r} 选项=['-r']")
        L.append(f"  GNU   exit={g.returncode} out={g.stdout.decode('utf-8','replace')!r}"
                 + (f" err={g.stderr.decode('utf-8','replace').strip()!r}" if g.stderr else ""))
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
