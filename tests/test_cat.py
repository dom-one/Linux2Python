"""cat 指令测试。

对照的是 Git Bash 里 GNU coreutils 8.32 的 cat 实测输出：
默认原样输出、多个文件连接、-n/-b 行号（编号右对齐 6 位加制表符）、
-E 行尾 $、-T 制表符 ^I、-s 连续空行压成一行、-v 的 ^ 与 M- 记号、
-e 等价 -vE、-t 等价 -vT、-A 等价 -vET、- 表示标准输入、
不给操作数读标准输入、CRLF 原样转交、末行无换行不补换行。
"""

import pytest

from conftest import run_cat


@pytest.fixture
def cat_tree(tmp_path):
    (tmp_path / "basic.txt").write_bytes(b"alpha\nbeta\ngamma\n")
    (tmp_path / "second.txt").write_bytes(b"delta\nepsilon\n")
    (tmp_path / "blank.txt").write_bytes(b"one\n\n\n\ntwo\n")
    (tmp_path / "ws.txt").write_bytes(b"one\n   \ntwo\n")
    (tmp_path / "tabs.txt").write_bytes(b"col1\tcol2\n")
    (tmp_path / "noeol.txt").write_bytes(b"one\ntwo")
    (tmp_path / "crlf.txt").write_bytes(b"l1\r\nl2\r\n")
    (tmp_path / "empty.txt").write_bytes(b"")
    (tmp_path / "ctrl.txt").write_bytes(b"bell\x07 del\x7f esc\x1b\n")
    (tmp_path / "high.bin").write_bytes(b"\x80\xa0\xff\n")
    sub = tmp_path / "sub"
    sub.mkdir()
    return tmp_path


# ---------- 正常路径 ----------


def test_prints_file_verbatim(cat_tree):
    code, out, err = run_cat([str(cat_tree / "basic.txt")])
    assert code == 0
    assert out == "alpha\nbeta\ngamma\n"
    assert err == ""


def test_multiple_files_are_concatenated(cat_tree):
    code, out, _ = run_cat([str(cat_tree / "basic.txt"), str(cat_tree / "second.txt")])
    assert code == 0
    assert out == "alpha\nbeta\ngamma\ndelta\nepsilon\n"


def test_empty_file_produces_no_output(cat_tree):
    code, out, err = run_cat([str(cat_tree / "empty.txt")])
    assert code == 0
    assert out == ""
    assert err == ""


def test_reads_stdin_when_no_operand(cat_tree):
    code, out, _ = run_cat([], cwd=cat_tree, stdin_text="from stdin\n")
    assert code == 0
    assert out == "from stdin\n"


def test_dash_means_stdin(cat_tree):
    code, out, _ = run_cat(["-"], cwd=cat_tree, stdin_text="from stdin\n")
    assert code == 0
    assert out == "from stdin\n"


def test_crlf_is_passed_through(cat_tree):
    """CRLF 文件的 \\r 属于行内容，必须原样转交，不能被吃掉。"""
    code, out, _ = run_cat([str(cat_tree / "crlf.txt")])
    assert code == 0
    assert out == "l1\r\nl2\r\n"


def test_last_line_without_newline_gets_none(cat_tree):
    code, out, _ = run_cat([str(cat_tree / "noeol.txt")])
    assert code == 0
    assert out == "one\ntwo"


def test_gbk_file_is_decoded(cat_tree):
    """GBK 内容应按 GBK 解码后输出 UTF-8，中文不乱码。"""
    target = cat_tree / "gbk.txt"
    target.write_bytes("中文内容\n".encode("gb18030"))
    code, out, _ = run_cat([str(target)])
    assert code == 0
    assert out == "中文内容\n"


def test_binary_file_is_passed_through_unchanged(cat_tree):
    """二进制文件逐字节原样转交，不做编码转换。"""
    target = cat_tree / "blob.bin"
    payload = bytes(range(256))
    target.write_bytes(payload)
    code, out, _ = run_cat([str(target)])
    assert code == 0
    assert out.encode("utf-8", errors="surrogateescape") == payload


def test_binary_file_with_high_bytes_is_unchanged(cat_tree):
    """没有 NUL 字节但含高位字节的文件，也应原样转交。"""
    target = cat_tree / "high.bin"
    payload = b"\x80\x81\xfe\xff\n"
    target.write_bytes(payload)
    code, out, _ = run_cat([str(target)])
    assert code == 0
    assert out.encode("utf-8", errors="surrogateescape") == payload


# ---------- 选项组合 ----------


def test_number_prefixes_all_lines(cat_tree):
    code, out, _ = run_cat(["-n", str(cat_tree / "basic.txt")])
    assert code == 0
    assert out == "     1\talpha\n     2\tbeta\n     3\tgamma\n"


def test_number_nonblank_skips_blank_lines(cat_tree):
    """-b 只给非空行编号，且计数器不因空行前进。"""
    code, out, _ = run_cat(["-b", str(cat_tree / "blank.txt")])
    assert code == 0
    assert out == "     1\tone\n\n\n\n     2\ttwo\n"


def test_number_nonblank_overrides_number(cat_tree):
    """GNU 里 -b 覆盖 -n，与选项先后顺序无关。"""
    code, out, _ = run_cat(["-n", "-b", str(cat_tree / "blank.txt")])
    assert code == 0
    assert out == "     1\tone\n\n\n\n     2\ttwo\n"


def test_number_counts_upward_across_files(cat_tree):
    """行号跨文件连续累计，不在文件边界重置。"""
    code, out, _ = run_cat(["-n", str(cat_tree / "basic.txt"), str(cat_tree / "second.txt")])
    assert code == 0
    assert out == (
        "     1\talpha\n     2\tbeta\n     3\tgamma\n"
        "     4\tdelta\n     5\tepsilon\n"
    )


def test_number_column_widens_past_nine(cat_tree):
    target = cat_tree / "many.txt"
    target.write_bytes(b"".join(b"l%d\n" % i for i in range(1, 13)))
    _, out, _ = run_cat(["-n", str(target)])
    lines = out.splitlines()
    assert lines[0] == "     1\tl1"
    assert lines[8] == "     9\tl9"
    assert lines[9] == "    10\tl10"


def test_show_ends_marks_line_end(cat_tree):
    code, out, _ = run_cat(["-E", str(cat_tree / "basic.txt")])
    assert code == 0
    assert out == "alpha$\nbeta$\ngamma$\n"


def test_show_ends_does_not_mark_unterminated_last_line(cat_tree):
    """末行没有换行符时不补 $，与 GNU 一致。"""
    code, out, _ = run_cat(["-E", str(cat_tree / "noeol.txt")])
    assert code == 0
    assert out == "one$\ntwo"


def test_show_tabs_marks_tab(cat_tree):
    code, out, _ = run_cat(["-T", str(cat_tree / "tabs.txt")])
    assert code == 0
    assert out == "col1^Icol2\n"


def test_squeeze_blank_collapses_repeated_empty_lines(cat_tree):
    code, out, _ = run_cat(["-s", str(cat_tree / "blank.txt")])
    assert code == 0
    assert out == "one\n\ntwo\n"


def test_squeeze_blank_leaves_whitespace_lines_alone(cat_tree):
    """只含空格的行不是空行，-s 不压它。"""
    code, out, _ = run_cat(["-s", str(cat_tree / "ws.txt")])
    assert code == 0
    assert out == "one\n   \ntwo\n"


def test_squeeze_state_continues_across_files(cat_tree):
    """空行压紧状态跨文件延续。"""
    first = cat_tree / "s1.txt"
    first.write_bytes(b"x\n\n")
    second = cat_tree / "s2.txt"
    second.write_bytes(b"\ny\n")
    code, out, _ = run_cat(["-s", str(first), str(second)])
    assert code == 0
    assert out == "x\n\ny\n"


def test_show_nonprinting_uses_caret_notation(cat_tree):
    code, out, _ = run_cat(["-v", str(cat_tree / "ctrl.txt")])
    assert code == 0
    assert out == "bell^G del^? esc^[\n"


def test_show_nonprinting_uses_meta_notation(cat_tree):
    """高位字节显示成 M- 加低七位记号。"""
    code, out, _ = run_cat(["-v", str(cat_tree / "high.bin")])
    assert code == 0
    assert out == "M-^@M- M-^?\n"


def test_e_is_equivalent_to_vE(cat_tree):
    """GNU 里 -e 等价于 -vE：既显示 $ 也显示非打印字符，$ 落在行尾。"""
    code, out, _ = run_cat(["-e", str(cat_tree / "ctrl.txt")])
    assert code == 0
    assert out == "bell^G del^? esc^[$\n"

def test_t_is_equivalent_to_vT(cat_tree):
    code, out, _ = run_cat(["-t", str(cat_tree / "tabs.txt")])
    assert code == 0
    assert out == "col1^Icol2\n"


def test_show_all_is_equivalent_to_vET(cat_tree):
    code, out, _ = run_cat(["-A", str(cat_tree / "tabs.txt")])
    assert code == 0
    assert out == "col1^Icol2$\n"


def test_number_with_squeeze(cat_tree):
    code, out, _ = run_cat(["-n", "-s", str(cat_tree / "blank.txt")])
    assert code == 0
    assert out == "     1\tone\n     2\t\n     3\ttwo\n"


def test_number_nonblank_with_squeeze(cat_tree):
    code, out, _ = run_cat(["-b", "-s", str(cat_tree / "blank.txt")])
    assert code == 0
    assert out == "     1\tone\n\n     2\ttwo\n"


def test_options_combine_on_stdin(cat_tree):
    code, out, _ = run_cat(["-n"], cwd=cat_tree, stdin_text="one\ntwo\n")
    assert code == 0
    assert out == "     1\tone\n     2\ttwo\n"


def test_stdin_and_file_can_be_mixed(cat_tree):
    code, out, _ = run_cat([str(cat_tree / "basic.txt"), "-"], cwd=cat_tree, stdin_text="tail\n")
    assert code == 0
    assert out == "alpha\nbeta\ngamma\ntail\n"


# ---------- 错误路径 ----------


def test_missing_file_reports_error_and_exits_two(cat_tree):
    code, out, err = run_cat([str(cat_tree / "nope.txt")])
    assert code == 2
    assert out == ""
    assert "nope.txt" in err


def test_error_does_not_stop_other_operands(cat_tree):
    """某个文件打不开时，其余文件照常输出。"""
    code, out, err = run_cat([str(cat_tree / "nope.txt"), str(cat_tree / "basic.txt")])
    assert code == 2
    assert out == "alpha\nbeta\ngamma\n"
    assert "nope.txt" in err


def test_directory_operand_reports_error(cat_tree):
    code, out, err = run_cat([str(cat_tree / "sub")])
    assert code == 2
    assert out == ""
    assert "目录" in err


def test_help_flag_exits_zero(capsys):
    with pytest.raises(SystemExit) as excinfo:
        run_cat(["--help"])
    assert excinfo.value.code == 0
    assert "连接文件内容" in capsys.readouterr().out
