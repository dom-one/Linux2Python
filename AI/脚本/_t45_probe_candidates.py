"""探针：仓库实际候选编码列表下，哪些字节算「文本」。

候选里含 latin-1（永远能解），所以判定二进制时必须把 latin-1 排除。

只读：不修改仓库源码。
"""

from __future__ import annotations

import codecs
import locale
import sys

FALLBACK = ("utf-8", "gb18030", "latin-1")


def candidates() -> list[str]:
    out: list[str] = []
    preferred = locale.getpreferredencoding(False)
    for encoding in ("utf-8", preferred, *FALLBACK):
        if encoding and encoding not in out:
            out.append(encoding)
    return out


def strict_ok(data: bytes, encoding: str) -> bool:
    try:
        codecs.getincrementaldecoder(encoding)(errors="strict").decode(data, final=True)
        return True
    except (UnicodeDecodeError, LookupError, ValueError):
        return False


def main() -> int:
    real = [e for e in candidates() if e != "latin-1"]
    print("候选列表:", candidates())
    print("文本判定用:", real)
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
        "nul_mid": b"abc\x00def\n",
        "latin1_text": "caf\xe9 au lait\n".encode("latin-1"),
    }
    for label, data in samples.items():
        oks = [e for e in real if strict_ok(data, e)]
        print("%-14s 严格可解=%-22s 判定=%s" % (label, ",".join(oks) or "(无)", "文本" if oks else "二进制"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
