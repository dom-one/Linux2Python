"""修 teach/21 里最后一处正文断言：0.9583 不是「所有纯 ASCII 文件」的分数。

用法:
    python AI/脚本/_t106_fix_teach21_score.py

问题:
    草稿写「纯 ASCII 文件用三种编码解出来分数完全一样（都是 0.9583）」。
    0.9583 是 'hello world\\n' 这一个样本的得分，不是纯 ASCII 文本的通值：
        'hello world\\n'         -> 0.958333
        'hello\\n'               -> 0.916667
        'abc\\n'                 -> 0.875000
        'plain ascii text\\n'    -> 0.970588
    得分 = 可打印字符数 / 总字符数（换行算 0.5 分），所以每个文件都不一样。

    真正要说的是「三种编码解同一个样本，分数完全一样」——这一点对所有样本
    都成立（纯 ASCII 在三种编码下解出来是同一串字符），门槛 0.3 挡住了
    后来的平分替换。

改法:
    改成给出样本与得分，并说明得分随内容变化、但三种编码之间始终相等。
    顺带补上「三种编码解同一字节串得到的是同一串字符」这个更本质的理由。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "teach" / "21-w2l-commands-cat.py-编码判定与显示记号.md"
PREVIEW = DOC.with_suffix(".md.preview")

OLD = (
    "`_SCORE_MARGIN = 0.3` 是「换冠军的门槛」：后来的编码必须比当前最优高出 0.3 分才能取代它。"
    "纯 ASCII 文件用三种编码解出来分数完全一样（都是 0.9583），门槛挡住了后面来的一次次平分替换，"
    "最终留在候选表第一个 `utf-8`。"
)

NEW = (
    "`_SCORE_MARGIN = 0.3` 是「换冠军的门槛」：后来的编码必须比当前最优高出 0.3 分才能取代它。\n"
    "\n"
    "纯 ASCII 文件用三种编码解出来，分数**完全一样**——因为三种编码解同一串 ASCII 字节，"
    "得到的是同一串字符。门槛挡住了后面来的一次次平分替换，最终留在候选表第一个 `utf-8`。\n"
    "\n"
    "这里要说清一件事：**分数不是纯 ASCII 文本的通值，它随内容变化**。"
    "得分是「可打印字符 1 分 + 换行 0.5 分」再除以总字符数，所以每个文件都不一样：\n"
    "\n"
    "| 样本 | 三种编码的得分 |\n"
    "|---|---|\n"
    "| `hello world\\n` | 0.958333 |\n"
    "| `hello\\n` | 0.916667 |\n"
    "| `abc\\n` | 0.875000 |\n"
    "| `plain ascii text\\n` | 0.970588 |\n"
    "\n"
    "四行里三种编码的分数都相同——这才是「纯 ASCII 不区分编码」的真正含义。"
    "而 GBK 正文之所以能被 utf-8 之外的编码压过，是因为解成乱码时每个高位字节只记 0.2 分，"
    "分数被拉低到和正经正文不在一个量级。"
)


def main() -> int:
    apply = "--apply" in sys.argv
    original = DOC.read_bytes()
    text = original.decode("utf-8")

    if text.count(OLD) != 1:
        print("中止：待改段落命中 %d 次，期望 1 次" % text.count(OLD))
        return 1
    text = text.replace(OLD, NEW, 1)

    if b"\r\n" in original:
        print("中止：原文件是 CRLF")
        return 1

    PREVIEW.write_bytes(text.encode("utf-8"))
    print()
    print("预览已写到 %s" % PREVIEW)
    print("长度：原 %d 字节 -> 新 %d 字节" % (len(original), len(text.encode("utf-8"))))
    if apply:
        os.replace(PREVIEW, DOC)
        print("已覆盖原文件 %s" % DOC)
    else:
        print("加 --apply 才覆盖原文件")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
