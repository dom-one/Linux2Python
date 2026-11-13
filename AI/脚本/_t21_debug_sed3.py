#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定位 sed -n '/TODO/p' 的解析问题。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from w2l.commands import sed as sed_mod  # noqa: E402

for script in ["/TODO/p", "s/a/b/", "/warn/p", "2p"]:
    print(f"脚本={script!r}")
    try:
        commands, labels = sed_mod._ScriptParser(script, False).parse()
        for index, command in enumerate(commands):
            print(f"  [{index}] name={command.name!r} addr1={command.addr1}")
    except Exception as exc:  # noqa: BLE001
        print(f"  报错: {exc}")
