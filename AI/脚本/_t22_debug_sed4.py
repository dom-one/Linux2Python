#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""看看 argparse 把 CLI 参数解析成了什么。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from w2l.commands.sed import build_parser  # noqa: E402

for argv in (
    ["-n", "/TODO/p", "README.md"],
    ["-n", "/warn/p", "README.md"],
    ["-n", "2p", "README.md"],
    ["s/a/b/", "README.md"],
):
    namespace = build_parser().parse_args(argv)
    print(f"argv={argv!r}")
    print(f"  script={namespace.script!r} files={namespace.files!r} quiet={namespace.quiet}")
