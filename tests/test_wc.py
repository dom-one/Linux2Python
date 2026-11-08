"""wc 指令测试。

断言里的期望输出全部取自 Git Bash 里 GNU coreutils 8.32 的 wc 实测值：
默认打印行/词/字节三列、-l/-w/-m/-c/-L 各自开一列、列的顺序固定、
行只按 \\n 计、词按空白分隔（片段里夹控制字符不算断开，整个片段没有可打印
字符时不算词）、-m 按字符计、-L 按显示宽度（制表符展开到 8 的倍数、\\r 清零、
取行内出现过的最大列数）、多文件最后打一行 total（最长行取最大值）、
- 表示标准输入、不给操作数读标准输入且不写文件名、重复的 - 只读一次、
打不开的文件不输出计数行只报错、目录输出一行全 0 再报错。

与 GNU 不同的地方（本项目约定）：错误信息是中文，退出码是 2（GNU 是 1）。
"""

import pytest

from conftest import run_wc


@pytest.fixture
def wc_tree(tmp_path):
    (tmp_path / "one.txt").write_bytes(b"x\n")
    (tmp_path / "two.txt").write_bytes(b"a b\nc\n")
    (tmp_path / "empty.txt").write_bytes(b"")
    (tmp_path / "noeol.txt").write_bytes(b"a\nb")
    (tmp_path / "crlf.txt").write_bytes(b"c1\r\nc2\r\n")
    (tmp_path / "cjk.txt").write_bytes("中文\n".encode("utf-8"))
    (tmp_path / "tab.txt").write_bytes(b"a\tb\tc\n")
    (tmp_path / "big.txt").write_bytes(b"y" * 99 + b"\n")
    (tmp_path / "bin.dat").write_bytes(b"\x00\x01\x02\xff\xfe\n")
    (tmp_path / "long.txt").write_bytes(b"x" * 19 + b"\n")
    (tmp_path / "short.txt").write_bytes(b"z\n")
    sub = tmp_path / "sub"
    sub.mkdir()
    return tmp_path


# ---------- 正常路径 ----------


def test_default_prints_lines_words_and_bytes(wc_tree):
    code, out, err = run_wc(["one.txt"], cwd=wc_tree)
    assert code == 0
    assert out == "1 1 2 one.txt\n"
    assert err == ""


def test_lines_option_prints_one_column(wc_tree):
    code, out, _ = run_wc(["-l", "one.txt"], cwd=wc_tree)
    assert code == 0
    assert out == "1 one.txt\n"


def test_words_option_prints_one_column(wc_tree):
    code, out, _ = run_wc(["-w", "two.txt"], cwd=wc_tree)
    assert code == 0
    assert out == "3 two.txt\n"


def test_bytes_option_prints_one_column(wc_tree):
    code, out, _ = run_wc(["-c", "two.txt"], cwd=wc_tree)
    assert code == 0
    assert out == "6 two.txt\n"


def test_chars_option_counts_characters(wc_tree):
    """-m 数的是字符不是字节：中文一个字算一个字符。"""
    code, out, _ = run_wc(["-m", "cjk.txt"], cwd=wc_tree)
    assert code == 0
    assert out == "3 cjk.txt\n"


def test_max_line_length_option_prints_display_width(wc_tree):
    """-L 数的是显示列宽：制表符展开到 8 的倍数。"""
    code, out, _ = run_wc(["-L", "tab.txt"], cwd=wc_tree)
    assert code == 0
    assert out == "17 tab.txt\n"


def test_multiple_files_add_a_total_line(wc_tree):
    code, out, _ = run_wc(["-lwc", "one.txt", "two.txt"], cwd=wc_tree)
    assert code == 0
    assert out == "1 1 2 one.txt\n2 3 6 two.txt\n3 4 8 total\n"


def test_reads_stdin_when_no_operand(wc_tree):
    """不给操作数时读标准输入，那一行不写文件名。"""
    code, out, _ = run_wc([], cwd=wc_tree, stdin_text="a b\nc\n")
    assert code == 0
    assert out == "      2       3       6\n"


def test_dash_means_stdin(wc_tree):
    """- 表示标准输入，文件名那一列写的是 -。"""
    code, out, _ = run_wc(["-lwc", "-"], cwd=wc_tree, stdin_text="a b\nc\n")
    assert code == 0
    assert out == "      2       3       6 -\n"


def test_repeated_dash_reads_stdin_once(wc_tree):
    """重复的 - 只读一次标准输入，第二次起是空的，total 也只算一次。"""
    code, out, _ = run_wc(["-lw", "-", "-"], cwd=wc_tree, stdin_text="a b\nc\n")
    assert code == 0
    assert out == "      2       3 -\n      0       0 -\n      2       3 total\n"


def test_empty_file_counts_zero(wc_tree):
    code, out, _ = run_wc(["-lwc", "empty.txt"], cwd=wc_tree)
    assert code == 0
    assert out == "0 0 0 empty.txt\n"


def test_last_line_without_newline_is_not_a_line(wc_tree):
    """末尾没有换行的那一行不算一行，但它的词照样算。"""
    code, out, _ = run_wc(["-lwc", "noeol.txt"], cwd=wc_tree)
    assert code == 0
    assert out == "1 2 3 noeol.txt\n"


def test_crlf_keeps_carriage_return_in_line(wc_tree):
    """\\r 留在行内容里，字节数照算。"""
    code, out, _ = run_wc(["-lwc", "crlf.txt"], cwd=wc_tree)
    assert code == 0
    assert out == "2 2 8 crlf.txt\n"


def test_binary_file_has_no_words(wc_tree):
    """整个片段没有可打印字符时不算词。"""
    code, out, _ = run_wc(["-lw", "bin.dat"], cwd=wc_tree)
    assert code == 0
    assert out == "1 0 bin.dat\n"


# ---------- 选项组合 ----------


def test_column_order_is_fixed(wc_tree):
    """列的顺序固定为 行 词 字符 字节 最长行，与选项书写顺序无关。"""
    code, out, _ = run_wc(["-clw", "one.txt"], cwd=wc_tree)
    assert code == 0
    assert out == "1 1 2 one.txt\n"


def test_width_follows_the_total_size(wc_tree):
    """列宽按普通文件字节数之和撑开，各列共用同一个宽度。"""
    code, out, _ = run_wc(["-lwc", "one.txt", "big.txt"], cwd=wc_tree)
    assert code == 0
    assert out == "  1   1   2 one.txt\n  1   1 100 big.txt\n  2   2 102 total\n"


def test_total_takes_the_longest_line_not_the_sum(wc_tree):
    """total 的最长行取最大值，不是求和。"""
    code, out, _ = run_wc(["-L", "long.txt", "short.txt"], cwd=wc_tree)
    assert code == 0
    assert out == "19 long.txt\n 1 short.txt\n19 total\n"


def test_max_line_length_resets_at_carriage_return(wc_tree):
    """\\r 之后的宽度再大也不算数，取的是行内出现过的最大列数。"""
    code, out, _ = run_wc(["-L", "crlf.txt"], cwd=wc_tree)
    assert code == 0
    assert out == "2 crlf.txt\n"


def test_single_column_is_not_padded(wc_tree):
    """只打印一列时不做对齐，计数有多长就写多长。"""
    code, out, _ = run_wc(["-l", "big.txt"], cwd=wc_tree)
    assert code == 0
    assert out == "1 big.txt\n"


def test_options_can_be_combined(wc_tree):
    code, out, _ = run_wc(["-lwc", "-m", "-L", "one.txt"], cwd=wc_tree)
    assert code == 0
    assert out == "1 1 2 2 1 one.txt\n"


# ---------- 错误路径 ----------


def test_missing_file_reports_error_and_returns_2(wc_tree):
    """打不开的文件不输出计数行，只报错，退出码按项目约定是 2。"""
    code, out, err = run_wc(["-l", "nope.txt"], cwd=wc_tree)
    assert code == 2
    assert out == ""
    assert "nope.txt" in err


def test_missing_file_does_not_stop_other_files(wc_tree):
    """缺文件不影响后面的文件，total 只算读到的那些。"""
    code, out, err = run_wc(["-lwc", "one.txt", "nope.txt"], cwd=wc_tree)
    assert code == 2
    assert out == "1 1 2 one.txt\n1 1 2 total\n"
    assert "nope.txt" in err


def test_directory_prints_zero_row_and_reports_error(wc_tree):
    """目录会打一行全 0，再报「是一个目录」。"""
    code, out, err = run_wc(["-lwc", "sub"], cwd=wc_tree)
    assert code == 2
    assert out == "      0       0       0 sub\n"
    assert "sub" in err
    assert "目录" in err
