#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定位 sed 差分里丢行的原因。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from w2l.commands import sed as sed_mod  # noqa: E402

FIXTURE = "alpha\nbravo\ncharlie\ndelta\necho\n"

lines = sed_mod._split_raw_lines(FIXTURE, "\n")
print("切行结果:", lines)

class Args:
    null_data = False
    binary = False

raw = FIXTURE.encode("utf-8")
enc = sed_mod._detect_encoding(raw[:8192])
print("判定编码:", enc)
decoded = raw.decode(enc, errors="replace")
print("解码结果:", repr(decoded))
print("再切一次:", sed_mod._split_raw_lines(decoded, "\n"))

source = sed_mod._LineSource(sed_mod._split_raw_lines(decoded, "\n"))
out: list[str] = []
writer = sed_mod._Writer(out.append)
commands, labels = sed_mod._ScriptParser("s/a/b/", False).parse()
print("解析出的命令:", commands)
engine = sed_mod._Engine(commands, labels, False)
engine.run(source, writer)
print("引擎输出:", out)
