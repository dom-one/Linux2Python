#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""聚焦探针（二）：查清教程要写的各处行为。

1. BRE 里 `^` 之后的 `*`（本实现抛「无效的正则表达式」，GNU 当字面量）
2. 范围终点的 `~` 的实际语义（按源文件行号统计，不是输出行号）
3. -i 与 -n 一起用会不会把文件清空
4. --in-place-suffix 的备份文件
5. -z 用 NUL 分隔
6. GBK 文件的编码判定
7. -n 下 a/i/c 文本、= 行号照样输出
8. q N 的退出码

用法：python AI/脚本/_t1003_probe_sed_more.py
产物：AI/数据/sed_more_report.txt
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "sed_more_report.txt"
sys.path.insert(0, str(ROOT))

from w2l.commands.sed import run_sed  # noqa: E402

MULTI = b"bravo\ncharlie\nbravo\ndelta\nbravo\necho\n"
SIMPLE = b"alpha\nbravo\ncharlie\ndelta\necho\n"


def find_sed() -> str:
    return shutil.which("sed") or r"C:\Program Files\Git\usr\bin\sed.exe"


def gnu_run(sed: str, tmp: Path, script: str, options: list[str], fname: str):
    sp = tmp / "s.sed"
    sp.write_bytes(script.encode("utf-8"))
    return subprocess.run(
        [sed, *options, "-f", "s.sed", fname],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(tmp),
    )


def mine_run(script: str, options: list[str], fname: str, cwd: Path):
    try:
        code, out, err = run_sed([*options, script, fname], cwd=cwd)
        return code, out, err
    except Exception as exc:  # noqa: BLE001
        return -1, "", f"{type(exc).__name__}: {exc}"


def show(lines, title, script, options, fname, tmp, sed):
    g = gnu_run(sed, tmp, script, options, fname)
    mc, mo, me = mine_run(script, options, fname, tmp)
    lines.append(f"{title}: 脚本={script!r} 选项={options!r}")
    lines.append(f"  GNU   exit={g.returncode} out={g.stdout.decode('utf-8','replace')!r}")
    lines.append(f"  本实现 exit={mc} out={mo!r}")
    if me:
        lines.append(f"  本实现 stderr={me!r}")
    lines.append("")


def main() -> int:
    sed = find_sed()
    tmp = Path(tempfile.mkdtemp(prefix="sedmore_"))
    (tmp / "simple.txt").write_bytes(SIMPLE)
    (tmp / "multi.txt").write_bytes(MULTI)
    # GBK 文件
    (tmp / "gbk.txt").write_bytes("第一行\n第二行\n".encode("gbk"))

    L: list[str] = []

    L.append("=" * 66)
    L.append("一、BRE：^ 之后的 * （simple.txt）")
    L.append("=" * 66)
    for script in ("s/^*/X/", "s/^*alpha/X/", "s/$*/X/", "s/*/X/", "s/a*/X/"):
        show(L, "", script, [], "simple.txt", tmp, sed)

    L.append("=" * 66)
    L.append("二、范围终点 ~ 的语义（multi.txt，bravo 在第 1/3/5 行）")
    L.append("=" * 66)
    L.append("说明：下面用「输出行的内容」判断覆盖了源文件的哪些行。")
    L.append("multi.txt 六行内容依次是: bravo/bravo/bravo/delta/bravo/echo")
    L.append("     （第 1、3、5 行是 bravo）")
    L.append("")
    for script in ("/bravo/,~0p", "/bravo/,~1p", "/bravo/,~2p", "/bravo/,~3p",
                   "1,~2p", "1,~3p", "2,~2p"):
        g = gnu_run(sed, tmp, script, ["-n"], "multi.txt")
        mc, mo, me = mine_run(script, ["-n"], "multi.txt", tmp)
        gl = g.stdout.decode("utf-8", "replace").splitlines()
        ml = mo.splitlines() if mo else []
        L.append(f"脚本={script!r}")
        L.append(f"  GNU   命中的源行={gl}")
        L.append(f"  本实现 命中的源行={ml}")
        if me:
            L.append(f"  本实现 stderr={me!r}")
        L.append("")

    L.append("=" * 66)
    L.append("三、-i 与 -n 一起用")
    L.append("=" * 66)
    for tag, opts in (("GNU -i", ["-i"]), ("GNU -i -n", ["-i", "-n"])):
        target = tmp / f"gnu_{tag.replace(' ', '_').replace('-', '')}.txt"
        target.write_bytes(SIMPLE)
        g = gnu_run(sed, tmp, "s/a/A/g", opts, target.name)
        L.append(f"{tag}: exit={g.returncode} 文件内容={target.read_bytes()!r}")
    for tag, opts in (("本实现 -i", ["-i"]), ("本实现 -i -n", ["-i", "-n"])):
        target = tmp / f"mine_{tag.replace(' ', '_').replace('-', '')}.txt"
        target.write_bytes(SIMPLE)
        mc, mo, me = mine_run("s/a/A/g", opts, target.name, tmp)
        L.append(f"{tag}: exit={mc} 文件内容={target.read_bytes()!r}")
    L.append("")

    L.append("=" * 66)
    L.append("四、--in-place-suffix 备份文件")
    L.append("=" * 66)
    gtarget = tmp / "gnu_bak.txt"
    gtarget.write_bytes(SIMPLE)
    gnu_run(sed, tmp, "s/a/A/g", ["-i.bak"], gtarget.name)
    L.append(f"GNU   主文件={gtarget.read_bytes()!r}")
    gbak = tmp / "gnu_bak.txt.bak"
    L.append(f"GNU   备份存在={gbak.exists()} 内容={(gbak.read_bytes() if gbak.exists() else None)!r}")
    mtarget = tmp / "mine_bak.txt"
    mtarget.write_bytes(SIMPLE)
    mc, mo, me = mine_run("s/a/A/g", ["--in-place-suffix=.bak"], "mine_bak.txt", tmp)
    mbak = tmp / "mine_bak.txt.bak"
    L.append(f"本实现 主文件={mtarget.read_bytes()!r}")
    L.append(f"本实现 备份存在={mbak.exists()} 内容={(mbak.read_bytes() if mbak.exists() else None)!r}")
    L.append("")

    L.append("=" * 66)
    L.append("五、-z 用 NUL 分隔")
    L.append("=" * 66)
    (tmp / "nul.txt").write_bytes(b"aaa\x00bbb\x00ccc\x00")
    g = gnu_run(sed, tmp, "s/a/X/", ["-z"], "nul.txt")
    L.append(f"GNU   exit={g.returncode} out={g.stdout!r}")
    mc, mo, me = mine_run("s/a/X/", ["-z"], "nul.txt", tmp)
    L.append(f"本实现 exit={mc} out={mo.encode('utf-8')!r}")
    L.append("")

    L.append("=" * 66)
    L.append("六、GBK 文件的编码判定")
    L.append("=" * 66)
    g = gnu_run(sed, tmp, "s/一/ONE/", [], "gbk.txt")
    L.append(f"GNU   exit={g.returncode} out={g.stdout!r}")
    mc, mo, me = mine_run("s/一/ONE/", [], "gbk.txt", tmp)
    L.append(f"本实现 exit={mc} out={mo.encode('utf-8')!r}")
    L.append("")

    L.append("=" * 66)
    L.append("七、-n 下 a/i/c 与 = 照样输出")
    L.append("=" * 66)
    for script in ("1a\\APPENDED", "1i\\PREPENDED", "1c\\REPLACED", "="):
        show(L, "", script, ["-n"], "simple.txt", tmp, sed)

    L.append("=" * 66)
    L.append("八、q N 的退出码")
    L.append("=" * 66)
    for script in ("2q", "q3", "2q7"):
        g = gnu_run(sed, tmp, script, [], "simple.txt")
        mc, mo, me = mine_run(script, [], "simple.txt", tmp)
        L.append(f"脚本={script!r}")
        L.append(f"  GNU   exit={g.returncode} out={g.stdout.decode('utf-8','replace')!r}")
        L.append(f"  本实现 exit={mc} out={mo!r}")
        if me:
            L.append(f"  本实现 stderr={me!r}")
        L.append("")

    L.append("=" * 66)
    L.append("九、不支持的指令")
    L.append("=" * 66)
    for script in ("h", "H", "g", "G", "x", "l", "r f", "R f", "w f", "W f", "e", "z", "F",
                   "s/a/b/w out.txt", "s/a/b/e"):
        show(L, "", script, [], "simple.txt", tmp, sed)

    OUT.write_text("\n".join(L), encoding="utf-8", newline="\n")
    print("\n".join(L))
    print(f"[result] 报告已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
