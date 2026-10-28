import io
import locale

import pytest

from conftest import _Tty, run_grep
from w2l.cli import main
from w2l.commands.grep import build_parser, grep
from w2l.context import RunContext
from w2l.errors import UsageError


def test_basic_match(sample_tree):
    code, out, err = run_grep(["ERROR", str(sample_tree / "app.log")])
    assert code == 0
    assert out == "ERROR failed\nERROR again\n"
    assert err == ""


def test_no_match_returns_one(sample_tree):
    code, out, _ = run_grep(["nothing", str(sample_tree / "app.log")])
    assert code == 1
    assert out == ""


def test_ignore_case(sample_tree):
    code, out, _ = run_grep(["-i", "beta", str(sample_tree / "notes.txt")])
    assert code == 0
    assert out == "Beta\n"


def test_invert_match(sample_tree):
    code, out, _ = run_grep(["-v", "ERROR", str(sample_tree / "app.log")])
    assert code == 0
    assert out == "INFO start\nwarn retry\n"


def test_line_number(sample_tree):
    code, out, _ = run_grep(["-n", "ERROR", str(sample_tree / "app.log")])
    assert code == 0
    assert out == "2:ERROR failed\n4:ERROR again\n"


def test_recursive_with_prefix(sample_tree):
    code, out, _ = run_grep(["-ri", "error", str(sample_tree)])
    assert code == 0
    assert str(sample_tree / "app.log") in out
    assert str(sample_tree / "sub" / "deep.txt") in out
    assert "error in deep" in out


def test_directory_without_recursive_is_usage_error(sample_tree):
    namespace = build_parser().parse_args(["error", str(sample_tree), str(sample_tree / "app.log")])
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(cwd=sample_tree, stdout=out, stderr=err, stdin=_Tty())
    with pytest.raises(UsageError):
        grep(namespace, ctx)
    assert out.getvalue() == ""


def test_trailing_backslash_is_usage_error(sample_tree):
    namespace = build_parser().parse_args(["foo\\", str(sample_tree / "app.log")])
    ctx = RunContext(cwd=sample_tree, stdout=io.StringIO(), stderr=io.StringIO(), stdin=_Tty())
    with pytest.raises(UsageError):
        grep(namespace, ctx)


def test_extended_regexp(sample_tree):
    code, out, _ = run_grep(["-E", "ERROR|warn", str(sample_tree / "app.log")])
    assert code == 0
    assert out == "ERROR failed\nwarn retry\nERROR again\n"


def test_basic_regexp_treats_pipe_as_literal(sample_tree):
    code, out, _ = run_grep(["ERROR|warn", str(sample_tree / "app.log")])
    assert code == 1
    assert out == ""


def test_basic_regexp_escaped_alternation(sample_tree):
    code, out, _ = run_grep([r"ERROR\|warn", str(sample_tree / "app.log")])
    assert code == 0
    assert out == "ERROR failed\nwarn retry\nERROR again\n"


def test_basic_regexp_escaped_group(sample_tree):
    code, out, _ = run_grep([r"\(ERROR\|warn\) failed", str(sample_tree / "app.log")])
    assert code == 0
    assert out == "ERROR failed\n"


def test_word_regexp(sample_tree):
    target = sample_tree / "words.txt"
    target.write_text("cat\nconcat\nthe cat sat\n", encoding="utf-8")
    code, out, _ = run_grep(["-w", "cat", str(target)])
    assert code == 0
    assert out == "cat\nthe cat sat\n"


def test_count(sample_tree):
    code, out, _ = run_grep(["-c", "ERROR", str(sample_tree / "app.log")])
    assert code == 0
    assert out == "2\n"


def test_count_multiple_files_prefixed(sample_tree):
    code, out, _ = run_grep(["-c", "e", str(sample_tree / "app.log"), str(sample_tree / "notes.txt")])
    assert code == 0
    assert f"{sample_tree / 'app.log'}:2" in out
    assert f"{sample_tree / 'notes.txt'}:1" in out


def test_files_with_matches(sample_tree):
    code, out, _ = run_grep(["-l", "ERROR", str(sample_tree / "app.log"), str(sample_tree / "notes.txt")])
    assert code == 0
    assert out == f"{sample_tree / 'app.log'}\n"


def test_only_matching(sample_tree):
    code, out, _ = run_grep(["-o", "-E", "E[a-zA-Z]+", str(sample_tree / "app.log")])
    assert code == 0
    assert out == "ERROR\nERROR\n"


def test_basic_regexp_treats_plus_as_literal(sample_tree):
    code, out, _ = run_grep(["E[a-z]+", str(sample_tree / "app.log")])
    assert code == 1
    assert out == ""


def test_only_matching_with_line_number(sample_tree):
    code, out, _ = run_grep(["-on", "ERROR", str(sample_tree / "app.log")])
    assert code == 0
    assert out == "2:ERROR\n4:ERROR\n"


def test_missing_file_reports_error(tmp_path):
    code, out, err = run_grep(["x", str(tmp_path / "nope.txt")])
    assert code == 2
    assert out == ""
    assert "nope.txt" in err


def test_binary_file_message(tmp_path):
    target = tmp_path / "bin.dat"
    target.write_bytes(b"\x00\x01error\x00tail\n")
    code, out, _ = run_grep(["error", str(target)])
    assert code == 0
    assert out.startswith("Binary file")


def test_binary_file_listed_with_l(tmp_path):
    target = tmp_path / "bin.dat"
    target.write_bytes(b"\x00\x01error\x00\n")
    code, out, _ = run_grep(["-l", "error", str(target)])
    assert code == 0
    assert out == f"{target}\n"


def test_stdin_search():
    code, out, _ = run_grep(["warn"], stdin_text="ok\nwarn here\n")
    assert code == 0
    assert out == "warn here\n"


def test_stdin_count():
    code, out, _ = run_grep(["-c", "warn"], stdin_text="ok\nwarn here\n")
    assert code == 0
    assert out == "1\n"


def test_no_path_reads_stdin_like_gnu_grep():
    namespace = build_parser().parse_args(["warn"])
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(cwd=None, stdout=out, stderr=err, stdin=io.StringIO("warn here\n"))
    code = grep(namespace, ctx)
    assert code == 0
    assert out.getvalue() == "warn here\n"


def test_no_path_on_terminal_prints_hint():
    namespace = build_parser().parse_args(["warn"])
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(cwd=None, stdout=out, stderr=err, stdin=_Tty())
    code = grep(namespace, ctx)
    assert code == 1
    assert out.getvalue() == ""
    assert "标准输入" in err.getvalue()


def test_crlf_line_endings(tmp_path):
    target = tmp_path / "crlf.txt"
    target.write_bytes(b"alpha\r\nbeta\r\n")
    code, out, _ = run_grep(["beta", str(target)])
    assert code == 0
    assert out == "beta\n"


def test_gbk_encoding(tmp_path):
    target = tmp_path / "gbk.txt"
    target.write_bytes("中文内容\n".encode("gbk"))
    code, out, _ = run_grep(["中文", str(target)])
    assert code == 0
    assert out == "中文内容\n"


def test_gbk_encoding_on_non_chinese_locale(tmp_path, monkeypatch):
    monkeypatch.setattr(locale, "getpreferredencoding", lambda do_setlocale=True: "cp1252")
    target = tmp_path / "gbk.txt"
    target.write_bytes("中文内容\n".encode("gbk"))
    code, out, _ = run_grep(["中文", str(target)])
    assert code == 0
    assert out == "中文内容\n"


def test_utf8_file_on_non_chinese_locale(tmp_path, monkeypatch):
    monkeypatch.setattr(locale, "getpreferredencoding", lambda do_setlocale=True: "cp1252")
    target = tmp_path / "utf8.txt"
    target.write_text("中文内容\n", encoding="utf-8")
    code, out, _ = run_grep(["中文", str(target)])
    assert code == 0
    assert out == "中文内容\n"


def test_latin1_file_stays_readable(tmp_path, monkeypatch):
    monkeypatch.setattr(locale, "getpreferredencoding", lambda do_setlocale=True: "cp1252")
    target = tmp_path / "latin.txt"
    target.write_bytes("café\nplain\n".encode("cp1252"))
    code, out, _ = run_grep(["café", str(target)])
    assert code == 0
    assert out == "café\n"


def test_invalid_regex_is_usage_error(sample_tree):
    namespace = build_parser().parse_args(["[unclosed", str(sample_tree / "app.log")])
    ctx = RunContext(cwd=sample_tree, stdout=io.StringIO(), stderr=io.StringIO(), stdin=_Tty())
    with pytest.raises(UsageError):
        grep(namespace, ctx)


def test_cli_dispatch_returns_match_code(sample_tree, capsys):
    code = main(["grep", "ERROR", str(sample_tree / "app.log")])
    assert code == 0
    assert "ERROR failed" in capsys.readouterr().out


def test_cli_unknown_command(capsys):
    code = main(["nope"])
    assert code == 2
    assert "未知指令" in capsys.readouterr().err


def test_cli_help_lists_commands(capsys):
    code = main(["--help"])
    assert code == 0
    assert "grep" in capsys.readouterr().out
