"""看一下过滤器索引里「Linux命令」来源的历史登记条目，照着已有格式登记本轮产物。

只读，不写。
"""

from __future__ import annotations

import json
from pathlib import Path

INDEX = Path(r"E:\1data\过滤器\索引\索引.jsonl")


def main() -> int:
    if not INDEX.exists():
        print(f"索引不存在: {INDEX}")
        return 1
    rows = []
    with INDEX.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    picked = [row for row in rows if row.get("来源") == "Linux命令"]
    print(f"总条目={len(rows)} 其中 Linux命令={len(picked)}")
    for row in picked[-12:]:
        print(json.dumps(row, ensure_ascii=False))
    print("--- 最后 3 条（任意来源）---")
    for row in rows[-3:]:
        print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
