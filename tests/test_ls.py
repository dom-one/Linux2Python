"""ls 指令测试。

对照的是 Git Bash 里 GNU coreutils 的 ls 实测输出：
默认按名字排序、隐藏文件默认不列、-a/-A 的差别、-l 长格式四列、
-t/-S 排序、-r 反序、-F 类型标记、-R 递归分块、多操作数时文件先于目录块。
"""

import os
import re

import pytest

from conftest import run_ls


@pytest.fixture
def ls_tree(tmp_path):
    (tmp_path / "alpha.txt").write_text("hello\n", encoding="utf-8")
    (tmp_path / "Beta.txt").write_text("B\n", encoding="utf-8")
    (tmp_path / "gamma.log").write_text("x" * 2048, encoding="utf-8")
    (tmp_path / "big.bin").write_bytes(b"\x00" * 5000)
    (tmp_path / ".hidden").write_text("h\n", encoding="utf-8")
    (tmp_path / "run.bat").write_text("@echo off\n", encoding="ascii")
    (tmp_path / "empty").mkdir()
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.txt").write_text("deep\n", encoding="utf-8")
    nested = sub / "nested"
    nested.mkdir()
    (nested / "leaf.txt").write_text("leaf\n", encoding="utf-8")
    return tmp_path


# ---------- 正常路径 ----------


def test_lists_entries_sorted_by_name(ls_tree):
    code, out, err = run_ls([str(ls_tree)])
    assert code == 0
    assert out == "Beta.txt\nalpha.txt\nbig.bin\nempty\ngamma.log\nrun.bat\nsub\n"
    assert err == ""


def test_default_path_is_current_directory(ls_tree):
    code, out, _ = run_ls([], cwd=ls_tree)
    assert code == 0
    assert "alpha.txt" in out


def test_hidden_file_not_listed_by_default(ls_tree):
    _, out, _ = run_ls([str(ls_tree)])
    assert ".hidden" not in out.splitlines()


def test_all_includes_dot_entries_and_hidden(ls_tree):
    _, out, _ = run_ls(["-a", str(ls_tree)])
    lines = out.splitlines()
    assert lines[0] == "."
    assert lines[1] == ".."
    assert ".hidden" in lines


def test_almost_all_excludes_dot_entries(ls_tree):
    _, out, _ = run_ls(["-A", str(ls_tree)])
    lines = out.splitlines()
    assert "." not in lines
    assert ".." not in lines
    assert ".hidden" in lines


def test_file_operand_lists_only_its_name(ls_tree):
    code, out, _ = run_ls([str(ls_tree / "alpha.txt")])
    assert code == 0
    assert out.strip().endswith("alpha.txt")
    assert "hello" not in out


def test_directory_option_lists_directory_itself(ls_tree):
    code, out, _ = run_ls(["-d", str(ls_tree / "sub")])
    assert code == 0
    assert out.strip().endswith("sub")
    assert "deep.txt" not in out


# ---------- 选项组合 ----------


def test_long_format_columns(ls_tree):
    code, out, _ = run_ls(["-l", str(ls_tree / "alpha.txt")])
    assert code == 0
    line = out.strip()
    size = os.path.getsize(ls_tree / "alpha.txt")
    name = re.escape(str(ls_tree / "alpha.txt"))
    assert re.match(rf"^-rw[rwx-]{{7}}\s+{size}\s+\S{{3}}\s+\d{{1,2}}\s+(\d{{2}}:\d{{2}}|\d{{4}})\s+{name}$", line)


def test_long_format_aligns_size_column(ls_tree):
    _, out, _ = run_ls(["-l", str(ls_tree)])
    columns = [
        re.match(r"^[-dlps][rwx-]{9}(\s*\S+) ", line).group(1)
        for line in out.splitlines()
    ]
    assert columns
    assert len({len(column) for column in columns}) == 1


def test_human_readable_size(ls_tree):
    _, out, _ = run_ls(["-lh", str(ls_tree / "gamma.log")])
    assert "2.0K" in out


def test_h_is_human_readable_not_help(ls_tree):
    """GNU 的 -h 是 --human-readable，不能被 argparse 的帮助选项吃掉。"""
    code, out, _ = run_ls(["-lh", str(ls_tree / "gamma.log")])
    assert code == 0
    assert "2.0K" in out
    assert "用法" not in out


def test_classify_marks_directories(ls_tree):
    _, out, _ = run_ls(["-F", str(ls_tree)])
    lines = out.splitlines()
    assert "sub/" in lines
    assert "empty/" in lines
    assert "alpha.txt" in lines


def test_long_format_with_classify(ls_tree):
    _, out, _ = run_ls(["-lF", str(ls_tree)])
    assert any(line.endswith("sub/") for line in out.splitlines())


def test_sort_by_time(ls_tree):
    for name in ("gamma.log", "big.bin", "run.bat", "empty", "sub"):
        os.utime(ls_tree / name, (1_000_000, 1_000_000))
    os.utime(ls_tree / "Beta.txt", (2_000_000, 2_000_000))
    os.utime(ls_tree / "alpha.txt", (3_000_000, 3_000_000))
    _, out, _ = run_ls(["-t", str(ls_tree)])
    assert out.splitlines() == [
        "alpha.txt",
        "Beta.txt",
        "big.bin",
        "empty",
        "gamma.log",
        "run.bat",
        "sub",
    ]


def test_sort_by_size(ls_tree):
    _, out, _ = run_ls(["-S", str(ls_tree)])
    assert out.splitlines()[0] == "big.bin"


def test_reverse_flips_default_order(ls_tree):
    _, forward, _ = run_ls([str(ls_tree)])
    _, backward, _ = run_ls(["-r", str(ls_tree)])
    assert backward.splitlines() == list(reversed(forward.splitlines()))


def test_recursive_writes_headers_per_level(ls_tree):
    code, out, _ = run_ls(["-R", str(ls_tree)])
    assert code == 0
    assert f"{ls_tree}:" in out
    assert f"{ls_tree}/sub:" in out
    assert f"{ls_tree}/sub/nested:" in out
    assert "deep.txt" in out
    assert "leaf.txt" in out


def test_multiple_operands_put_files_before_directory_block(ls_tree):
    code, out, _ = run_ls(
        [str(ls_tree / "gamma.log"), str(ls_tree / "alpha.txt"), str(ls_tree / "sub")]
    )
    assert code == 0
    # GNU 把普通文件统一排序后先输出，再输出目录块
    assert out.startswith(f"{ls_tree / 'alpha.txt'}\n{ls_tree / 'gamma.log'}\n")
    assert f"{ls_tree / 'sub'}:" in out
    assert "deep.txt" in out


def test_blocks_are_separated_by_blank_line(ls_tree):
    _, out, _ = run_ls([str(ls_tree / "alpha.txt"), str(ls_tree / "sub")])
    assert out == f"{ls_tree / 'alpha.txt'}\n\n{ls_tree / 'sub'}:\ndeep.txt\nnested\n"


# ---------- 错误路径 ----------


def test_missing_path_reports_error_and_exits_two(ls_tree):
    code, out, err = run_ls([str(ls_tree / "nope")])
    assert code == 2
    assert out == ""
    assert "nope" in err


def test_error_does_not_stop_other_operands(ls_tree):
    code, out, err = run_ls([str(ls_tree / "nope"), str(ls_tree / "alpha.txt")])
    assert code == 2
    assert "alpha.txt" in out
    assert err.strip() != ""


def test_empty_directory_has_no_result(ls_tree):
    code, out, err = run_ls([str(ls_tree / "empty")])
    assert code == 1
    assert out == ""
    assert err == ""


def test_help_flag_exits_zero(capsys):
    with pytest.raises(SystemExit) as excinfo:
        run_ls(["--help"])
    assert excinfo.value.code == 0
    assert "列出目录内容" in capsys.readouterr().out
