#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针：地址分隔符的各种写法，本实现 vs GNU sed 4.9。

背景：README 第 499 行与第 550 行推荐用 `\\|TODO\\|p` 这种写法绕开
Git Bash 的 MSYS 路径改写。本脚本把各种写法逐条跑一遍，
看本实现与 GNU 各自认不认。

注意：脚本用 subprocess 直接 spawn，不经过 shell，
所以 MSYS 的路径改写只在「真实命令行」那条路上发生。
真实命令行那条路单独用 subprocess 跑 bash -c。

用法：python AI/脚本/_t1014_probe_sed_delim.py
产物：AI/数据/sed_delim_report.txt
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "sed_delim_report.txt"
BASH = r"E:\software\Git\Git\bin\bash.exe"
sys.path.insert(0, str(ROOT))

from w2l.commands.sed import run_sed  # noqa: E402

FORMS = [
    r"/bravo/p",
    r"\|bravo|p",
    r"\|bravo\|p",
    r"\%bravo%p",
    r"\?bravo?p",
    r"\#bravo#p",
    r"|bravo|p",
]


def find_sed() -> str:
    return shutil.which("sed") or r"C:\Program Files\Git\usr\bin\sed.exe"


def main() -> int:
    sed = find_sed()
    tmp = Path(tempfile.mkdtemp(prefix="seddelim_"))
    (tmp / "a.txt").write_bytes(b"alpha\nbravo\ncharlie\ndelta\necho\n")

    L: list[str] = []
    L.append("语料 a.txt: alpha/bravo/charlie/delta/echo")
    L.append("")

    L.append("=" * 70)
    L.append("一、subprocess 直 spawn（不经 shell，没有 MSYS 改写）")
    L.append("=" * 70)
    for form in FORMS:
        script = form + "p" if not form.endswith("p") else form
        # 拼成完整脚本：形式里已含 p 的直接用，否则补
        sp = tmp / "s.sed"
        sp.write_text(script, encoding="utf-8")
        g = subprocess.run(
            [sed, "-n", "-f", "s.sed", "a.txt"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(tmp),
        )
        try:
            code, so, se = run_sed(["-n", script, "a.txt"], cwd=tmp)
        except Exception as exc:  # noqa: BLE001
            code, so, se = -1, "", f"{type(exc).__name__}: {exc}"
        L.append(f"脚本={script!r}")
        L.append(f"  GNU   exit={g.returncode} out={g.stdout.decode('utf-8','replace')!r}"
                 + (f" err={g.stderr.decode('utf-8','replace').strip()!r}" if g.stderr else ""))
        L.append(f"  本实现 exit={code} out={so!r}" + (f" err={se!r}" if se else ""))
        L.append("")

    L.append("=" * 70)
    L.append("二、真实命令行（bash -c，经 MSYS 路径改写）")
    L.append("=" * 70)
    for form in (r"/bravo/p", r"\|bravo|p", r"\|bravo\|p"):
        cmd = f"python main.py sed -n '{form}' AI/数据/sed_demo/a.txt"
        proc = subprocess.run(
            [BASH, "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=str(ROOT),
        )
        L.append(f"命令: {cmd}")
        L.append(f"  exit={proc.returncode}")
        L.append(f"  stdout={proc.stdout.decode('utf-8','replace')!r}")
        L.append(f"  stderr={proc.stderr.decode('utf-8','replace').strip()!r}")
        L.append("")

    L.append("=" * 70)
    L.append("三、加 MSYS_NO_PATHCONV=1 之后")
    L.append("=" * 70)
    for form in (r"/bravo/p",):
        cmd = f"MSYS_NO_PATHCONV=1 python main.py sed -n '{form}' AI/数据/sed_demo/a.txt"
        proc = subprocess.run(
            [BASH, "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=str(ROOT),
        )
        L.append(f"命令: {cmd}")
        L.append(f"  exit={proc.returncode}")
        L.append(f"  stdout={proc.stdout.decode('utf-8','replace')!r}")
        L.append(f"  stderr={proc.stderr.decode('utf-8','replace').strip()!r}")
        L.append("")

    L.append("=" * 70)
    L.append("四、README 第 499/550 行推荐的写法，本实现认不认")
    L.append("=" * 70)
    for form in (r"\|TODO\|p", r"\|TODO|p"):
        script = form.replace("TODO", "bravo")
        try:
            code, so, se = run_sed(["-n", script, "a.txt"], cwd=tmp)
        except Exception as exc:  # noqa: BLE001
            code, so, se = -1, "", f"{type(exc).__name__}: {exc}"
        L.append(f"脚本={script!r}")
        L.append(f"  本实现 exit={code} out={so!r}" + (f" err={se!r}" if se else ""))
        L.append("")

    OUT.write_text("\n".join(L), encoding="utf-8", newline="\n")
    print("\n".join(L))
    print(f"[result] 报告已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
