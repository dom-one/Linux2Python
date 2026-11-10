"""tree 指令的测试。

覆盖三块：正常路径、选项组合、错误路径。

语义基线来自 GNU tree 2.3.x 上游源码（tree.c / list.c / unix.c / color.c）：
本机没有 GNU tree 可做差分对照，所以断言按源码里的规则写死：

- 连接符：非最后一个兄弟用「├── 」，最后一个用「└── 」
- 祖先层后面还有兄弟才画竖线，竖线是「│」加两个不换行空格再加一个普通空格
- 末尾统计行前有一个空行，数目为 1 时用单数（1 directory / 1 file）
- 根目录里一个条目都没有时，它本身不计入目录数
- -t 按修改时间排序是旧的在前（与 ls -t 相反）
"""

import os
import re
import time

import pytest

from conftest import run_tree
from w2l.errors import UsageError

# GNU 的 UTF-8 画线字符：竖线后面跟的是不换行空格（U+00A0）
BRANCH = "├── "
LAST = "└── "
PIPE = "│\u00a0\u00a0 "
BLANK = "    "


@pytest.fixture
def tree(tmp_path):
    """一棵小树：三个文件、一个隐藏文件、一个子目录（子目录里两个文件）。"""
    (tmp_path / "a.txt").write_bytes(b"hello\n")
    (tmp_path / "B.txt").write_bytes(b"upper\n")
    (tmp_path / "notes.md").write_bytes(b"# t\n")
    (tmp_path / ".hidden").write_bytes(b"x\n")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.txt").write_bytes(b"deep\n")
    (sub / "code.py").write_bytes(b"print(1)\n")
    return tmp_path


# --------------------------------------------------------------------------
# 正常路径
# --------------------------------------------------------------------------


def test_tree_default_layout(tree):
    """默认输出：根目录一行 + 按名字排序的树 + 末尾统计行。"""
    code, out, err = run_tree(["."], cwd=tree)
    assert code == 0
    assert err == ""
    assert out == (
        ".\n"
        + BRANCH + "B.txt\n"
        + BRANCH + "a.txt\n"
        + BRANCH + "notes.md\n"
        + LAST + "sub\n"
        + BLANK + BRANCH + "code.py\n"
        + BLANK + LAST + "deep.txt\n"
        + "\n2 directories, 5 files\n"
    )


def test_tree_report_counts_root_and_subdirs(tree):
    """统计行：根目录算一个目录，数目为 1 时用单数。"""
    code, out, err = run_tree(["."], cwd=tree)
    assert code == 0
    assert out.endswith("\n2 directories, 5 files\n")


def test_tree_empty_directory_is_not_counted(tmp_path):
    """空目录：GNU 连根目录本身都不计入目录数。"""
    empty = tmp_path / "empty"
    empty.mkdir()
    code, out, err = run_tree(["empty"], cwd=tmp_path)
    assert code == 0
    assert err == ""
    assert out == "empty\n\n0 directories, 0 files\n"


def test_tree_single_file_uses_singular_report(tmp_path):
    """只有一个文件时，统计行用单数 file。"""
    (tmp_path / "only.txt").write_bytes(b"x\n")
    code, out, err = run_tree(["."], cwd=tmp_path)
    assert code == 0
    assert out.endswith("\n1 directory, 1 file\n")


def test_tree_multiple_operands_share_one_report(tmp_path):
    """多个操作数：各自成树，末尾只有一行合计统计。"""
    (tmp_path / "one").mkdir()
    (tmp_path / "one" / "x.txt").write_bytes(b"x\n")
    (tmp_path / "two").mkdir()
    code, out, err = run_tree(["one", "two"], cwd=tmp_path)
    assert code == 0
    # "two" 是空目录，按 GNU 的口径连它自己都不计入目录数
    assert out == (
        "one\n"
        + LAST + "x.txt\n"
        + "two\n"
        + "\n1 directory, 1 file\n"
    )


def test_tree_hides_dotfiles_by_default(tree):
    """默认不列隐藏文件。"""
    code, out, err = run_tree(["."], cwd=tree)
    assert code == 0
    assert ".hidden" not in out


def test_tree_never_shows_dot_and_dotdot(tree):
    """跟 ls -a 不同：. 与 .. 永远不列。"""
    code, out, err = run_tree(["-a", "."], cwd=tree)
    assert code == 0
    assert "\n. \n" not in out
    assert ".." not in out


# --------------------------------------------------------------------------
# 选项组合
# --------------------------------------------------------------------------


def test_tree_a_shows_dotfiles(tree):
    """-a 把隐藏文件也列出来。"""
    code, out, err = run_tree(["-a", "."], cwd=tree)
    assert code == 0
    assert BRANCH + ".hidden\n" in out
    assert out.endswith("\n2 directories, 6 files\n")


def test_tree_level_limits_depth(tree):
    """-L N：根目录往下最多 N 层，到层的目录不再展开。"""
    code, out, err = run_tree(["-L", "1", "."], cwd=tree)
    assert code == 0
    assert out == (
        ".\n"
        + BRANCH + "B.txt\n"
        + BRANCH + "a.txt\n"
        + BRANCH + "notes.md\n"
        + LAST + "sub\n"
        + "\n2 directories, 3 files\n"
    )


def test_tree_level_two_expands_subdir(tree):
    """-L 2：子目录展开一层，但它的子目录不再展开。"""
    code, out, err = run_tree(["-L", "2", "."], cwd=tree)
    assert code == 0
    assert BLANK + BRANCH + "code.py\n" in out
    assert out.endswith("\n2 directories, 5 files\n")


def test_tree_dirs_only(tree):
    """-d 只列目录，统计行也只有目录数。"""
    code, out, err = run_tree(["-d", "."], cwd=tree)
    assert code == 0
    assert out == (
        ".\n"
        + LAST + "sub\n"
        + "\n2 directories\n"
    )


def test_tree_fullpath(tree):
    """-f 给每个条目打完整路径。"""
    code, out, err = run_tree(["-f", "."], cwd=tree)
    assert code == 0
    assert BRANCH + "./B.txt\n" in out
    assert BLANK + BRANCH + "./sub/code.py\n" in out


def test_tree_no_indent(tree):
    """-i 不画缩进线，只打名字。"""
    code, out, err = run_tree(["-i", "."], cwd=tree)
    assert code == 0
    assert "├──" not in out
    assert "code.py\n" in out


def test_tree_ascii_charset(tree):
    """--charset=ascii 用 ASCII 画线字符。"""
    code, out, err = run_tree(["--charset=ascii", "."], cwd=tree)
    assert code == 0
    assert "|-- B.txt\n" in out
    assert "`-- sub\n" in out
    assert "│" not in out


def test_tree_dirsfirst(tree):
    """--dirsfirst 把目录提到文件前面。"""
    code, out, err = run_tree(["--dirsfirst", "."], cwd=tree)
    assert code == 0
    # 第一层的条目直接以连接符开头；更深层的行以竖线或空格开头
    level1 = [
        line.rsplit("── ", 1)[-1]
        for line in out.splitlines()[1:]
        if line.startswith(BRANCH) or line.startswith(LAST)
    ]
    assert level1 == ["sub", "B.txt", "a.txt", "notes.md"]


def test_tree_reverse(tree):
    """-r 把排序结果整体反向。"""
    code, out, err = run_tree(["-r", "."], cwd=tree)
    assert code == 0
    assert out.startswith(".\n" + BRANCH + "sub\n")
    assert out.endswith(LAST + "B.txt\n\n2 directories, 5 files\n")


def test_tree_ignore_pattern(tree):
    """-I 把匹配的条目整个去掉（目录被去掉时它的内容也不列）。"""
    code, out, err = run_tree(["-I", "*.txt", "."], cwd=tree)
    assert code == 0
    assert "a.txt" not in out
    assert "deep.txt" not in out
    assert BRANCH + "notes.md\n" in out
    assert out.endswith("\n2 directories, 2 files\n")


def test_tree_ignore_pattern_is_case_sensitive(tree):
    """默认区分大小写，--ignore-case 才忽略。"""
    code, out, err = run_tree(["-I", "*.TXT", "."], cwd=tree)
    assert code == 0
    assert "a.txt" in out
    code, out, err = run_tree(["-I", "*.TXT", "--ignore-case", "."], cwd=tree)
    assert code == 0
    assert "a.txt" not in out


def test_tree_pattern_keeps_only_matching_files(tree):
    """-P 只列匹配的文件，目录照旧列出。"""
    code, out, err = run_tree(["-P", "*.txt", "."], cwd=tree)
    assert code == 0
    assert "notes.md" not in out
    assert "code.py" not in out
    assert BRANCH + "a.txt\n" in out
    assert BLANK + LAST + "deep.txt\n" in out
    assert out.endswith("\n2 directories, 3 files\n")


def test_tree_size_column(tree):
    """-s 打出字节数，列宽 11 右对齐（前面再加一个空格）。"""
    code, out, err = run_tree(["-s", "."], cwd=tree)
    assert code == 0
    assert BRANCH + " " + f"{6:>11d}" + "a.txt\n" in out


def test_tree_human_readable_size(tmp_path):
    """-h 隐含 -s，并且按 1024 进制带单位。"""
    (tmp_path / "big.bin").write_bytes(b"z" * 2048)
    code, out, err = run_tree(["-h", "."], cwd=tmp_path)
    assert code == 0
    assert " 2.0K" in out


def test_tree_permissions_column(tree):
    """-p 打出权限位，目录与文件类型字符不同。"""
    code, out, err = run_tree(["-p", "."], cwd=tree)
    assert code == 0
    assert re.search(r"d[-rwx]{9}", out)
    assert re.search(r"-[-rwx]{9}", out)


def test_tree_date_column(tmp_path):
    """-D 打修改时间：半年以内显示时刻，更早显示年份。"""
    old = tmp_path / "old.txt"
    old.write_bytes(b"x\n")
    os.utime(old, (1_600_000_000, 1_600_000_000))
    code, out, err = run_tree(["-D", "."], cwd=tmp_path)
    assert code == 0
    assert "2020" in out


def test_tree_classify_marks_directories(tree):
    """-F 给目录名追加 /。"""
    code, out, err = run_tree(["-F", "."], cwd=tree)
    assert code == 0
    assert LAST + "sub/\n" in out
    assert BRANCH + "notes.md\n" in out


def test_tree_noreport(tree):
    """--noreport 不打末尾的统计行。"""
    code, out, err = run_tree(["--noreport", "."], cwd=tree)
    assert code == 0
    assert "directories" not in out
    assert out.endswith("deep.txt\n")


def test_tree_sort_by_mtime_oldest_first(tmp_path):
    """-t 按修改时间排序，旧的在前。"""
    for name, stamp in (("new.txt", 3000), ("mid.txt", 2000), ("old.txt", 1000)):
        target = tmp_path / name
        target.write_bytes(b"x\n")
        os.utime(target, (stamp, stamp))
    code, out, err = run_tree(["-t", "."], cwd=tmp_path)
    assert code == 0
    order = [line.rsplit(" ", 1)[-1] for line in out.splitlines()[1:4]]
    assert order == ["old.txt", "mid.txt", "new.txt"]


def test_tree_unsorted_lists_everything(tree):
    """-U 不排序，但条目一个不少。"""
    code, out, err = run_tree(["-U", "."], cwd=tree)
    assert code == 0
    for name in ("B.txt", "a.txt", "notes.md", "sub", "code.py", "deep.txt"):
        assert name in out


def test_tree_combined_options(tree):
    """选项组合：-a 与 -L 1 一起用。"""
    code, out, err = run_tree(["-a", "-L", "1", "."], cwd=tree)
    assert code == 0
    assert ".hidden" in out
    assert "code.py" not in out
    assert out.endswith("\n2 directories, 4 files\n")


def test_tree_dirs_and_level_combined(tree):
    """选项组合：-d 与 -L 1 一起用，只列目录且不展开。"""
    code, out, err = run_tree(["-d", "-L", "1", "."], cwd=tree)
    assert code == 0
    assert out == ".\n" + LAST + "sub\n" + "\n2 directories\n"


# --------------------------------------------------------------------------
# 错误路径
# --------------------------------------------------------------------------


def test_tree_missing_path_is_an_error(tmp_path):
    """路径不存在：报错并返回退出码 2。"""
    code, out, err = run_tree(["nope"], cwd=tmp_path)
    assert code == 2
    assert "无法访问" in err
    assert "'nope'" in err


def test_tree_file_operand_is_an_error(tmp_path):
    """操作数是文件而不是目录：报错并返回退出码 2。"""
    (tmp_path / "a.txt").write_bytes(b"x\n")
    code, out, err = run_tree(["a.txt"], cwd=tmp_path)
    assert code == 2
    assert "不是目录" in err


def test_tree_level_zero_is_a_usage_error(tree):
    """-L 0 非法（GNU 也报错）。"""
    with pytest.raises(UsageError):
        run_tree(["-L", "0", "."], cwd=tree)


def test_tree_unknown_charset_is_a_usage_error(tree):
    """不认识的字符集报错。"""
    with pytest.raises(UsageError):
        run_tree(["--charset=gbk", "."], cwd=tree)


def test_tree_non_numeric_level_is_rejected(tree):
    """-L 的参数不是数字时由 argparse 拦下。"""
    with pytest.raises(SystemExit):
        run_tree(["-L", "abc", "."], cwd=tree)
