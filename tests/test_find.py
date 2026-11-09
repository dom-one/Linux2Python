"""find 指令的测试。

覆盖三块：正常路径、选项组合、错误路径。
语义基线来自 Git Bash 的 GNU find 4.10.0 实测（差分对照脚本在 AI/脚本/ 下）。

两个容易踩的约定：

- 语料用 write_bytes 写，不��� write_text：Windows 上文本模式会把 \\n 翻成 \\r\\n，
  字节数会多 1，-size 的断言就会对不上。
- 打印出来的路径用正斜杠（跟 GNU 一致），比较时要先把期望值也换成正斜杠。
"""

import os
import time

import pytest

from conftest import run_find


def p(path):
    """把路径换成本实现（与 GNU 一致）的正斜杠显示形式。"""
    return str(path).replace("\\", "/")


@pytest.fixture
def tree(tmp_path):
    """一棵小树：两个文件、一个空文件、一个隐藏文件、一个子目录。"""
    (tmp_path / "a.txt").write_bytes(b"hello\n")
    (tmp_path / "B.txt").write_bytes(b"upper\n")
    (tmp_path / "notes.md").write_bytes(b"# t\n")
    (tmp_path / "empty.log").write_bytes(b"")
    (tmp_path / ".hidden").write_bytes(b"x\n")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.txt").write_bytes(b"deep\n")
    (sub / "code.py").write_bytes(b"print(1)\n")
    return tmp_path


def lines(text):
    return [line for line in text.splitlines() if line]


def names(text):
    return {line.rsplit("/", 1)[-1] for line in lines(text)}


# --------------------------------------------------------------------------
# 正常路径
# --------------------------------------------------------------------------


def test_find_without_expression_prints_everything(tree):
    code, out, err = run_find([str(tree)], cwd=tree)
    assert code == 0
    assert err == ""
    found = lines(out)
    assert p(tree) in found
    assert p(tree / "a.txt") in found
    assert p(tree / "sub" / "deep.txt") in found
    # 树本身 + 5 个条目 + sub 目录 + sub 里的两个文件
    assert len(found) == 9


def test_find_by_name(tree):
    code, out, err = run_find([str(tree), "-name", "*.txt"], cwd=tree)
    assert code == 0
    assert names(out) == {"a.txt", "B.txt", "deep.txt"}


def test_find_name_is_case_sensitive(tree):
    code, out, err = run_find([str(tree), "-name", "*.TXT"], cwd=tree)
    assert code == 1
    assert out == ""


def test_find_iname_ignores_case(tree):
    code, out, err = run_find([str(tree), "-iname", "*.TXT"], cwd=tree)
    assert code == 0
    assert names(out) == {"a.txt", "B.txt", "deep.txt"}


def test_find_by_type(tree):
    code, out, err = run_find([str(tree), "-type", "d"], cwd=tree)
    assert code == 0
    found = names(out)
    assert "sub" in found
    assert "a.txt" not in found


def test_find_type_f_lists_only_files(tree):
    code, out, err = run_find([str(tree), "-type", "f"], cwd=tree)
    assert code == 0
    assert p(tree / "sub") not in lines(out)
    assert p(tree / "a.txt") in lines(out)


def test_find_empty_matches_empty_file_only(tree):
    code, out, err = run_find([str(tree), "-empty"], cwd=tree)
    assert code == 0
    assert names(out) == {"empty.log"}


def test_find_size_counts_blocks(tree):
    # 6 字节的文件占 1 个 512 字节块
    code, out, err = run_find([str(tree), "-size", "1"], cwd=tree)
    assert code == 0
    found = names(out)
    assert "a.txt" in found
    assert "empty.log" not in found


def test_find_size_with_c_suffix_is_exact_bytes(tree):
    code, out, err = run_find([str(tree), "-size", "6c"], cwd=tree)
    assert code == 0
    assert names(out) == {"a.txt", "B.txt"}


def test_find_size_greater_than(tree):
    code, out, err = run_find([str(tree), "-size", "+6c"], cwd=tree)
    assert code == 0
    assert names(out) == {"code.py"}


def test_find_regex(tree):
    code, out, err = run_find([str(tree), "-regex", ".*\\.md$"], cwd=tree)
    assert code == 0
    assert names(out) == {"notes.md"}


def test_find_print0_uses_nul_separator(tree):
    code, out, err = run_find([str(tree), "-name", "*.md", "-print0"], cwd=tree)
    assert code == 0
    assert out.endswith("\0")
    assert out.count("\0") == 1
    assert "\n" not in out


def test_find_printf_formats(tree):
    code, out, err = run_find([str(tree), "-name", "*.md", "-printf", "%f|%s|%y\n"], cwd=tree)
    assert code == 0
    assert out.strip() == "notes.md|4|f"


def test_find_returns_1_when_nothing_matches(tree):
    code, out, err = run_find([str(tree), "-name", "没有这个"], cwd=tree)
    assert code == 1
    assert out == ""


def test_find_default_path_is_current_directory(tree):
    code, out, err = run_find(["-name", "*.md"], cwd=tree)
    assert code == 0
    assert lines(out) == ["./notes.md"]


def test_find_hidden_files_are_matched_by_wildcard(tree):
    code, out, err = run_find([str(tree), "-name", "*.txt"], cwd=tree)
    assert code == 0
    assert ".hidden" not in names(out)
    code, out, err = run_find([str(tree), "-name", "*"], cwd=tree)
    assert code == 0
    assert ".hidden" in names(out)


# --------------------------------------------------------------------------
# 选项组合
# --------------------------------------------------------------------------


def test_find_maxdepth_limits_depth(tree):
    code, out, err = run_find([str(tree), "-maxdepth", "1", "-type", "f"], cwd=tree)
    assert code == 0
    found = names(out)
    assert "deep.txt" not in found
    assert "a.txt" in found


def test_find_maxdepth_zero_only_root(tree):
    code, out, err = run_find([str(tree), "-maxdepth", "0"], cwd=tree)
    assert code == 0
    assert lines(out) == [p(tree)]


def test_find_mindepth_skips_root(tree):
    code, out, err = run_find([str(tree), "-mindepth", "1"], cwd=tree)
    assert code == 0
    assert p(tree) not in lines(out)


def test_find_or_expression(tree):
    code, out, err = run_find([str(tree), "-name", "*.md", "-o", "-name", "*.py"], cwd=tree)
    assert code == 0
    assert names(out) == {"notes.md", "code.py"}


def test_find_parentheses_group(tree):
    code, out, err = run_find(
        [str(tree), "(", "-name", "*.md", "-o", "-name", "*.py", ")", "-print"], cwd=tree
    )
    assert code == 0
    assert names(out) == {"notes.md", "code.py"}


def test_find_not_operator(tree):
    code, out, err = run_find([str(tree), "!", "-name", "*.txt"], cwd=tree)
    assert code == 0
    found = names(out)
    assert "a.txt" not in found
    assert "notes.md" in found


def test_find_prune_stops_descent(tree):
    code, out, err = run_find(
        [str(tree), "-type", "d", "-name", "sub", "-prune", "-o", "-print"], cwd=tree
    )
    assert code == 0
    found = names(out)
    assert "deep.txt" not in found
    assert "notes.md" in found


def test_find_prune_still_prints_the_pruned_directory(tree):
    # GNU 手册：表达式里除了 -prune 之外没有别的动作时，隐式 -print 仍然生效
    code, out, err = run_find([str(tree), "-type", "d", "-prune"], cwd=tree)
    assert code == 0
    assert lines(out) == [p(tree)]


def test_find_and_operator(tree):
    code, out, err = run_find([str(tree), "-name", "*.txt", "-a", "-size", "+0"], cwd=tree)
    assert code == 0
    assert names(out) == {"a.txt", "B.txt", "deep.txt"}


def test_find_multiple_paths(tree):
    code, out, err = run_find([str(tree / "sub"), str(tree / "notes.md"), "-name", "*.txt"], cwd=tree)
    assert code == 0
    assert lines(out) == [p(tree / "sub" / "deep.txt")]


def test_find_mtime_zero_matches_recent(tree):
    code, out, err = run_find([str(tree), "-type", "f", "-mtime", "0"], cwd=tree)
    assert code == 0
    assert "a.txt" in names(out)


def test_find_newer(tree):
    reference = tree / "a.txt"
    older = tree / "notes.md"
    stamp = time.time() - 3600
    os.utime(older, (stamp, stamp))
    code, out, err = run_find([str(tree), "-type", "f", "-newer", str(reference)], cwd=tree)
    assert code == 0
    found = names(out)
    assert "notes.md" not in found
    assert "deep.txt" in found


def test_find_delete_removes_matched_files(tmp_path):
    (tmp_path / "keep.txt").write_bytes(b"keep\n")
    (tmp_path / "drop.txt").write_bytes(b"drop\n")
    code, out, err = run_find([str(tmp_path), "-name", "drop.txt", "-delete"], cwd=tmp_path)
    # -delete 是动作不是打印，命中了就算有结果
    assert code == 0
    assert not (tmp_path / "drop.txt").exists()
    assert (tmp_path / "keep.txt").exists()


def test_find_depth_prints_children_before_parents(tree):
    code, out, err = run_find([str(tree), "-depth", "-type", "d"], cwd=tree)
    assert code == 0
    found = lines(out)
    assert found[-1] == p(tree)
    assert p(tree / "sub") in found


# --------------------------------------------------------------------------
# 错误路径
# --------------------------------------------------------------------------


def test_find_unknown_predicate_is_usage_error(tree):
    from w2l.errors import UsageError

    with pytest.raises(UsageError) as info:
        run_find([str(tree), "-没有这个谓词"], cwd=tree)
    assert "未知谓词" in str(info.value)


def test_find_missing_argument_is_usage_error(tree):
    from w2l.errors import UsageError

    with pytest.raises(UsageError) as info:
        run_find([str(tree), "-name"], cwd=tree)
    assert "缺少参数" in str(info.value)


def test_find_unclosed_parenthesis_is_usage_error(tree):
    from w2l.errors import UsageError

    with pytest.raises(UsageError) as info:
        run_find([str(tree), "(", "-name", "*.txt"], cwd=tree)
    assert "')'" in str(info.value)


def test_find_path_after_expression_is_usage_error(tree):
    from w2l.errors import UsageError

    with pytest.raises(UsageError) as info:
        run_find([str(tree), "-name", "*.txt", "多余的操作数"], cwd=tree)
    assert "路径必须写在表达式前面" in str(info.value)


def test_find_invalid_type_is_usage_error(tree):
    from w2l.errors import UsageError

    with pytest.raises(UsageError) as info:
        run_find([str(tree), "-type", "x"], cwd=tree)
    assert "-type" in str(info.value)


def test_find_missing_operand_reports_error(tree):
    code, out, err = run_find([str(tree / "没有这个目录")], cwd=tree)
    assert code == 2
    assert "无法访问" in err


def test_find_maxdepth_without_value_is_usage_error(tree):
    from w2l.errors import UsageError

    with pytest.raises(UsageError) as info:
        run_find([str(tree), "-maxdepth"], cwd=tree)
    assert "缺少参数" in str(info.value)
