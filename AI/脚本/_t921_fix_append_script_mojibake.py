"""修掉 _t919_append_tick11.py 里的两处 U+FFFD 坏字符（写盘时编码转换吃掉的）。

「结果是错的」→「结果是??的」，「不加」→「不??」。
两处都用上下文定位，避免误伤。

用法:
    python AI/脚本/_t921_fix_append_script_mojibake.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "_t919_append_tick11.py"

BAD = "\ufffd\ufffd"
FIXES = [
    ("结果是" + BAD + "的", "结果是错的"),
    ("不" + BAD + "」", "不加」"),
]


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    original = text

    for broken, fixed in FIXES:
        count = text.count(broken)
        print("  %r 出现 %d 处" % (broken, count))
        if count != 1:
            print("    预期恰好 1 处，实际 %d 处，不动" % count)
            return 1
        text = text.replace(broken, fixed)

    assert "\ufffd" not in text, "还有没修掉的坏字符"

    with open(TARGET, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    reread = TARGET.read_text(encoding="utf-8")
    assert reread == text, "回读与写入不一致"

    print("已修好 %s，字节数 %d -> %d" % (
        TARGET.name,
        len(original.encode("utf-8")), len(text.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
