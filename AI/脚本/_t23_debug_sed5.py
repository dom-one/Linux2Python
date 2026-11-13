#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复现 CLI 路径下的 sed 报错并打印调用栈。"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import w2l.cli as cli  # noqa: E402
from w2l.commands.sed import build_parser, sed as sed_handler  # noqa: E402
from w2l.context import RunContext  # noqa: E402
import io  # noqa: E402

argv = ["sed", "-n", "/warn/p", "README.md"]
namespace = build_parser().parse_args(argv[1:])
print("namespace.script =", repr(namespace.script))
print("namespace.files  =", namespace.files)

ctx = RunContext(
    cwd=ROOT,
    stdout=io.StringIO(),
    stderr=io.StringIO(),
    stdin=io.StringIO(""),
)
try:
    code = sed_handler(namespace, ctx)
    print("退出码", code)
except Exception:  # noqa: BLE001
    traceback.print_exc()
