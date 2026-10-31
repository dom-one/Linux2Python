"""把刚追加的 tick 日志编号从 #2 改回 #1。

原因：追加前先把文件头的「本次会话」写成了 tick #1，_t11_progress.py 是靠
扫描文件里最大的「tick #N」来算下一个编号的，于是把本轮算成了 #2。
开发任务此前没有任何 tick（文件头原本是「tick #0（尚未触发）」），本轮就是 #1。

改的是本轮自己刚写的那一段，不是历史段落；改完文件里编号自洽：
文件头与日志条目都是 #1。

用法：python AI/脚本/_t23_fix_tick_no.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROGRESS = ROOT / "AI" / "阅读进度.md"


def main() -> None:
    raw = PROGRESS.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")

    blocks = re.findall(r"^#### tick #(\d+)", text, flags=re.MULTILINE)
    print("改动前的日志编号：", blocks)

    if blocks == ["2"]:
        text = text.replace("#### tick #2（", "#### tick #1（", 1)
    elif blocks == ["1"]:
        print("编号已经是 #1，无需修改")
    else:
        raise SystemExit(f"日志编号不是预期状态，放弃修改：{blocks}")

    headers = re.findall(r"^本次会话：cron tick #(\d+)", text, flags=re.MULTILINE)
    print("文件头编号：", headers)

    final = re.findall(r"^#### tick #(\d+)", text, flags=re.MULTILINE)
    if final != headers:
        raise SystemExit(f"编号仍不自洽，日志 {final} vs 文件头 {headers}")

    PROGRESS.write_bytes(text.encode("utf-8"))
    print(f"已写回，日志编号与文件头一致：#{final[0]}")
    print("CRLF 行数：", PROGRESS.read_bytes().count(b"\r\n"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
