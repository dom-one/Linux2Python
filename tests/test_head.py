"""head 指令测试。

对照的是 Git Bash 里 GNU coreutils 8.32 的 head 实测输出：
默认前 10 行、-n 指定行数、-c 指定字节数（两个都给时后写的生效）、
计数带正负号（+N 等价 N，-N 表示除末 N 行之外全要，0 与 -0 含义不同）、
乘数后缀（b=512、k/K=1024、kB=1000、KiB=K）、多文件的 `==> 文件名 <==`
标题与标题前的空行、-q 不打标题、-v 强制打标题（两者同开时后写的生效）、
打不开的文件不打标题只报错、- 表示标准输入、不给操作数读标准输入、
-z 用 NUL 当行分隔符、CRLF 原样转交、末行无换行不补换行。
"""

import io

import pytest

from conftest import build_head_namespace, run_head
from w2l.commands.head import head
from w2l.context import RunContext
from w2l.errors import UsageError


@pytest.fixture
def head_tree(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"l1\nl2\nl3\nl4\nl5\n")
    (tmp_path / "b.txt").write_bytes(b"x\n")
    (tmp_path / "nonl.txt").write_bytes(b"p1\np2\np3")
    (tmp_path / "empty.txt").write_bytes(b"")
    (tmp_path / "blank.txt").write_bytes(b"b1\n\nb3\n")
    (tmp_path / "crlf.txt").write_bytes(b"c1\r\nc2\r\nc3\r\n")
    (tmp_path / "zeros.bin").write_bytes(b"z1\x00z2\x00z3\x00")
    (tmp_path / "bin.dat").write_bytes(bytes(range(256)))
    sub = tmp_path / "sub"
    sub.mkdir()
    return tmp_path


# ---------- 正常路径 ----------


def test_prints_first_ten_lines_by_default(head_tree):
    code, out, err = run_head([str(head_tree / "a.txt")])
    assert code == 0
    assert out == "l1\nl2\nl3\nl4\nl5\n"
    assert err == ""


def test_lines_option_limits_output(head_tree):
    code, out, _ = run_head(["-n", "2", str(head_tree / "a.txt")])
    assert code == 0
    assert out == "l1\nl2\n"


def test_bytes_option_limits_output(head_tree):
    code, out, _ = run_head(["-c", "5", str(head_tree / "a.txt")])
    assert code == 0
    assert out == "l1\nl2"


def test_reads_stdin_when_no_operand(head_tree):
    code, out, _ = run_head([], cwd=head_tree, stdin_text="from stdin\n")
    assert code == 0
    assert out == "from stdin\n"


def test_dash_means_stdin(head_tree):
    code, out, _ = run_head(["-"], cwd=head_tree, stdin_text="from stdin\n")
    assert code == 0
    assert out == "from stdin\n"


def test_crlf_is_passed_through(head_tree):
    """CRLF 文件的 \\r 属于行内容，必须原样转交。"""
    code, out, _ = run_head(["-n", "2", str(head_tree / "crlf.txt")])
    assert code == 0
    assert out == "c1\r\nc2\r\n"


def test_last_line_without_newline_is_not_padded(head_tree):
    code, out, _ = run_head([str(head_tree / "nonl.txt")])
    assert code == 0
    assert out == "p1\np2\np3"


def test_empty_file_produces_no_output(head_tree):
    code, out, err = run_head([str(head_tree / "empty.txt")])
    assert code == 0
    assert out == ""
    assert err == ""


def test_binary_content_is_passed_through(head_tree):
    code, out, _ = run_head([str(head_tree / "bin.dat")])
    assert code == 0
    assert out.encode("utf-8", errors="surrogateescape") == bytes(range(256))


# ---------- 选项组合 ----------


def test_multiple_files_get_headers(head_tree):
    """第二个及以后的标题前先空一行。"""
    code, out, _ = run_head([str(head_tree / "a.txt"), str(head_tree / "b.txt")])
    assert code == 0
    assert out == "==> %s <==\nl1\nl2\nl3\nl4\nl5\n\n==> %s <==\nx\n" % (
        head_tree / "a.txt",
        head_tree / "b.txt",
    )


def test_quiet_suppresses_headers(head_tree):
    code, out, _ = run_head(["-q", str(head_tree / "a.txt"), str(head_tree / "b.txt")])
    assert code == 0
    assert out == "l1\nl2\nl3\nl4\nl5\nx\n"


def test_verbose_forces_header_for_single_file(head_tree):
    code, out, _ = run_head(["-v", str(head_tree / "a.txt")])
    assert code == 0
    assert out.startswith("==> ")


def test_quiet_and_verbose_last_one_wins(head_tree):
    """GNU 里 -q 与 -v 同时给时，后写的那个生效。"""
    code, out, _ = run_head(["-q", "-v", str(head_tree / "a.txt"), str(head_tree / "b.txt")])
    assert code == 0
    assert "==>" in out

    code, out, _ = run_head(["-v", "-q", str(head_tree / "a.txt"), str(head_tree / "b.txt")])
    assert code == 0
    assert "==>" not in out


def test_lines_and_bytes_last_one_wins(head_tree):
    """-c 7 -n 2 取 2 行，-n 2 -c 7 取 7 字节。"""
    code, out, _ = run_head(["-c", "7", "-n", "2", str(head_tree / "a.txt")])
    assert code == 0
    assert out == "l1\nl2\n"

    code, out, _ = run_head(["-n", "2", "-c", "7", str(head_tree / "a.txt")])
    assert code == 0
    assert out == "l1\nl2\nl"


def test_negative_count_means_all_but_last(head_tree):
    code, out, _ = run_head(["-n", "-2", str(head_tree / "a.txt")])
    assert code == 0
    assert out == "l1\nl2\nl3\n"


def test_negative_count_drops_unterminated_last_line(head_tree):
    """末行没有换行时，它也算一行，会被 -n -1 一起去掉。"""
    code, out, _ = run_head(["-n", "-1", str(head_tree / "nonl.txt")])
    assert code == 0
    assert out == "p1\np2\n"


def test_plus_sign_is_same_as_plain_count(head_tree):
    """head 没有 tail 那种「从第 N 行开始」的语义，+N 等价 N。"""
    code, out, _ = run_head(["-n", "+2", str(head_tree / "a.txt")])
    assert code == 0
    assert out == "l1\nl2\n"


def test_zero_and_negative_zero_differ(head_tree):
    """-n 0 一行不要，-n -0 全部都要。"""
    code, out, _ = run_head(["-n", "0", str(head_tree / "a.txt")])
    assert code == 0
    assert out == ""

    code, out, _ = run_head(["-n", "-0", str(head_tree / "a.txt")])
    assert code == 0
    assert out == "l1\nl2\nl3\nl4\nl5\n"


def test_compact_numeric_option(head_tree):
    """GNU 的 -NUM 紧凑写法等价于 -n NUM。"""
    code, out, _ = run_head(["-2", str(head_tree / "a.txt")])
    assert code == 0
    assert out == "l1\nl2\n"


def test_long_option_forms(head_tree):
    code, out, _ = run_head(["--lines=2", str(head_tree / "a.txt")])
    assert code == 0
    assert out == "l1\nl2\n"

    code, out, _ = run_head(["--bytes=5", str(head_tree / "a.txt")])
    assert code == 0
    assert out == "l1\nl2"


def test_multiplier_suffixes(head_tree):
    """b=512、k/K=1024、kB=1000、KiB=K。"""
    (head_tree / "big.txt").write_bytes(b"X" * 2000)

    code, out, _ = run_head(["-c", "1b", str(head_tree / "big.txt")])
    assert code == 0
    assert len(out) == 512

    code, out, _ = run_head(["-c", "1k", str(head_tree / "big.txt")])
    assert code == 0
    assert len(out) == 1024

    code, out, _ = run_head(["-c", "1kB", str(head_tree / "big.txt")])
    assert code == 0
    assert len(out) == 1000

    code, out, _ = run_head(["-c", "1KiB", str(head_tree / "big.txt")])
    assert code == 0
    assert len(out) == 1024


def test_zero_terminated_uses_nul_as_delimiter(head_tree):
    code, out, _ = run_head(["-z", "-n", "2", str(head_tree / "zeros.bin")])
    assert code == 0
    assert out == "z1\x00z2\x00"


def test_stdin_header_uses_standard_input(head_tree):
    code, out, _ = run_head(["-v", "-"], cwd=head_tree, stdin_text="s1\ns2\n")
    assert code == 0
    assert out == "==> standard input <==\ns1\ns2\n"


def test_blank_line_counts_as_a_line(head_tree):
    code, out, _ = run_head(["-n", "2", str(head_tree / "blank.txt")])
    assert code == 0
    assert out == "b1\n\n"


# ---------- 错误路径 ----------


def test_missing_file_reports_error_and_returns_two(head_tree):
    code, out, err = run_head([str(head_tree / "nope.txt")])
    assert code == 2
    assert out == ""
    assert "nope.txt" in err


def test_missing_file_gets_no_header(head_tree):
    """打不开的文件不打标题。"""
    code, out, err = run_head(
        ["-v", str(head_tree / "a.txt"), str(head_tree / "nope.txt")]
    )
    assert code == 2
    assert out.count("==>") == 1
    assert "nope.txt" not in out
    assert "nope.txt" in err


def test_directory_reports_error_but_keeps_going(head_tree):
    """目录会先打标题再报读取错误，后面的文件照常输出。"""
    code, out, err = run_head(
        [str(head_tree / "a.txt"), str(head_tree / "sub"), str(head_tree / "b.txt")]
    )
    assert code == 2
    assert out.startswith("==> ")
    assert "是一个目录" in err
    assert "x\n" in out


def test_invalid_count_is_usage_error(head_tree):
    namespace = build_head_namespace(["-n", "abc", str(head_tree / "a.txt")])
    ctx = RunContext(
        cwd=head_tree, stdout=io.StringIO(), stderr=io.StringIO(), stdin=io.StringIO("")
    )
    with pytest.raises(UsageError):
        head(namespace, ctx)


def test_invalid_suffix_is_usage_error(head_tree):
    namespace = build_head_namespace(["-c", "1g", str(head_tree / "a.txt")])
    ctx = RunContext(
        cwd=head_tree, stdout=io.StringIO(), stderr=io.StringIO(), stdin=io.StringIO("")
    )
    with pytest.raises(UsageError):
        head(namespace, ctx)


def test_missing_option_value_is_usage_error():
    with pytest.raises(SystemExit) as excinfo:
        run_head(["-n"])
    assert excinfo.value.code == 2


def test_unknown_option_is_usage_error():
    with pytest.raises(SystemExit) as excinfo:
        run_head(["--bogus"])
    assert excinfo.value.code == 2


def test_help_flag_exits_zero(capsys):
    with pytest.raises(SystemExit) as excinfo:
        run_head(["--help"])
    assert excinfo.value.code == 0
    assert "打印文件开头部分" in capsys.readouterr().out
