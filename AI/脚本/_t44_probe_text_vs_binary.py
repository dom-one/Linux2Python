"""探针：哪些字节序列能被 utf-8 / cp1252 / gb18030 严格解码。

用途：判定「文本 vs 二进制」的边界——严格解不出来的就是二进制，
应逐字节原样转交，不做编码转换。

只读：不修改仓库源码。
"""

from __future__ import annotations

import codecs
import locale
import sys

CANDIDATES = ("utf-8", "gb18030", "cp1252", "latin-1")


def strict_ok(data: bytes, encoding: str) -> bool:
    try:
        codecs.getincrementaldecoder(encoding)(errors="strict").decode(data, final=True)
        return True
    except (UnicodeDecodeError, LookupError, ValueError):
        return False


def main() -> int:
    print("preferred encoding:", locale.getpreferredencoding(False))
    print()
    samples = {
        "ascii": b"hello world\n",
        "utf8_cn": "中文内容\n".encode("utf-8"),
        "gbk_cn": "中文内容\n".encode("gb18030"),
        "cp1252_text": "café au lait\n".encode("cp1252"),
        "high_bin": b"\x80\x81\xfe\xff\n",
        "one_high": b"a\x80b\n",
        "all_bytes": bytes(range(256)),
        "png_head": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
        "latin1_high": b"\xe9\xe8\xea\n",
    }
    for label, data in samples.items():
        marks = []
        for encoding in CANDIDATES:
            marks.append("%s=%s" % (encoding, "Y" if strict_ok(data, encoding) else "n"))
        print("%-14s %s" % (label, "  ".join(marks)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
