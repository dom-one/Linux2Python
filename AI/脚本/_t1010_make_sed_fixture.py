"""造 sed 教程用的固定夹具，落在 AI/数据/sed_demo/（gitignore 目录）。

为什么要固定夹具：
预期输出不能凭印象写。源码当示例的预期输出必然随源码改动过期，
用一次性生成的固定夹具，预期输出从此不会过期。

每行内容刻意唯一（u.txt 的 L1/L2X/...），这样从输出能直接反推
范围地址覆盖了源文件的哪几行，不用猜。

夹具每次全量重建（先删后建），保证目录状态不被上一轮操作带偏。
"""

from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "sed_demo"

# 文件名 -> 字节内容
FILES: dict[str, bytes] = {
    # 五行英文，每行一个单词
    "a.txt": b"alpha\nbravo\ncharlie\ndelta\necho\n",
    # 带序号的行，用来演示 = 与地址
    "num.txt": b"1 one\n2 two\n3 three\n4 four\n5 five\n",
    # 每行唯一，含 X 的行是第 2/4/6 行 —— 范围地址覆盖了哪几行一眼可见
    "u.txt": b"L1\nL2X\nL3\nL4X\nL5\nL6X\nL7\nL8\n",
    # CRLF 行尾
    "crlf.txt": b"one\r\ntwo\r\nthree\r\n",
    # 末行没有换行符
    "nonl.txt": b"no trailing newline",
    # 中间有空行
    "blank.txt": b"first\n\nthird\n",
    # 两个字面的星号，用来演示 BRE 里锚点后跟 * 的处理
    "star.txt": b"a*b\nplain\n*lead\n",
    # 两个文件，用来看 -s 与默认拼流的差别
    "m1.txt": b"1 alpha\n",
    "m2.txt": b"2 alpha\n",
    # NUL 分隔，给 -z 用
    "nul.txt": b"aaa\x00bbb\x00ccc\x00",
    # GBK 编码的中文，给编码判定用
    "gbk.txt": "第一行\n第二行\n".encode("gbk"),
    # 原地修改用的两份副本：ip.txt 演示 --in-place，ip2.txt 演示 --in-place-suffix
    "ip.txt": b"alpha\nbravo\ncharlie\ndelta\necho\n",
    "ip2.txt": b"alpha\nbravo\ncharlie\ndelta\necho\n",
    # 脚本文件：演示 -f 与标签跳转
    "jump.sed": b"/bravo/{\ns/a/X/\nt end\n}\np\n:end\n",
}


def build() -> Path:
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)
    for name, payload in FILES.items():
        (DATA / name).write_bytes(payload)
    return DATA


def main() -> None:
    data = build()
    print("已生成 AI/数据/sed_demo/（%d 个文件）" % len(FILES))
    for name in sorted(FILES):
        path = data / name
        print("  %-12s %4d 字节" % (name, path.stat().st_size))


if __name__ == "__main__":
    main()
