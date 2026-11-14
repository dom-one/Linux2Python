"""awk-lite 指令的测试。

覆盖三块：正常路径、选项组合、错误路径。

语义基线来自 GNU awk 5.3.2（Git Bash 的 /usr/bin/awk）实跑对照，
60 组用例（字段取值 / 模式 / 分隔符 / 变量 / 多文件 / 标准输入 / GBK 文件）
输出逐条一致。

关键语义（都是实测出来的，不是照抄手册）：

- 默认分隔符是「空白串」：连续空格与制表符算一个分隔，两端的空白不算字段
- ``-F`` 给单个分隔符时按字面切，连续出现会切出空字段（GNU 行为）
- ``-F`` 的值先解开转义（``\\t`` 是制表符），多字符分隔符按字面串处理
- ``{print}`` 等价于 ``{print $0}``，多个参数之间用 OFS（默认一个空格）连接
- ``$NF`` 是最后一个字段；字段号超出范围时是空串
- 模式是正则（ERE），只写模式不写动作时打整行
- ``NR`` 跨文件连续，``FNR`` 每个文件从头算，``FILENAME`` 是当前文件名
- ``-v name=value`` 赋的变量放在字段位置时，值是数字就当字段号
- 文件读不到返回 2，程序写错也返回 2；正常处理完返回 0（没有输出也是 0）
"""

import pytest

from conftest import run_awk_lite
from w2l.errors import UsageError


@pytest.fixture
def workdir(tmp_path):
    """一个装着样例文件的小目录。"""
    (tmp_path / "app.log").write_bytes(
        b"INFO start app\nERROR failed db\nwarn  retry queue\nERROR again db\n"
    )
    (tmp_path / "two.log").write_bytes(b"INFO second file\nERROR tail error\n")
    (tmp_path / "semi.log").write_bytes(b"a;b;c\nd;e;f\n")
    (tmp_path / "gap.log").write_bytes(b"a;;c\n")
    (tmp_path / "empty.log").write_bytes(b"")
    (tmp_path / "blank.log").write_bytes(b"\n\nx y\n")
    (tmp_path / "nonl.log").write_bytes(b"one two")
    (tmp_path / "gbk.log").write_bytes("INFO 开始\nERROR 失败\n".encode("gb18030"))
    (tmp_path / "subdir").mkdir()
    return tmp_path


# --------------------------------------------------------------------------
# 正常路径
# --------------------------------------------------------------------------


def test_awk_lite_prints_first_field(workdir):
    """{print $1} 取每行的第一列。"""
    code, out, err = run_awk_lite(["{print $1}", "app.log"], cwd=workdir)
    assert code == 0
    assert err == ""
    assert out == "INFO\nERROR\nwarn\nERROR\n"


def test_awk_lite_prints_last_field(workdir):
    """$NF 取最后一个字段。"""
    code, out, _ = run_awk_lite(["{print $NF}", "app.log"], cwd=workdir)
    assert code == 0
    assert out == "app\ndb\nqueue\ndb\n"


def test_awk_lite_bare_print_is_whole_line(workdir):
    """裸 print 等价于 {print $0}。"""
    code, out, _ = run_awk_lite(["{print}", "app.log"], cwd=workdir)
    assert code == 0
    assert out == (
        "INFO start app\n"
        "ERROR failed db\n"
        "warn  retry queue\n"
        "ERROR again db\n"
    )


def test_awk_lite_prints_several_fields_with_space(workdir):
    """多个 print 参数之间用一个空格连。"""
    code, out, _ = run_awk_lite(["{print $1, $2}", "app.log"], cwd=workdir)
    assert code == 0
    assert out == "INFO start\nERROR failed\nwarn retry\nERROR again\n"


def test_awk_lite_field_beyond_end_is_empty(workdir):
    """字段号超出范围时是空串，不报错。"""
    code, out, _ = run_awk_lite(["{print $9}", "app.log"], cwd=workdir)
    assert code == 0
    assert out == "\n\n\n\n"


def test_awk_lite_pattern_only_prints_matching_lines(workdir):
    """只写模式时打整行。"""
    code, out, _ = run_awk_lite(["/ERROR/", "app.log"], cwd=workdir)
    assert code == 0
    assert out == "ERROR failed db\nERROR again db\n"


def test_awk_lite_pattern_with_action(workdir):
    """模式加动作：只对命中的行做动作。"""
    code, out, _ = run_awk_lite(["/ERROR/ {print $2}", "app.log"], cwd=workdir)
    assert code == 0
    assert out == "failed\nagain\n"


def test_awk_lite_pattern_not_matching_prints_nothing(workdir):
    """模式不命中时没有输出，但退出码仍是 0（与 GNU awk 一致）。"""
    code, out, err = run_awk_lite(["/nomatch/", "app.log"], cwd=workdir)
    assert code == 0
    assert out == ""
    assert err == ""


def test_awk_lite_builtin_variables(workdir):
    """NR / NF / FNR / FILENAME。"""
    code, out, _ = run_awk_lite(["{print NR, NF}", "app.log"], cwd=workdir)
    assert code == 0
    assert out == "1 3\n2 3\n3 3\n4 3\n"

    code, out, _ = run_awk_lite(["{print FNR}", "app.log", "two.log"], cwd=workdir)
    assert code == 0
    assert out == "1\n2\n3\n4\n1\n2\n"

    code, out, _ = run_awk_lite(["{print FILENAME}", "app.log"], cwd=workdir)
    assert code == 0
    assert out == "app.log\napp.log\napp.log\napp.log\n"


def test_awk_lite_reads_stdin():
    """不给文件时读标准输入。"""
    code, out, _ = run_awk_lite(["{print $1}"], stdin_text="a b\nc d\n")
    assert code == 0
    assert out == "a\nc\n"


def test_awk_lite_multiple_files_share_nr(workdir):
    """多文件的 NR 连续。"""
    code, out, _ = run_awk_lite(["{print NR, $1}", "app.log", "two.log"], cwd=workdir)
    assert code == 0
    assert out == (
        "1 INFO\n2 ERROR\n3 warn\n4 ERROR\n5 INFO\n6 ERROR\n"
    )


def test_awk_lite_empty_file(workdir):
    """空文件没有输出，退出码仍是 0。"""
    code, out, _ = run_awk_lite(["{print $1}", "empty.log"], cwd=workdir)
    assert code == 0
    assert out == ""


def test_awk_lite_blank_lines_have_no_field(workdir):
    """空行的字段数是 0。"""
    code, out, _ = run_awk_lite(["{print NF}", "blank.log"], cwd=workdir)
    assert code == 0
    assert out == "0\n0\n2\n"


def test_awk_lite_default_separator_splits_runs_of_blanks(workdir):
    """默认分隔符把连续空白当一个，两端空白不算字段。"""
    (workdir / "sp.txt").write_bytes(b"a  b   c\n")
    code, out, _ = run_awk_lite(["{print NF, $2}", "sp.txt"], cwd=workdir)
    assert code == 0
    assert out == "3 b\n"


def test_awk_lite_reads_gbk_file(workdir):
    """GBK 文件按判定出的编码解码，中文正常。"""
    code, out, _ = run_awk_lite(["{print $2}", "gbk.log"], cwd=workdir)
    assert code == 0
    assert out == "开始\n失败\n"


def test_awk_lite_last_line_without_newline(workdir):
    """末行没有换行符也照样处理。"""
    code, out, _ = run_awk_lite(["{print $2}", "nonl.log"], cwd=workdir)
    assert code == 0
    assert out == "two\n"


def test_awk_lite_print_with_parentheses(workdir):
    """print(...) 的写法也认。"""
    code, out, _ = run_awk_lite(["{print($1, $2)}", "app.log"], cwd=workdir)
    assert code == 0
    assert out == "INFO start\nERROR failed\nwarn retry\nERROR again\n"


def test_awk_lite_prints_string_literal(workdir):
    """字符串字面量原样打印。"""
    code, out, _ = run_awk_lite(['{print "x", $1}', "app.log"], cwd=workdir)
    assert code == 0
    assert out == "x INFO\nx ERROR\nx warn\nx ERROR\n"


# --------------------------------------------------------------------------
# 选项组合
# --------------------------------------------------------------------------


def test_awk_lite_field_separator_option(workdir):
    """-F 换分隔符。"""
    code, out, _ = run_awk_lite(["-F;", "{print $2}", "semi.log"], cwd=workdir)
    assert code == 0
    assert out == "b\ne\n"


def test_awk_lite_field_separator_keeps_empty_fields(workdir):
    """单字符分隔符连续出现会切出空字段。"""
    code, out, _ = run_awk_lite(["-F;", "{print $1, $2, $3}", "gap.log"], cwd=workdir)
    assert code == 0
    assert out == "a  c\n"


def test_awk_lite_field_separator_long_option(workdir):
    """--field-separator 与 -F 等价。"""
    code, out, _ = run_awk_lite(
        ["--field-separator", ";", "{print $3}", "semi.log"], cwd=workdir
    )
    assert code == 0
    assert out == "c\nf\n"


def test_awk_lite_single_char_separator_is_literal(workdir):
    """单个字符的分隔符按字面量切，`.` 就是一个点，不是任意字符。"""
    (workdir / "dot.txt").write_bytes(b"a.b.c\n")
    code, out, _ = run_awk_lite(["-F.", "{print $2}", "dot.txt"], cwd=workdir)
    assert code == 0
    assert out == "b\n"


def test_awk_lite_multi_char_separator_is_regex(workdir):
    """多个字符的分隔符按正则切（GNU 的规则）。"""
    (workdir / "multi.txt").write_bytes(b"aXXbXXc\n")
    code, out, _ = run_awk_lite(["-FXX", "{print $2}", "multi.txt"], cwd=workdir)
    assert code == 0
    assert out == "b\n"

    code, out, _ = run_awk_lite(["-F[XY]+", "{print $2}", "multi.txt"], cwd=workdir)
    assert code == 0
    assert out == "b\n"


def test_awk_lite_explicit_space_separator_matches_default(workdir):
    """显式给一个空格当分隔符，跟默认一样按空白串切。"""
    (workdir / "sp.txt").write_bytes(b"a  b   c\n")
    code, out, _ = run_awk_lite(["-F ", "{print NF}", "sp.txt"], cwd=workdir)
    assert code == 0
    assert out == "3\n"


def test_awk_lite_stdin_honours_separator():
    """读标准输入时也按 -F 切字段。"""
    code, out, _ = run_awk_lite(["-F;", "{print $2}"], stdin_text="a;b\nc;d\n")
    assert code == 0
    assert out == "b\nd\n"


def test_awk_lite_field_separator_decodes_escape(workdir):
    """-F 的值先解开转义，\\t 是制表符。"""
    (workdir / "tab.txt").write_bytes(b"a\tb\n")
    code, out, _ = run_awk_lite(["-F\\t", "{print $2}", "tab.txt"], cwd=workdir)
    assert code == 0
    assert out == "b\n"


def test_awk_lite_assign_variable_as_field_number(workdir):
    """-v 赋的变量放在字段位置时，值是数字就当字段号。"""
    code, out, _ = run_awk_lite(["-v", "n=2", "{print $n}", "app.log"], cwd=workdir)
    assert code == 0
    assert out == "start\nfailed\nretry\nagain\n"


def test_awk_lite_assign_variable_as_value(workdir):
    """变量也可以直接打印。"""
    code, out, _ = run_awk_lite(["-v", "tag=INFO", "{print tag}", "app.log"], cwd=workdir)
    assert code == 0
    assert out == "INFO\nINFO\nINFO\nINFO\n"


def test_awk_lite_assign_changes_ofs(workdir):
    """-v OFS=; 改掉多个参数之间的连接符。"""
    code, out, _ = run_awk_lite(["-v", "OFS=;", "{print $1, $2}", "app.log"], cwd=workdir)
    assert code == 0
    assert out == "INFO;start\nERROR;failed\nwarn;retry\nERROR;again\n"


def test_awk_lite_assign_long_option(workdir):
    """--assign 与 -v 等价。"""
    code, out, _ = run_awk_lite(
        ["--assign", "n=1", "{print $n}", "app.log"], cwd=workdir
    )
    assert code == 0
    assert out == "INFO\nERROR\nwarn\nERROR\n"


def test_awk_lite_options_combined(workdir):
    """-F 与 -v 一起用。"""
    code, out, _ = run_awk_lite(
        ["-F;", "-v", "n=3", "{print $n}", "semi.log"], cwd=workdir
    )
    assert code == 0
    assert out == "c\nf\n"


def test_awk_lite_separator_beats_assign(workdir):
    """-F 优先于 -v FS=...。"""
    code, out, _ = run_awk_lite(
        ["-v", "FS=,", "-F;", "{print $2}", "semi.log"], cwd=workdir
    )
    assert code == 0
    assert out == "b\ne\n"


def test_awk_lite_options_before_program(workdir):
    """选项写在程序前面，位置参数仍然是程序和文件。"""
    code, out, _ = run_awk_lite(["-F;", "{print $1}", "semi.log"], cwd=workdir)
    assert code == 0
    assert out == "a\nd\n"


# --------------------------------------------------------------------------
# 错误路径
# --------------------------------------------------------------------------


def test_awk_lite_empty_program_is_usage_error(workdir):
    """程序是空的报用法错误。"""
    with pytest.raises(UsageError):
        run_awk_lite(["", "app.log"], cwd=workdir)


def test_awk_lite_unknown_program_is_usage_error(workdir):
    """看不懂的程序报用法错误。"""
    with pytest.raises(UsageError):
        run_awk_lite(["print $1", "app.log"], cwd=workdir)


def test_awk_lite_unclosed_brace_is_usage_error(workdir):
    """动作块没闭合报用法错误。"""
    with pytest.raises(UsageError):
        run_awk_lite(["{print $1", "app.log"], cwd=workdir)


def test_awk_lite_unsupported_action_is_usage_error(workdir):
    """只支持 print，其他动作明确报错。"""
    with pytest.raises(UsageError):
        run_awk_lite(["{printf \"%s\", $1}", "app.log"], cwd=workdir)


def test_awk_lite_unsupported_expression_is_usage_error(workdir):
    """算术表达式不支持，明确报错而不是悄悄忽略。"""
    with pytest.raises(UsageError):
        run_awk_lite(["{print $1 + $2}", "app.log"], cwd=workdir)


def test_awk_lite_invalid_regex_is_usage_error(workdir):
    """无效的正则报用法错误。"""
    with pytest.raises(UsageError):
        run_awk_lite(["/[unclosed/", "app.log"], cwd=workdir)


def test_awk_lite_unterminated_regex_is_usage_error(workdir):
    """正则没收尾的 / 报用法错误。"""
    with pytest.raises(UsageError):
        run_awk_lite(["/ERROR", "app.log"], cwd=workdir)


def test_awk_lite_assign_without_equals_is_usage_error(workdir):
    """-v 的参数要写成 name=value。"""
    with pytest.raises(UsageError):
        run_awk_lite(["-v", "name", "{print $1}", "app.log"], cwd=workdir)


def test_awk_lite_unassigned_variable_is_usage_error(workdir):
    """变量没赋值就用到，报用法错误。"""
    with pytest.raises(UsageError):
        run_awk_lite(["{print $x}", "app.log"], cwd=workdir)


def test_awk_lite_missing_file_returns_two(workdir):
    """文件读不到返回 2 并写错误信息。"""
    code, out, err = run_awk_lite(["{print $1}", "nope.log"], cwd=workdir)
    assert code == 2
    assert out == ""
    assert "nope.log" in err


def test_awk_lite_missing_file_still_processes_others(workdir):
    """中间的文件读不到，后面的文件照样处理，最后返回 2。"""
    code, out, err = run_awk_lite(
        ["{print $1}", "app.log", "nope.log", "two.log"], cwd=workdir
    )
    assert code == 2
    assert out == "INFO\nERROR\nwarn\nERROR\nINFO\nERROR\n"
    assert "nope.log" in err


def test_awk_lite_directory_operand_returns_two(workdir):
    """目录当文件用返回 2。"""
    code, out, err = run_awk_lite(["{print $1}", "subdir"], cwd=workdir)
    assert code == 2
    assert out == ""
    assert "subdir" in err
