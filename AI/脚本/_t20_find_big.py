#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""找出 AI/ 下的大文件（REPL 崩溃循环留下的日志）。"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
AI = ROOT / "AI"

rows = []
total = 0
for path in AI.rglob("*"):
    if path.is_file():
        size = path.stat().st_size
        total += size
        rows.append((size, path))
rows.sort(reverse=True)
print(f"[result] AI 目录合计 {total / 1024 / 1024:.1f} MB，文件数 {len(rows)}")
for size, path in rows[:12]:
    print(f"[result] {size / 1024 / 1024:10.2f} MB  {path}")
