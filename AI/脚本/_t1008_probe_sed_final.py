#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""聚焦探针（四）：把三处差异的边界钉死。

1. `,` 后面接 `~step` 的范围终点：GNU 的算法与本实现完全不同。
2. `first~step` 里 step 为 0 的写法。
3. `^` / `$` 之后的 `*`：GNU 当字面量，本实现直接报错。

用法：python AI/脚本/_t1008_probe_sed_final.py
产物：AI/数据/sed_final_report.txt
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "sed_final_report.txt"
sys.path.insert(0, str(ROOT))

from w2l.commands.sed import run_sed  # noqa: E402

LINES = [f"L{i}" + ("X" if i in (2, 4, 6) else "") for i in range(1, 9)]
DATA = ("\n".join(LINES) + "\n").encode("utf-8")
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
    tmp = Path(tempfile.mkdtemp(prefix="sedfinal_"))
    (tmp / "u.txt").write_bytes(DATA)
    (tmp / "star.txt").write_bytes(STAR)

    L: list[str] = []
    L.append("语料 u.txt: " + " ".join(LINES))
    L.append("")

    L.append("=" * 70)
    L.append("一、first~step（首地址），step=0 的写法")
    L.append("=" * 70)
    for script in ("1~0p", "1~1p", "1~2p", "2~0p", "2~2p"):
        g = gnu(sed, tmp, script, ["-n"], "u.txt")
        mc, mo, me = mine(script, ["-n"], "u.txt", tmp)
        L.append(f"脚本={script!r}")
        L.append(f"  GNU   exit={g.returncode} 覆盖行={g.stdout.decode('utf-8','replace').split()}")
        L.append(f"  本实现 exit={mc} 覆盖行={mo.split()}")
        if me:
            L.append(f"  本实现 stderr={me!r}")
        L.append("")

    L.append("=" * 70)
    L.append("二、, +step 的范围终点（首地址是行号）")
    L.append("=" * 70)
    for script in ("1,+2p", "1,+3p", "2,+2p", "3,+3p"):
        g = gnu(sed, tmp, script, ["-n"], "u.txt")
        mc, mo, me = mine(script, ["-n"], "u.txt", tmp)
        L.append(f"脚本={script!r}")
        L.append(f"  GNU   覆盖行={g.stdout.decode('utf-8','replace').split()}")
        L.append(f"  本实现 覆盖行={mo.split()}")
        L.append("")

    L.append("=" * 70)
    L.append("三、, ~step 的范围终点（首地址是行号）")
    L.append("=" * 70)
    L.append("GNU 上游算法（execute.c 的 ADDR_IS_STEP_MOD 分支）：")
    L.append("  范围开始时 end = start + step - (start % step)")
    L.append("")
    for script in ("1,~1p", "1,~2p", "1,~3p", "2,~1p", "2,~2p", "2,~3p",
                   "3,~1p", "3,~2p", "3,~3p", "4,~2p", "4,~3p"):
        g = gnu(sed, tmp, script, ["-n"], "u.txt")
        mc, mo, me = mine(script, ["-n"], "u.txt", tmp)
        L.append(f"脚本={script!r}")
        L.append(f"  GNU   覆盖行={g.stdout.decode('utf-8','replace').split()}")
        L.append(f"  本实现 覆盖行={mo.split()}")
        L.append("")

    L.append("=" * 70)
    L.append("四、, ~step 的范围终点（首地址是正则）")
    L.append("=" * 70)
    for script in ("/X/,~1p", "/X/,~2p", "/X/,~3p", "/X/,~4p"):
        g = gnu(sed, tmp, script, ["-n"], "u.txt")
        mc, mo, me = mine(script, ["-n"], "u.txt", tmp)
        L.append(f"脚本={script!r}")
        L.append(f"  GNU   覆盖行={g.stdout.decode('utf-8','replace').split()}")
        L.append(f"  本实现 覆盖行={mo.split()}")
        L.append("")

    L.append("=" * 70)
    L.append("五、锚点后面的 *（语料 star.txt: a*b / plain / *lead）")
    L.append("=" * 70)
    for script in ("s/^*/X/", "s/$*/X/", "s/a^*/X/", "s/^*a/X/",
                   "s/\\(^*\\)/X/", "s/^*/X/g"):
        g = gnu(sed, tmp, script, [], "star.txt")
        mc, mo, me = mine(script, [], "star.txt", tmp)
        L.append(f"脚本={script!r}")
        L.append(f"  GNU   exit={g.returncode} out={g.stdout.decode('utf-8','replace')!r}")
        if g.stderr:
            L.append(f"  GNU   err={g.stderr.decode('utf-8','replace').strip()!r}")
        L.append(f"  本实现 exit={mc} out={mo!r}")
        if me:
            L.append(f"  本实现 stderr={me!r}")
        L.append("")

    L.append("=" * 70)
    L.append("六、错误路径的退出码")
    L.append("=" * 70)
    for script in ("s/a/b", "s/a/b/", "nosuchcmd", "s/a/b/xyz", "/X/,~2p"):
        g = gnu(sed, tmp, script, [], "u.txt")
        mc, mo, me = mine(script, [], "u.txt", tmp)
        L.append(f"脚本={script!r}")
        L.append(f"  GNU   exit={g.returncode} err={g.stderr.decode('utf-8','replace').strip()!r}")
        L.append(f"  本实现 exit={mc} err={me!r}")
        L.append("")

    OUT.write_text("\n".join(L), encoding="utf-8", newline="\n")
    print("\n".join(L))
    print(f"[result] 报告已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
