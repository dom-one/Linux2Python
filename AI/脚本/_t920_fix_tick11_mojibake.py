"""修掉 tick #11 日志里的两处 U+FFFD 坏字符。

坏字符是「结」与「加」——写脚本时编码转换吃掉的，肉眼看不出来。
「结果是错的」被写成「结果是<两个 U+FFFD>的」，「不加」被写成「不<两个 U+FFFD>」。

做法：按上下文定位并替换掉那两串坏字节，不重写整个 tick 段落。

注意：本文件的 docstring 里刻意不写真正的 U+FFFD 字符——
写进去的文件自己就会带坏字符，脚本里用 "\ufffd\ufffd" 转义写法代替。

用法:
    python AI/脚本/_t920_fix_tick11_mojibake.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PROGRESS = ROOT / "AI" / "教程进度.md"

BAD = "\ufffd\ufffd"

# (坏字符前后的上下文, 正确的整串)
FIXES = [
    ("结果是" + BAD + "的", "结果是错的"),
    ("不" + BAD + "」", "不加」"),
]


def main() -> int:
    text = PROGRESS.read_text(encoding="utf-8")
    original = text

    for broken, fixed in FIXES:
        count = text.count(broken)
        print("  %r 出现 %d 处" % (broken, count))
        if count != 1:
            print("    预期恰好 1 处，实际 %d 处，不动" % count)
            return 1
        text = text.replace(broken, fixed)

    assert BAD not in text, "还有没修掉的坏字符"
    assert "\ufffd" not in text, "还有单字节的坏字符"

    with open(PROGRESS, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    reread = PROGRESS.read_text(encoding="utf-8")
    assert reread == text, "回读与写入不一致"
    assert b"\r\n" not in PROGRESS.read_bytes(), "文件里混进了 CRLF"

    print("已修好，字节数 %d -> %d" % (
        len(original.encode("utf-8")), len(text.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
