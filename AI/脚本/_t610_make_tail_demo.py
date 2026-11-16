"""生成 tail 教程用的固定演示夹具。

用法:
    python AI/脚本/_t610_make_tail_demo.py

产出（全部落在 AI/数据/tail_demo/，该目录在 .gitignore 里，不进仓库）:
    a.txt        5 行，l1..l5，每行以 LF 结尾
    b.txt        1 行，x
    nonl.txt     3 行，末行没有换行
    crlf.txt     3 行，CRLF 结尾
    zeros.bin    3 段，NUL 分隔
    mixed.txt    前两行 ASCII，末行 GBK 中文

为什么不用 w2l/registry.py 当示例:
    源码会变。registry.py 一改，教程里写死的「预期输出」就全过期了
    （teach/20 那批过期点就是这么来的）。夹具内容由本脚本固定，
    预期输出从此不会过期。
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEMO_DIR = os.path.join(ROOT, "AI", "数据", "tail_demo")

FILES = {
    "a.txt": b"l1\nl2\nl3\nl4\nl5\n",
    "b.txt": b"x\n",
    "nonl.txt": b"p1\np2\np3",
    "crlf.txt": b"c1\r\nc2\r\nc3\r\n",
    "zeros.bin": b"z1\x00z2\x00z3\x00",
    "big.txt": b"X" * 2000,
    "many.txt": b"".join(b"n%03d\n" % i for i in range(600)),
}


def main() -> int:
    os.makedirs(DEMO_DIR, exist_ok=True)
    for name, data in FILES.items():
        with open(os.path.join(DEMO_DIR, name), "wb") as fh:
            fh.write(data)
    # 混合编码：前两行纯 ASCII，末行是 GBK 中文
    with open(os.path.join(DEMO_DIR, "mixed.txt"), "wb") as fh:
        fh.write(b"ascii one\nascii two\n")
        fh.write("中文末行\n".encode("gb18030"))
    print("已生成 AI/数据/tail_demo/（%d 个夹具）" % (len(FILES) + 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
