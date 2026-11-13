#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读取 AI/教程进度.md 末尾最近一条 tick 的时间戳，判断是否落在 30 分钟活动窗口内。"""
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PROGRESS = ROOT / "AI" / "教程进度.md"

if not PROGRESS.exists():
    print("[result] 教程进度文件不存在，跳过活动窗口检查")
    sys.exit(0)

text = PROGRESS.read_text(encoding="utf-8", errors="replace")

# tick 标题形如：#### tick #12（2026-11-13 02:15）— xxx
pat = re.compile(r"tick\s*#\d+[^\n]*?(\d{4}-\d{2}-\d{2})\s+(\d{2}):(\d{2})")
hits = pat.findall(text)

if not hits:
    print("[result] 教程进度文件里没找到 tick 时间戳，跳过活动窗口检查")
    sys.exit(0)

d, hh, mm = hits[-1]
ts = time.mktime(time.strptime(f"{d} {hh}:{mm}", "%Y-%m-%d %H:%M"))
age = time.time() - ts

print(f"[result] 教程最近 tick: {d} {hh}:{mm}，距今 {age / 60:.1f} 分钟")
if age < 30 * 60:
    print("[result] 判定：教程任务刚跑过，本轮应跳过")
    sys.exit(1)
print("[result] 判定：教程任务不在活动窗口内，可以开工")
sys.exit(0)
