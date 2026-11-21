#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针：`-i` 选项在真实 CLI 入口上到底能不能用。

背景：
`split_inplace()`（sed.py 第 1221 行）是专门为 `-i` / `-i.bak` 写的 argv 改写函数，
但它只在 `run_sed()`（给测试用的薄封装，第 1381 行）里被调用。
真实入口 `w2l/cli.py` 第 83 行直接 `parser.parse_args(argv[1:])`，
没走 `split_inplace`。
所以 `python main.py sed -i ...` 走 argparse 时，`-i` 不是已注册选项，
argparse 会报 unrecognized arguments。

本脚本分别走三条路径验证：
1. 真实 CLI（subprocess 跑 main.py）
2. run_sed（测试用的封装）
3. 直接调 split_inplace + build_parser().parse_args（模拟真实入口该走的路）

用法：python AI/脚本/_t1013_probe_sed_inplace.py
产物：AI/数据/sed_inplace_report.txt
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "sed_inplace_report.txt"
sys.path.insert(0, str(ROOT))

from w2l.commands.sed import build_parser, run_sed, split_inplace  # noqa: E402

BASE = b"alpha\nbravo\ncharlie\ndelta\necho\n"


def main() -> int:
    L: list[str] = []
    L.append("=" * 70)
    L.append("一、真实 CLI 入口（python main.py sed ...）")
    L.append("=" * 70)
    tmp = Path(tempfile.mkdtemp(prefix="sedip_"))
    for label, args in (
        ("sed -i", ["-i", "s/a/A/g"]),
        ("sed -i.bak", ["-i.bak", "s/a/A/g"]),
        ("sed --in-place", ["--in-place", "s/a/A/g"]),
        ("sed --in-place-suffix=.bak", ["--in-place-suffix=.bak", "s/a/A/g"]),
        ("sed -ni", ["-ni", "s/a/A/g"]),
    ):
        target = tmp / "t.txt"
        target.write_bytes(BASE)
        proc = subprocess.run(
            [sys.executable, "main.py", "sed", *args, str(target)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(ROOT),
        )
        L.append(f"{label}")
        L.append(f"  exit={proc.returncode}")
        L.append(f"  stdout={proc.stdout.decode('utf-8', 'replace')!r}")
        L.append(f"  stderr={proc.stderr.decode('utf-8', 'replace').strip()!r}")
        L.append(f"  文件内容={target.read_bytes()!r}")
        L.append("")

    L.append("=" * 70)
    L.append("二、run_sed（测试用的封装，内部调了 split_inplace）")
    L.append("=" * 70)
    for label, args in (
        ("-i", ["-i", "s/a/A/g"]),
        ("-i.bak", ["-i.bak", "s/a/A/g"]),
    ):
        target = tmp / "t2.txt"
        target.write_bytes(BASE)
        code, so, se = run_sed([*args, str(target)], cwd=tmp)
        L.append(f"{label}")
        L.append(f"  exit={code}")
        L.append(f"  stdout={so!r}")
        L.append(f"  stderr={se!r}")
        L.append(f"  文件内容={target.read_bytes()!r}")
        L.append("")

    L.append("=" * 70)
    L.append("三、模拟真实入口该走的路（split_inplace + parse_args）")
    L.append("=" * 70)
    for label, args in (
        ("-i", ["-i", "s/a/A/g"]),
        ("-i.bak", ["-i.bak", "s/a/A/g"]),
        ("-ni", ["-ni", "s/a/A/g"]),
        ("-rni", ["-rni", "s/a/A/g"]),
    ):
        rewritten = split_inplace(args)
        L.append(f"{label}")
        L.append(f"  split_inplace 改写后 = {rewritten!r}")
        try:
            ns = build_parser().parse_args(rewritten)
            L.append(f"  parse_args 成功: in_place={ns.in_place} "
                     f"suffix={ns.in_place_suffix!r} quiet={ns.quiet}")
        except SystemExit as exc:
            L.append(f"  parse_args 退出码={exc.code}")
        L.append("")

    L.append("=" * 70)
    L.append("四、build_parser 里注册了哪些选项（argparse 的 dest）")
    L.append("=" * 70)
    parser = build_parser()
    for action in parser._actions:
        if action.option_strings:
            L.append(f"  {action.option_strings}  dest={action.dest}")
    L.append("")

    L.append("=" * 70)
    L.append("五、cli.py 的真实调用方式")
    L.append("=" * 70)
    cli_src = (ROOT / "w2l" / "cli.py").read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(cli_src, 1):
        if "parse_args" in line or "parser_factory" in line:
            L.append(f"  第 {i} 行: {line.strip()}")
    L.append("")
    L.append("  cli.py 里没有出现 split_inplace —— 所以真实入口不走那段改写。")

    OUT.write_text("\n".join(L), encoding="utf-8", newline="\n")
    print("\n".join(L))
    print(f"[result] 报告已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
