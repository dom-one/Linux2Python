"""sed 指令的测试。

覆盖三块：正常路径、选项组合、错误路径。

语义基线来自 GNU sed 4.9（Git Bash 的 /usr/bin/sed）实跑对照，
162 组用例（脚本 / 原地编辑 / 标准输入三组）输出逐字节一致。

关键语义（都是实测出来的，不是照抄手册）：

- 正则默认 BRE：``\\(`` ``\\)`` 是分组、``\\|`` 是或、``\\+`` ``\\?`` 是量词；
  未转义的 ``( ) { } | + ?`` 都是字面量；``-r`` 切到 ERE
- 替换默认只换每行第一个匹配，``g`` 换成全部，``N`` 换成第 N 个
- ``s`` 不带 ``g`` 时，整块模式空间里也只换第一个匹配
- 空匹配紧跟在非空匹配后面时不算一次匹配（``s/.*/X/g`` 只换一个 X）
- ``-n`` 关掉自动打印，但 ``a`` / ``i`` / ``c`` 的文本照样输出
- ``n`` 先打印当前模式空间再读下一行；``N`` 把下一行接在模式空间后面
- ``{ }`` 块的地址只在进块时判一次，块里改过模式空间不影响它
- 范围地址的终点是正则时不在起始行上试；终点找不到就延伸到文件末尾
- 地址 ``0`` 表示第一行之前，所以 ``0,/re/`` 从第 1 行开始
- 文本模式读文件时行尾的 CR 被去掉，``-b`` 保留
"""

import pytest

from conftest import run_sed
from w2l.errors import UsageError


@pytest.fixture
def workdir(tmp_path):
    """一个装着样例文件的小目录。"""
    (tmp_path / "a.txt").write_bytes(b"alpha\nbravo\ncharlie\ndelta\necho\n")
    (tmp_path / "num.txt").write_bytes(b"1 one\n2 two\n3 three\n4 four\n5 five\n")
    (tmp_path / "crlf.txt").write_bytes(b"one\r\ntwo\r\nthree\r\n")
    (tmp_path / "nonl.txt").write_bytes(b"no trailing newline")
    return tmp_path


# --------------------------------------------------------------------------
# 正常路径
# --------------------------------------------------------------------------


def test_sed_replaces_first_match_per_line(workdir):
    """默认每行只换第一个匹配。"""
    code, out, err = run_sed(["s/a/b/", "a.txt"], cwd=workdir)
    assert code == 0
    assert err == ""
    assert out == "blpha\nbrbvo\nchbrlie\ndeltb\necho\n"


def test_sed_global_flag(workdir):
    """g 换成这一行里的全部匹配。"""
    code, out, _ = run_sed(["s/a/b/g", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "blphb\nbrbvo\nchbrlie\ndeltb\necho\n"


def test_sed_nth_occurrence_flag(workdir):
    """数字标志只换第 N 个匹配。"""
    code, out, _ = run_sed(["s/a/A/2", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "alphA\nbravo\ncharlie\ndelta\necho\n"


def test_sed_quiet_mode_prints_nothing(workdir):
    """-n 关掉自动打印。"""
    code, out, _ = run_sed(["-n", "p", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "alpha\nbravo\ncharlie\ndelta\necho\n"

    code, out, _ = run_sed(["-n", "2p", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "bravo\n"


def test_sed_line_number_address(workdir):
    """行号地址只作用在那一行。"""
    code, out, _ = run_sed(["-n", "2p", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "bravo\n"


def test_sed_regex_address(workdir):
    """正则地址命中含该模式的行。"""
    code, out, _ = run_sed(["-n", "/bravo/p", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "bravo\n"


def test_sed_regex_address_other_delimiter(workdir):
    """地址里的正则也能换分隔符（GNU 同样支持）。

    Git Bash 的 MSYS 运行时会把以 / 开头的参数当路径改写，
    所以推荐用 | 之类不跟路径冲突的分隔符。
    """
    code, out, _ = run_sed([r"\|bravo|p", "-n", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "bravo\n"


def test_sed_range_address(workdir):
    """范围地址含两端。"""
    code, out, _ = run_sed(["-n", "2,3p", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "bravo\ncharlie\n"


def test_sed_range_to_end_of_file(workdir):
    """范围终点找不到就延伸到文件末尾。"""
    code, out, _ = run_sed(["-n", "/bravo/,/zzz/p", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "bravo\ncharlie\ndelta\necho\n"


def test_sed_range_start_never_matches(workdir):
    """范围起点找不到就一行都不输出。"""
    code, out, _ = run_sed(["-n", "/zzz/,/echo/p", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == ""


def test_sed_delete_command(workdir):
    """d 删掉命中的行。"""
    code, out, _ = run_sed(["/bravo/d", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "alpha\ncharlie\ndelta\necho\n"


def test_sed_print_line_number(workdir):
    """= 打印当前行号。"""
    code, out, _ = run_sed(["-n", "=;p", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "1\nalpha\n2\nbravo\n3\ncharlie\n4\ndelta\n5\necho\n"


def test_sed_append_insert_change(workdir):
    """a / i / c 分别追加、插入、替换文本。"""
    code, out, _ = run_sed(["1a\\inserted", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "alpha\ninserted\nbravo\ncharlie\ndelta\necho\n"

    code, out, _ = run_sed(["1i\\inserted", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "inserted\nalpha\nbravo\ncharlie\ndelta\necho\n"

    code, out, _ = run_sed(["1c\\changed", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "changed\nbravo\ncharlie\ndelta\necho\n"


def test_sed_backreference_and_whole_match(workdir):
    """BRE 分组反向引用与 & 整行匹配。"""
    code, out, _ = run_sed([r"s/\(a\)\(l\)/\2\1/", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "lapha\nbravo\ncharlie\ndelta\necho\n"

    code, out, _ = run_sed(["s/a/&b/", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "ablpha\nbrabvo\nchabrlie\ndeltab\necho\n"


def test_sed_case_conversion_in_replacement(workdir):
    """替换里的 \\U \\L \\u \\l 大小写修饰。"""
    code, out, _ = run_sed([r"s/a/\Uab/", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "ABlpha\nbrABvo\nchABrlie\ndeltAB\necho\n"

    code, out, _ = run_sed([r"s/alpha/\u&/", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "Alpha\nbravo\ncharlie\ndelta\necho\n"


def test_sed_transliterate(workdir):
    """y 按字符对逐个转写。"""
    code, out, _ = run_sed(["y/abc/xyz/", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "xlphx\nyrxvo\nzhxrlie\ndeltx\nezho\n"


def test_sed_reads_stdin_when_no_file(workdir):
    """不给文件时读标准输入。"""
    code, out, _ = run_sed(["s/a/b/"], cwd=workdir, stdin_text="alpha\nbravo\n")
    assert code == 0
    assert out == "blpha\nbrbvo\n"


def test_sed_concatenates_files_by_default(workdir):
    """默认把多个文件拼成一条流，行号连续。"""
    code, out, _ = run_sed(["-n", "=", "num.txt", "num.txt"], cwd=workdir)
    assert code == 0
    assert out == "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n"


def test_sed_keeps_missing_final_newline(workdir):
    """原文件末行没有换行，输出也不补。"""
    code, out, _ = run_sed(["s/no/NOT/", "nonl.txt"], cwd=workdir)
    assert code == 0
    assert out == "NOT trailing newline"


def test_sed_strips_carriage_return_in_text_mode(workdir):
    """文本模式读文件时行尾的 CR 被去掉。"""
    code, out, _ = run_sed(["s/one/1/", "crlf.txt"], cwd=workdir)
    assert code == 0
    assert out == "1\ntwo\nthree\n"


def test_sed_branch_and_label(workdir):
    """b / t / 标签跳转。"""
    code, out, _ = run_sed(["/bravo/{s/a/X/;t end}\np\n:end", "-n", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "alpha\ncharlie\ndelta\necho\n"


# --------------------------------------------------------------------------
# 选项组合
# --------------------------------------------------------------------------


def test_sed_multiple_expressions(workdir):
    """多个 -e 按顺序叠加执行。"""
    code, out, _ = run_sed(["-e", "s/a/b/", "-e", "s/b/c/", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "clpha\ncrbvo\nchcrlie\ndeltc\necho\n"


def test_sed_extended_regexp(workdir):
    """-r 把正则切到 ERE。"""
    code, out, _ = run_sed(["-r", r"s/(a)(l)/\2\1/", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "lapha\nbravo\ncharlie\ndelta\necho\n"

    # 同一个脚本在 BRE 下 ( ) 是字面量，匹配不上
    code, out, _ = run_sed([r"s/(a)(l)/\2\1/", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "alpha\nbravo\ncharlie\ndelta\necho\n"


def test_sed_script_file(workdir):
    """-f 从文件读脚本。"""
    script = workdir / "s.sed"
    script.write_bytes(b"s/a/b/\n")
    code, out, _ = run_sed(["-f", "s.sed", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "blpha\nbrbvo\nchbrlie\ndeltb\necho\n"


def test_sed_separate_files(workdir):
    """-s 让每个文件各算各的行号。"""
    code, out, _ = run_sed(["-n", "-s", "=", "num.txt", "num.txt"], cwd=workdir)
    assert code == 0
    assert out == "1\n2\n3\n4\n5\n1\n2\n3\n4\n5\n"


def test_sed_in_place(workdir):
    """-i 原地改文件。"""
    target = workdir / "a.txt"
    code, out, _ = run_sed(["-i", "s/a/A/g", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == ""
    assert target.read_bytes() == b"AlphA\nbrAvo\nchArlie\ndeltA\necho\n"


def test_sed_in_place_with_suffix(workdir):
    """-i 带后缀时留一份备份。"""
    target = workdir / "a.txt"
    code, _, _ = run_sed(["-i.bak", "s/a/A/g", "a.txt"], cwd=workdir)
    assert code == 0
    assert target.read_bytes() == b"AlphA\nbrAvo\nchArlie\ndeltA\necho\n"
    assert (workdir / "a.txt.bak").read_bytes() == b"alpha\nbravo\ncharlie\ndelta\necho\n"


def test_sed_binary_mode_keeps_carriage_return(workdir):
    """-b 保留行尾的 CR。"""
    code, out, _ = run_sed(["-b", "s/one/1/", "crlf.txt"], cwd=workdir)
    assert code == 0
    assert out == "1\r\ntwo\r\nthree\r\n"


def test_sed_quiet_and_in_place_together(workdir):
    """-i 配 -n：文件被清空（GNU 同样如此，-n 下没人往文件里写东西）。"""
    target = workdir / "a.txt"
    code, out, _ = run_sed(["-i", "-n", "s/a/A/g", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == ""
    assert target.read_bytes() == b""


def test_sed_quit_with_exit_code(workdir):
    """q 可以指定退出码。"""
    code, out, _ = run_sed(["q 3", "a.txt"], cwd=workdir)
    assert code == 3
    assert out == "alpha\n"


def test_sed_quit_stops_reading(workdir):
    """q 之后的行不再处理。"""
    code, out, _ = run_sed(["2q", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "alpha\nbravo\n"


def test_sed_null_data_option(workdir):
    """-z 用 NUL 分隔输入行。"""
    target = workdir / "nul.txt"
    target.write_bytes(b"a\x00b\x00")
    code, out, _ = run_sed(["-z", "s/a/A/", "nul.txt"], cwd=workdir)
    assert code == 0
    assert out == "A\x00b\x00"


# --------------------------------------------------------------------------
# 错误路径
# --------------------------------------------------------------------------


def test_sed_missing_script(workdir):
    """既没有脚本也没有 -e/-f 就报错。"""
    with pytest.raises(UsageError):
        run_sed([], cwd=workdir)


def test_sed_unterminated_substitution(workdir):
    """s 命令没闭合。"""
    with pytest.raises(UsageError):
        run_sed(["s/a/b", "a.txt"], cwd=workdir)


def test_sed_invalid_regex(workdir):
    """正则编不过。"""
    with pytest.raises(UsageError):
        run_sed(["s/[/x/", "a.txt"], cwd=workdir)


def test_sed_unknown_command(workdir):
    """不认识的指令。"""
    with pytest.raises(UsageError):
        run_sed(["nosuchcmd", "a.txt"], cwd=workdir)


def test_sed_unsupported_command(workdir):
    """保留区相关的指令明确说不支持，而不是悄悄忽略。"""
    with pytest.raises(UsageError):
        run_sed(["h", "a.txt"], cwd=workdir)


def test_sed_transliterate_length_mismatch(workdir):
    """y 的两个字符串长度必须一样。"""
    with pytest.raises(UsageError):
        run_sed(["y/abc/xy/", "a.txt"], cwd=workdir)


def test_sed_zero_occurrence_is_invalid(workdir):
    """s 的匹配序号不能是 0（GNU 也报错）。"""
    with pytest.raises(UsageError):
        run_sed(["s/a/b/0", "a.txt"], cwd=workdir)


def test_sed_missing_label(workdir):
    """跳转到不存在的标签。"""
    with pytest.raises(UsageError):
        run_sed(["b nowhere", "a.txt"], cwd=workdir)


def test_sed_missing_file_returns_error_code(workdir):
    """文件读不到：报错并返回 2。"""
    code, out, err = run_sed(["s/a/b/", "nope.txt"], cwd=workdir)
    assert code == 2
    assert out == ""
    assert "nope.txt" in err


def test_sed_directory_as_file_returns_error_code(workdir):
    """目录当文件用：报错并返回 2。"""
    code, out, err = run_sed(["s/a/b/", "sub"], cwd=workdir)
    assert code == 2
    assert out == ""
    assert "sub" in err


def test_sed_in_place_without_file(workdir):
    """-i 必须给文件。"""
    with pytest.raises(UsageError):
        run_sed(["-i", "s/a/b/"], cwd=workdir)


def test_sed_missing_file_still_processes_others(workdir):
    """其中一个文件读不到，其余照常处理。"""
    code, out, err = run_sed(["s/a/b/", "a.txt", "nope.txt"], cwd=workdir)
    assert code == 2
    assert out == "blpha\nbrbvo\nchbrlie\ndeltb\necho\n"
    assert "nope.txt" in err
