"""生成 GBK 演示文件，供 teach/23 的第 16 步使用。

用法:
    python AI/脚本/_t606_make_tail_gbk_demo.py

产出:
    AI/数据/tail_gbk_demo.txt —— GBK 编码，3 行中文

为什么单独写个脚本:
    GBK 内容的字节没法直接用 printf 在 bash 里拼（终端编码是 UTF-8，
    写出去的已经是 UTF-8 字节），必须用 Python 按 gb18030 编码落盘。
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LINES = [
    "日志第一行：程序启动",
    "日志第二行：开始读取配置",
    "日志第三行：磁盘写入完成",
]


def main() -> int:
    outdir = os.path.join(ROOT, "AI", "数据")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "tail_gbk_demo.txt")
    data = ("\n".join(LINES) + "\n").encode("gb18030")
    with open(path, "wb") as fh:
        fh.write(data)
    print("已生成 AI/数据/tail_gbk_demo.txt（GBK 编码，%d 行）" % len(LINES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
