"""向进度文件追加一段 tick 日志。

字节追加，历史不覆盖；tick 号在写入前一刻现算。

用法:
    python AI/脚本/_t11_progress.py --进度 AI/阅读进度.md --主题 "实现 ls 指令" \
        --理由 "命令队列下一个" --产出 w2l/commands/ls.py --收获 "..." --负面 "..."
"""

import argparse
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TICK_PATTERN = re.compile(r"tick\s*#(\d+)", re.IGNORECASE)


def next_tick(path):
    highest = 0
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for match in TICK_PATTERN.finditer(handle.read()):
                highest = max(highest, int(match.group(1)))
    return highest + 1


def build_block(tick, theme, reason, products, gain, negative, pending):
    stamp = time.strftime("%Y-%m-%d %H:%M")
    lines = [
        "",
        "#### tick #%d（%s）— %s" % (tick, stamp, theme),
        "- **选本理由**：%s" % reason,
        "- **产出**：%s" % products,
        "- **关键收获**：%s" % gain,
        "- **负面结果**：%s" % negative,
    ]
    if pending:
        lines.append("- **剩余待决**：%s" % pending)
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="追加 tick 日志")
    parser.add_argument("--进度", required=True)
    parser.add_argument("--主题", required=True)
    parser.add_argument("--理由", default="")
    parser.add_argument("--产出", default="")
    parser.add_argument("--收获", default="")
    parser.add_argument("--负面", default="")
    parser.add_argument("--剩余", default="")
    args = parser.parse_args()

    path = args.进度
    if not os.path.isabs(path):
        path = os.path.join(ROOT, path.replace("/", os.sep))

    tick = next_tick(path)
    block = build_block(tick, args.主题, args.理由, args.产出,
                        args.收获, args.负面, args.剩余)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "ab") as handle:
        handle.write(block.encode("utf-8"))
    print("tick #%d 已追加到 %s" % (tick, path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
