"""编码判定共享模块（w2l/encoding.py）测试。

这个模块原先在 cat/head/tail/wc/sed/awk_lite/grep 七处各抄了一份，
现在收成一处，所以测试分三组：

1. **接口契约**：候选序、严格解码、打分权重、判定结果；
2. **与旧实现等价**：用旧算法（逐字符累加）当参照物，新实现必须给出同一个分值，
   至少在浮点精度内一致——这是「提速不改行为」这条底线的护栏；
3. **单一真相源**：七个指令必须共用这一份实现，不能各留一份本地副本。
"""

import codecs
import locale

import pytest

from conftest import run_cat, run_grep, run_head, run_wc
from w2l import encoding as enc
from w2l.commands import awk_lite, cat, grep, head, sed, tail, wc

GBK_TEXT = "中文内容测试\n"
UTF8_TEXT = "中文内容测试\n"


# --------------------------------------------------------------------------
# 参照实现：改前那份逐字符打分（来自 git HEAD 的 grep.py）
# --------------------------------------------------------------------------

_CJK_RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF))


def reference_score(text: str) -> float:
    """旧实现：逐字符按权重累加，再除以字符数。"""
    if not text:
        return 0.0
    score = 0.0
    for char in text:
        code = ord(char)
        if 32 <= code < 127:
            score += 1.0
        elif any(low <= code <= high for low, high in _CJK_RANGES):
            score += 3.0
        elif 0x3000 <= code <= 0x303F or 0xFF00 <= code <= 0xFFEF:
            score += 1.0
        elif code in (9, 10, 13):
            score += 0.5
        elif code >= 0x80:
            score += 0.2
    return score / len(text)


def reference_detect(sample: bytes) -> str:
    """旧实现：给每个候选打分，领先 0.3 分才换冠军。"""
    best_encoding = "utf-8"
    best_score = -1.0
    for encoding in enc.candidate_encodings():
        text = enc.decode_sample(sample, encoding)
        if text is None:
            continue
        score = reference_score(text)
        if score > best_score + 0.3:
            best_score = score
            best_encoding = encoding
    return best_encoding


# --------------------------------------------------------------------------
# 1. 接口契约
# --------------------------------------------------------------------------


def test_candidate_encodings_starts_with_utf8_and_has_no_dupes():
    candidates = enc.candidate_encodings()
    assert candidates[0] == "utf-8"
    assert len(candidates) == len(set(candidates))
    assert "gb18030" in candidates
    assert "latin-1" in candidates


def test_decode_sample_is_strict():
    assert enc.decode_sample("中文".encode("utf-8"), "utf-8") == "中文"
    # GBK 字节不是合法 UTF-8
    assert enc.decode_sample(GBK_TEXT.encode("gb18030"), "utf-8") is None
    # 未知编码要返回 None，而不是抛异常
    assert enc.decode_sample(b"abc", "no-such-codec") is None


def test_decode_sample_latin1_accepts_any_bytes():
    payload = bytes(range(256))
    decoded = enc.decode_sample(payload, "latin-1")
    assert decoded is not None
    assert len(decoded) == 256


def test_text_score_empty_is_zero():
    assert enc.text_score("") == 0.0


@pytest.mark.parametrize(
    "text, expected",
    [
        ("abc", 1.0),          # 可打印 ASCII
        ("中", 3.0),            # CJK
        ("　", 1.0),            # 全角空格
        ("\n", 0.5),           # 换行
        ("\t", 0.5),           # 制表符
        ("\x00", 0.0),         # 其它控制字符
        ("\xff", 0.2),         # 高位乱码字节
    ],
)
def test_text_score_weights(text, expected):
    assert enc.text_score(text) == pytest.approx(expected, abs=1e-9)


def test_text_score_matches_reference_on_corpus():
    """新实现与旧实现必须给出同一个分值（浮点末位允许 1e-9 误差）。"""
    samples = [
        "",
        "plain ascii text\n",
        GBK_TEXT,
        "全角标点，标点。\n",
        "\x00\x01\x02binary\x7f\xff\n",
        "mixed 混合 ascii 123\n",
        "tab\there\r\n",
        "emoji \U0001f600 surrogate pairs",
    ]
    for text in samples:
        assert enc.text_score(text) == pytest.approx(reference_score(text), abs=1e-9)


def test_detect_encoding_ascii_returns_utf8():
    assert enc.detect_encoding(b"plain ascii\n") == "utf-8"


def test_detect_encoding_utf8_chinese():
    assert enc.detect_encoding(UTF8_TEXT.encode("utf-8")) == "utf-8"


def test_detect_encoding_gbk_roundtrips():
    """GBK 文件判出来的编码必须能把原文解回去（不限定具体编码名）。"""
    payload = GBK_TEXT.encode("gb18030")
    chosen = enc.detect_encoding(payload)
    assert payload.decode(chosen) == GBK_TEXT


def test_detect_encoding_prefers_chinese_over_mojibake():
    """GBK 正文得分必须压过「按系统首选编码解出来的乱码」。"""
    payload = GBK_TEXT.encode("gb18030")
    chosen = enc.detect_encoding(payload)
    assert chosen != "latin-1"
    assert enc.text_score(payload.decode(chosen)) > enc.text_score(
        payload.decode("latin-1")
    )


def test_detect_encoding_matches_reference():
    for payload in (
        b"plain ascii\n",
        UTF8_TEXT.encode("utf-8"),
        GBK_TEXT.encode("gb18030"),
        b"\x00\x01\x02\x03",
        bytes(range(256)),
    ):
        assert enc.detect_encoding(payload) == reference_detect(payload)


def test_detect_encoding_never_raises_on_random_bytes():
    for seed in range(64):
        payload = bytes((seed * 37 + i * 91) % 256 for i in range(256))
        enc.detect_encoding(payload)


def test_is_text_excludes_latin1():
    """latin-1 能解任何字节，所以判文本时必须排除它。

    这几个字节在 utf-8 / cp1252 / gb18030 下都解不出来，
    只有 latin-1 能解——所以判文本时排除 latin-1 才能给出 False。
    """
    assert enc.is_text(b"plain ascii\n") is True
    assert enc.is_text("中文".encode("utf-8")) is True
    assert enc.is_text(b"\x81\x20") is False


def test_pick_encoding_binary_with_nul():
    assert enc.pick_encoding(b"text\x00more") == enc.BINARY_ENCODING


def test_pick_encoding_text():
    assert enc.pick_encoding(b"plain ascii\n") == "utf-8"
    payload = GBK_TEXT.encode("gb18030")
    assert payload.decode(enc.pick_encoding(payload)) == GBK_TEXT


def test_marker_table_is_built_once():
    """映射表建一次就缓存住，不能每回打分都重建。"""
    assert enc._marker_table() is enc._marker_table()


def test_ascii_fast_path_disabled_when_encoding_not_transparent(monkeypatch):
    """候选编码对 ASCII 不透明时，纯 ASCII 快速路径必须让位给慢路径。

    utf-16-le 把两个字节当一个字符，纯 ASCII 样本解出来会多出 NUL，
    得分会变——所以快速路径的前提检查不能省。
    """
    fake = ["utf-8", "utf-16-le", "gb18030", "latin-1"]
    monkeypatch.setattr(enc, "candidate_encodings", lambda: list(fake))
    monkeypatch.setattr(enc, "_ASCII_TRANSPARENT", None)

    assert enc._ascii_transparent() is False
    # 慢路径给出的结果要和参照实现一致
    assert enc.detect_encoding(b"plain ascii\n") == reference_detect(b"plain ascii\n")


def test_ascii_fast_path_used_when_transparent(monkeypatch):
    """候选都透明时走快速路径，直接返回 utf-8。"""
    monkeypatch.setattr(
        enc, "candidate_encodings", lambda: ["utf-8", "gb18030", "latin-1"]
    )
    monkeypatch.setattr(enc, "_ASCII_TRANSPARENT", None)

    assert enc._ascii_transparent() is True
    assert enc.detect_encoding(b"plain ascii\n") == "utf-8"


# --------------------------------------------------------------------------
# 2. 单一真相源：七个指令必须共用这一份实现
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module",
    [grep, cat, head, tail, wc, awk_lite],
)
def test_commands_share_one_encoding_implementation(module):
    """指令里的编码函数必须是共享模块的那一份，不能有本地副本。"""
    for name in ("_detect_encoding", "_text_score", "_candidate_encodings"):
        local = getattr(module, name, None)
        if local is None:
            continue
        assert local is getattr(enc, name.removeprefix("_")), name


def test_sed_keeps_its_own_nul_rule():
    """sed 的判定多一条「含 NUL 一律按 latin-1」，与其它指令不同，保留本地包装。"""
    assert sed._detect_encoding is not enc.detect_encoding
    assert sed._detect_text_encoding is enc.detect_encoding
    assert sed._detect_encoding(b"text\x00more") == "latin-1"
    assert sed._detect_encoding(b"plain ascii\n") == "utf-8"


# --------------------------------------------------------------------------
# 3. 指令侧回归：GBK 文件在各指令里都不能乱码
# --------------------------------------------------------------------------


def test_cat_reads_gbk_file(tmp_path):
    target = tmp_path / "gbk.txt"
    target.write_bytes(GBK_TEXT.encode("gb18030"))
    code, out, err = run_cat([str(target)])
    assert code == 0
    assert out == GBK_TEXT
    assert err == ""


def test_head_reads_gbk_file(tmp_path):
    target = tmp_path / "gbk.txt"
    target.write_bytes(GBK_TEXT.encode("gb18030"))
    code, out, err = run_head(["-n", "1", str(target)])
    assert code == 0
    assert out == GBK_TEXT
    assert err == ""


def test_grep_finds_chinese_in_gbk_file(tmp_path):
    target = tmp_path / "gbk.log"
    target.write_bytes(("INFO 开始\nERROR 失败\n").encode("gb18030"))
    code, out, err = run_grep(["失败", str(target)])
    assert code == 0
    assert out == "ERROR 失败\n"
    assert err == ""


def test_wc_counts_gbk_characters(tmp_path):
    target = tmp_path / "gbk.txt"
    target.write_bytes(GBK_TEXT.encode("gb18030"))
    code, out, err = run_wc(["-m", str(target)])
    assert code == 0
    assert out.split()[0] == str(len(GBK_TEXT))
    assert err == ""


def test_latin1_fallback_is_not_used_for_text():
    """判定文本时不能把 latin-1 算进去，否则二进制会被当成文本。"""
    candidates = enc.candidate_encodings()
    assert "latin-1" in candidates
    assert enc.is_text(b"\xff\xfe\x00\x01") is False


def test_preferred_encoding_is_in_candidates():
    preferred = locale.getpreferredencoding(False)
    assert preferred in enc.candidate_encodings()
    assert codecs.lookup(preferred) is not None
