"""w2l/jsonout.py 的测试。

JSON 输出口径是**跨指令共用**的：输出长什么样、错误走哪、中文怎么转义。
口径一旦各指令各写一份就会漂，所以判据定死在这里。
"""

import io
import json
import stat
from pathlib import Path

import pytest

from w2l import jsonout
from w2l.context import RunContext


def _ctx():
    out, err = io.StringIO(), io.StringIO()
    return RunContext(cwd=Path.cwd(), stdout=out, stderr=err, stdin=io.StringIO()), out, err


# ---------- dumps ----------


def test_dumps_is_valid_json():
    text = jsonout.dumps({"a": 1, "b": [2, 3]})
    assert json.loads(text) == {"a": 1, "b": [2, 3]}


def test_dumps_ends_with_newline():
    text = jsonout.dumps({"a": 1})
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


def test_dumps_keeps_chinese_readable():
    """中文不能被转义成 \\uXXXX，否则机器读得懂、人读不动。"""
    text = jsonout.dumps({"名": "中文"})
    assert "中文" in text
    assert "\\u" not in text


def test_dumps_uses_two_space_indent():
    text = jsonout.dumps({"a": {"b": 1}})
    assert '\n  "a"' in text


def test_dumps_keeps_insertion_order():
    text = jsonout.dumps({"z": 1, "a": 2})
    assert text.index('"z"') < text.index('"a"')


def test_dumps_rejects_nan():
    """NaN / Infinity 不是合法 JSON，放出去会污染下游的解析器。"""
    with pytest.raises(ValueError):
        jsonout.dumps({"x": float("nan")})


# ---------- write ----------


def test_write_goes_to_stdout():
    ctx, out, err = _ctx()
    jsonout.write(ctx, {"command": "ls", "entries": []})
    assert json.loads(out.getvalue()) == {"command": "ls", "entries": []}
    assert err.getvalue() == ""


# ---------- type_name ----------


def test_type_name_regular_file():
    assert jsonout.type_name(stat.S_IFREG | 0o644) == "file"


def test_type_name_directory():
    assert jsonout.type_name(stat.S_IFDIR | 0o755) == "directory"


def test_type_name_symlink():
    assert jsonout.type_name(stat.S_IFLNK | 0o777) == "symlink"


def test_type_name_fifo():
    assert jsonout.type_name(stat.S_IFIFO | 0o644) == "fifo"


def test_type_name_unknown_is_other():
    assert jsonout.type_name(0) == "other"
