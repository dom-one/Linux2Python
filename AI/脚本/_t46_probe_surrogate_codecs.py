"""探针：surrogateescape 在 utf-8 / gb18030 等编码上的编解码往返。

只读：不修改仓库源码。
"""

from __future__ import annotations

import codecs
import sys


def main() -> int:
    raw = b"\x80\x81\xfe\xff abc"

    def safe(text: str) -> str:
        """控制台是 GBK，打不出代理码位，用 ascii 转义展示。"""
        return ascii(text)

    print("=== 解码侧 ===")
    for encoding in ("utf-8", "gb18030", "cp936", "latin-1"):
        text = raw.decode(encoding, errors="surrogateescape")
        print("  %-8s -> %s" % (encoding, safe(text)))

    print()
    print("=== 编码侧：代理码位能否还原成原字节 ===")
    for encoding in ("utf-8", "gb18030", "cp936", "latin-1"):
        text = raw.decode("utf-8", errors="surrogateescape")
        try:
            back = text.encode(encoding, errors="surrogateescape")
            print("  %-8s -> %r  same=%s" % (encoding, back, back == raw))
        except Exception as exc:  # noqa: BLE001
            print("  %-8s -> ERROR %s: %s" % (encoding, type(exc).__name__, exc))

    print()
    print("=== gb18030 正文的往返（文本路径）===")
    gbk = "中文内容\n".encode("gb18030")
    text = gbk.decode("gb18030", errors="surrogateescape")
    print("  解码 -> %s" % safe(text))
    print("  再按 utf-8 编码 -> %r" % text.encode("utf-8", errors="surrogateescape"))

    print()
    print("=== 混合：合法 GBK + 一个非法字节 ===")
    mixed = "中文".encode("gb18030") + b"\xff"
    t = mixed.decode("gb18030", errors="surrogateescape")
    print("  解码 -> %s" % safe(t))
    print("  utf-8 编码 -> %r" % t.encode("utf-8", errors="surrogateescape"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
