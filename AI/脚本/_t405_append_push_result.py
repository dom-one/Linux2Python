"""给 tick #10 的日志补一行：推送最终成功了。

进度文件只能追加，所以不改写已经写下的「推送未成功」那一行，
只在后面补一条最终结果，让下一个 tick 读到的是准确状态。

用法:
    python AI/脚本/_t405_append_push_result.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROGRESS = ROOT / "AI" / "阅读进度.md"

LINE = (
    "- **推送最终成功**（2026-11-15 02:19 前后）：上面记的 4 次失败是网络抖动，"
    "第 5 次 `git push origin main` 成功，输出 `4b3fe03..ee455d7  main -> main`——"
    "tick #9 遗留的三个提交连同本轮三个提交（共 5 个）一起推上去了，远程与本地已同步，"
    "下一个 tick 不用再补推。教训：网络不通时先确认是网络层断还是凭据问题"
    "（HTTPS HEAD 探 github.com 也不通就是网络层），凭据问题会先弹登录框；"
    "本地提交不回滚，隔一会儿重试大概率能推上去。\n"
)


def main() -> int:
    with PROGRESS.open("ab") as handle:
        handle.write(LINE.encode("utf-8"))
    print("已补记推送结果到", PROGRESS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
