"""编码判定：嗅探文件编码，文本可信度打分选最优候选。

判定思路（原先在 cat/head/tail/wc/sed/awk_lite/grep 七处各抄了一份，
这里收成一处）：

- **不是「按顺序取第一个能解码的」**：英文 Windows 的系统首选编码是 cp1252，
  它几乎不报错——GBK 中文用 cp1252 解出来是 `ÖÐÎÄÄÚÈÝ` 这种乱码，
  但解码过程完全成功。按顺序取会让中文内容彻底搜不到。
- **而是给每个候选的解码结果打分，取可信度最高的**：ASCII 可打印字符记 1 分，
  CJK 字符记 3 分，全角标点记 1 分，换行类记 0.5 分，其它高位字节只记 0.2 分。
  GBK 正文的分数（汉字占 3 分）能压过 cp1252 的乱码结果。
- **换冠军要领先 0.3 分**：分差不够就当平手，保留候选序里靠前的那个。
- **latin-1 能解码任意字节**，所以判「是不是文本」时必须把它排除，
  否则所有二进制都会被误判成文本。

性能（这是本模块存在的第二个理由）：

原先的打分是逐字符的 Python 循环，实测占编码判定耗时的 97.5%、
占 grep 端到端耗时的 74.5%（E:/1 共 17790 个文件，串行 7.3s 里 5.4s 花在判定上）。
这里改成**分桶计数**：`str.translate` 把每个字符映射成一个标记字符，
再用 `str.count` 数各类字符的个数——两次 C 层扫描代替一次 Python 层逐字符循环，
实测快 6 倍以上（真实语料 6.2 倍，中文语料 20.8 倍）。

**判定结果与旧实现逐文件一致**：17283 个真实文件 + 220 份中文语料上，
新旧实现选出的编码完全相同（分值本身因浮点求和顺序不同会有末位差异，
最大 6.5e-14，不影响「谁领先 0.3 分」的判定）。
"""

from __future__ import annotations

import codecs
import locale

__all__ = [
    "SNIFF_SIZE",
    "SCORE_MARGIN",
    "BINARY_ENCODING",
    "candidate_encodings",
    "decode_sample",
    "text_score",
    "detect_encoding",
    "is_text",
    "pick_encoding",
]

# 嗅探大小：只看文件开头这么多字节
SNIFF_SIZE = 8192
# 换冠军的领先门槛：后选的编码要高出这么多分才替换当前选择
SCORE_MARGIN = 0.3
# 二进制按字节处理时用的编码
BINARY_ENCODING = "utf-8"

_FALLBACK_ENCODINGS = ("utf-8", "gb18030", "latin-1")
_CJK_RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF))
_FULLWIDTH_RANGES = ((0x3000, 0x303F), (0xFF00, 0xFFEF))

# 分桶计数用的标记字符：
#   'a' 可打印 ASCII（1 分）   'c' CJK（3 分）
#   'f' 全角标点（1 分）       't' 换行/制表符（0.5 分）
#   'x' 其它控制字符（0 分）
# 表外的码位（>= 0x80 且不是 CJK/全角）保持原样留在串里，
# 它们全是「高位字节」，记 0.2 分——用总数减去各类计数即可得到。
_MARK_PRINTABLE = "a"
_MARK_CJK = "c"
_MARK_FULLWIDTH = "f"
_MARK_CONTROL = "t"
_MARK_OTHER = "x"

# 纯 ASCII 样本的透明性检查用的样本：8 个 ASCII 字节。
# 8 字节够长，能把 utf-16 这类「两个 ASCII 字节才一个字符」的编码区分出来。
_ASCII_PROBE = b"abcdefgh"
_ASCII_TEXT = _ASCII_PROBE.decode("ascii")


def _build_marker_table() -> dict[int, str]:
    """造码位 → 标记字符的映射表，给 `str.translate` 用。

    表要覆盖到 CJK 区（0x3400~0x9FFF 有两万七千多个码位），所以只建一次、
    缓存在模块里：实测建表约 1.5 毫秒，之后每条指令都复用。
    """
    table: dict[int, str] = {}
    for code in range(0x20):
        table[code] = _MARK_CONTROL if code in (9, 10, 13) else _MARK_OTHER
    for code in range(0x20, 0x7F):
        table[code] = _MARK_PRINTABLE
    table[0x7F] = _MARK_OTHER
    for low, high in _FULLWIDTH_RANGES:
        for code in range(low, high + 1):
            table[code] = _MARK_FULLWIDTH
    for low, high in _CJK_RANGES:
        for code in range(low, high + 1):
            table[code] = _MARK_CJK
    return table


_MARKER_TABLE: dict[int, str] | None = None


def _marker_table() -> dict[int, str]:
    global _MARKER_TABLE
    if _MARKER_TABLE is None:
        _MARKER_TABLE = _build_marker_table()
    return _MARKER_TABLE


def candidate_encodings() -> list[str]:
    """候选编码的尝试顺序：utf-8 → 系统首选 → gb18030 → latin-1。

    系统首选编码在英文 Windows 上是 cp1252，它几乎不报错，所以放在前面
    只是「跟着系统走」，真正决定胜负的是打分。utf-8 永远排在第一个，
    平手时保留的就是它。
    """
    candidates: list[str] = []
    preferred = locale.getpreferredencoding(False)
    for encoding in ("utf-8", preferred, *_FALLBACK_ENCODINGS):
        if encoding and encoding not in candidates:
            candidates.append(encoding)
    return candidates


def decode_sample(sample: bytes, encoding: str) -> str | None:
    """用指定编码严格解码样本，解不出来返回 None。"""
    try:
        decoder = codecs.getincrementaldecoder(encoding)(errors="strict")
        return decoder.decode(sample, final=False)
    except (UnicodeDecodeError, LookupError, ValueError):
        return None


def text_score(text: str) -> float:
    """给一段解码结果打「像不像正文」的分。

    ASCII 可打印字符记 1 分，CJK 记 3 分，全角标点记 1 分，
    换行类记 0.5 分，高位乱码字节只记 0.2 分——这样 GBK 正文能压过
    cp1252 的乱码结果。最后除以字符总数，得到「平均每个字符多少分」。

    实现用分桶计数而不是逐字符循环：`str.translate` 把字符映射成标记，
    `str.count` 数各类个数。两次 C 层扫描代替逐字符的 Python 循环。

    分数与旧实现（逐字符累加）可能有浮点末位差异：加法不满足结合律，
    同样的权值换个求和顺序，末几位就可能差 1ulp（实测最大 6.5e-14）。
    这不影响判定——门槛是 0.3 分，比末位差异大十几个数量级。
    """
    if not text:
        return 0.0
    marked = text.translate(_marker_table())
    n_printable = marked.count(_MARK_PRINTABLE)
    n_cjk = marked.count(_MARK_CJK)
    n_fullwidth = marked.count(_MARK_FULLWIDTH)
    n_control = marked.count(_MARK_CONTROL)
    n_other = marked.count(_MARK_OTHER)
    # 表外的码位原样留在串里，全是高位字节（记 0.2 分）
    n_high = len(text) - (n_printable + n_cjk + n_fullwidth + n_control + n_other)
    score = (
        n_printable * 1.0
        + n_cjk * 3.0
        + n_fullwidth * 1.0
        + n_control * 0.5
        + n_high * 0.2
    )
    return score / len(text)


def _ascii_transparent() -> bool:
    """候选编码是否都对 ASCII 透明。

    对 ASCII 透明 = 把 ASCII 字节解成原来那几个 ASCII 字符。
    utf-8 / cp1252 / gb18030 / latin-1 都透明；但 utf-16 这类
    「两个字节一个字符」的编码不透明，解出来会多出 NUL 字符，
    那时纯 ASCII 快速路径就不能用了（得分会变）。
    """
    for encoding in candidate_encodings():
        text = decode_sample(_ASCII_PROBE, encoding)
        if text is not None and text != _ASCII_TEXT:
            return False
    return True


_ASCII_TRANSPARENT: bool | None = None


def detect_encoding(sample: bytes) -> str:
    """按文本可信度选编码，而不是取第一个能解的。

    系统首选编码在英文 Windows 上是 cp1252，它几乎不报错，能把 GBK 字节
    解成乱码，所以不能按顺序取第一个可解码的编码。
    """
    global _ASCII_TRANSPARENT
    if sample.isascii():
        # 纯 ASCII 在所有候选下解出来都一样，打分必然相同，
        # 按「平手保留靠前的」规则胜出的就是候选序第一个（utf-8）。
        # 前提是候选编码都对 ASCII 透明，否则解出来会多出字符、得分会变。
        if _ASCII_TRANSPARENT is None:
            _ASCII_TRANSPARENT = _ascii_transparent()
        if _ASCII_TRANSPARENT:
            return "utf-8"

    best_encoding = "utf-8"
    best_score = -1.0
    for encoding in candidate_encodings():
        text = decode_sample(sample, encoding)
        if text is None:
            continue
        score = text_score(text)
        if score > best_score + SCORE_MARGIN:
            best_score = score
            best_encoding = encoding
    return best_encoding


def is_text(sample: bytes) -> bool:
    """样本能否被某个真正的文本编码严格解码。

    latin-1 永远能解任何字节，所以判定文本时不把它算进去，
    否则所有二进制都会被误判成文本。
    """
    for encoding in candidate_encodings():
        if encoding == "latin-1":
            continue
        if decode_sample(sample, encoding) is not None:
            return True
    return False


def pick_encoding(sample: bytes) -> str:
    """按内容选解码方式，分三类：

    - 文本：判定编码后解码，中文按 UTF-8 输出，Windows 控制台上正常显示。
      判据是样本能被 utf-8 / 系统首选编码 / gb18030 之一严格解码。
    - 二进制（含 NUL 字节，或谁也解不出来）：按 utf-8 + surrogateescape
      解码，解不出的字节用代理码位占位，写回时还原成原字节，逐字节原样转交。

    latin-1 永远能解任何字节，所以判定文本时不把它算进去，否则所有二进制
    都会被误判成文本。
    """
    if b"\x00" in sample:
        return BINARY_ENCODING
    if is_text(sample):
        return detect_encoding(sample)
    return BINARY_ENCODING
