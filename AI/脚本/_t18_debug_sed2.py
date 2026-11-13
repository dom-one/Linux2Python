#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定位 t 标签跳转为什么没生效。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from w2l.commands import sed as sed_mod  # noqa: E402

script = "/bravo/{s/a/X/;t end}\np\n:end"
commands, labels = sed_mod._ScriptParser(script, False).parse()
print("命令数:", len(commands))
for index, command in enumerate(commands):
    print(f"  [{index}] name={command.name} addr1={command.addr1} addr2={command.addr2} payload={command.payload}")
print("标签表:", labels)

out: list[str] = []
writer = sed_mod._Writer(out.append)
engine = sed_mod._Engine(commands, labels, True)
source = sed_mod._LineSource(["alpha\n", "bravo\n", "charlie\n", "delta\n", "echo\n"])
engine.run(source, writer)
print("输出:", out)
