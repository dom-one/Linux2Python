#!/usr/bin/env python
"""把 teach/28 教程里的命令块改成项目约定的写法。

用法：
    python AI/脚本/_t1307_fix_teach28_paths.py

项目约定（与 teach/27 一致）：
- 每个 ```bash 块第一行是 `cd E:\\1\\NULL\\Windows-to-Linux`
- 路径写全成仓库根相对路径（`AI/数据/awk_demo/app.log`）
- 核对器 `AI/脚本/_t12_verify_teach.py` 会剥掉 cd 行、在仓库根跑其余命令

改动只发生在 ```bash 围栏块内，正文与表格里的文件名不动。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DOC = ROOT / "teach" / "28-w2l-commands-awk_lite.py-字段投影与解析边界.md"

CD_LINE = r"cd E:\1\NULL\Windows-to-Linux"

FIXTURES = [
    "app.log",
    "two.log",
    "access.csv",
    "semi.log",
    "gap.log",
    "blank.log",
    "nonl.log",
    "gbk.log",
    "multi.txt",
    "nope.log",
]

FENCE = re.compile(r"```bash\n(.*?)```", re.DOTALL)


def transform_line(line: str) -> str:
    out = line
    out = out.replace("python ../../main.py", "python main.py")
    for name in FIXTURES:
        # 只替换命令行里的独立文件名（前面是空格或引号，后面是空格或行尾）
        out = re.sub(
            rf"(?<![\w/.-]){re.escape(name)}(?![\w.-])",
            f"AI/数据/awk_demo/{name}",
            out,
        )
    return out


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    before = text

    def repl(match: re.Match[str]) -> str:
        body = match.group(1)
        lines = [ln for ln in body.strip().splitlines() if ln.strip()]
        new_lines = [CD_LINE] + [transform_line(ln) for ln in lines]
        return "```bash\n" + "\n".join(new_lines) + "\n```"

    text = FENCE.sub(repl, text)

    # 正文里那句「在 AI/数据/awk_demo 目录下跑」要跟着改
    text = text.replace(
        "下面的命令都在 `AI/数据/awk_demo/` 目录下跑。",
        "下面的命令都在仓库根目录（`E:\\1\\NULL\\Windows-to-Linux`）下跑，"
        "夹具路径写全成 `AI/数据/awk_demo/...`，这样每个块都能单独复制执行。",
    )

    # 文件不存在的示例，错误信息里带的是完整路径，预期输出要跟着改
    text = text.replace(
        "nope.log: No such file or directory\n```",
        "AI/数据/awk_demo/nope.log: No such file or directory\n```",
    )

    if text == before:
        print("没有改动，请检查脚本")
        return 1

    DOC.write_text(text, encoding="utf-8")
    print(f"已改写 {DOC}")
    print(f"bash 块数：{len(FENCE.findall(text))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
