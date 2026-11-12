"""du 指令的测试。

覆盖三块：正常路径、选项组合、错误路径。

语义基线来自 GNU coreutils 8.32 的 du（Git Bash 的 /usr/bin/du）实跑对照，
本实现默认按「表观大小」统计，对应 GNU 的 --apparent-size：

- 输出是「大小<TAB>路径」，目录排在它自己的内容后面（后序遍历）
- 目录自身按 0 算；文件按字节数算
- 默认块大小 1K，显示时把字节数向上取整到块；-b 按字节、-k/-m/-B 自定
- -a 连文件一起列，-s 每个操作数只给一行总数，-c 末尾再加一行 total
- -d N 只打印到第 N 层，统计照样算到底
- -t 的阈值跟字节数比，不是跟块数比；给负数则只显示不大于它的条目
- -h/--si 人类可读：尾数向上取整到一位小数，取整后达到 10 就改成整数
- 同一个文件只算一次（多个操作数覆盖同一棵树时，后来的那份不重复统计也不输出）
"""

import pytest

from conftest import run_du
from w2l.errors import UsageError


@pytest.fixture
def tree(tmp_path):
    """一棵小树：三个文件、一个空文件、一个空目录、一个两层子目录。

    字节数刻意选在 1024 的边界两侧：
    a.txt 10 字节、b.txt 2048 字节、c.txt 100 字节、zero.txt 0 字节、
    sub/d.txt 5 字节、sub/deeper/e.txt 4096 字节。
    整棵树合计 6259 字节，默认 1K 块下向上取整是 7 块。
    """
    root = tmp_path / "tree"
    root.mkdir()
    (root / "a.txt").write_bytes(b"A" * 10)
    (root / "b.txt").write_bytes(b"B" * 2048)
    (root / "c.txt").write_bytes(b"C" * 100)
    (root / "zero.txt").write_bytes(b"")
    (root / "empty").mkdir()
    sub = root / "sub"
    sub.mkdir()
    (sub / "d.txt").write_bytes(b"D" * 5)
    deeper = sub / "deeper"
    deeper.mkdir()
    (deeper / "e.txt").write_bytes(b"E" * 4096)
    return tmp_path


# --------------------------------------------------------------------------
# 正常路径
# --------------------------------------------------------------------------


def test_du_lists_directories_post_order(tree):
    """默认只列目录，且目录排在它自己的内容后面。"""
    code, out, err = run_du(["tree"], cwd=tree)
    assert code == 0
    assert err == ""
    # sub 在 deeper 之后，tree 在最后
    assert out.splitlines()[-1].endswith("tree")
    assert "tree/sub" in out
    assert "tree/sub/deeper" in out


def test_du_default_block_size_is_1k(tree):
    """默认块大小 1K，字节数向上取整到块。"""
    code, out, err = run_du(["-s", "tree"], cwd=tree)
    assert code == 0
    assert err == ""
    # 合计 6259 字节 -> ceil(6259 / 1024) = 7 块
    assert out == "7\ttree\n"


def test_du_bytes_option_gives_exact_size(tree):
    """-b 按字节显示，不取整。"""
    code, out, err = run_du(["-s", "-b", "tree"], cwd=tree)
    assert code == 0
    assert err == ""
    assert out == "6259\ttree\n"


def test_du_single_file_operand(tree):
    """操作数是文件时给它的字节数。"""
    code, out, err = run_du(["-b", "tree/b.txt"], cwd=tree)
    assert code == 0
    assert err == ""
    assert out == "2048\ttree/b.txt\n"


def test_du_directory_itself_counts_zero(tree):
    """目录自身按 0 算，所以空目录是 0。"""
    code, out, err = run_du(["-s", "tree/empty"], cwd=tree)
    assert code == 0
    assert err == ""
    assert out == "0\ttree/empty\n"


def test_du_default_operand_is_current_directory(tree):
    """不给操作数时统计当前目录。"""
    code, out, err = run_du(["-s"], cwd=tree)
    assert code == 0
    assert err == ""
    assert out == "7\t.\n"


def test_du_output_is_tab_separated(tree):
    """大小与路径之间是制表符，不是空格。"""
    code, out, err = run_du(["-s", "tree"], cwd=tree)
    assert code == 0
    assert "\t" in out
    assert " " not in out


# --------------------------------------------------------------------------
# 选项组合
# --------------------------------------------------------------------------


def test_du_all_lists_files_too(tree):
    """-a 连普通文件一起列。"""
    code, out, err = run_du(["-a", "tree"], cwd=tree)
    assert code == 0
    assert err == ""
    assert "tree/a.txt" in out
    assert "tree/zero.txt" in out
    assert "tree/sub/d.txt" in out


def test_du_total_adds_grand_total(tree):
    """-c 末尾多打一行 total。"""
    code, out, err = run_du(["-s", "-c", "tree"], cwd=tree)
    assert code == 0
    assert err == ""
    assert out == "7\ttree\n7\ttotal\n"


def test_du_max_depth_limits_printing_not_counting(tree):
    """-d 限制打印层数，但统计照样算到底。"""
    code, out, err = run_du(["-d", "1", "tree"], cwd=tree)
    assert code == 0
    assert err == ""
    # tree/sub 含 d.txt 与 deeper/e.txt，显示的仍是自己的总数
    assert "5\ttree/sub\n" in out
    # 更深的一层不打印
    assert "tree/sub/deeper" not in out
    # 根目录的总数没有因为少打印而变小
    assert "7\ttree\n" in out


def test_du_max_depth_zero_prints_only_root(tree):
    """-d 0 只打印操作数自己。"""
    code, out, err = run_du(["-d", "0", "tree"], cwd=tree)
    assert code == 0
    assert err == ""
    assert out == "7\ttree\n"


def test_du_threshold_keeps_big_entries(tree):
    """-t 跟字节数比：小于阈值的条目不显示。"""
    code, out, err = run_du(["-t", "1024", "-a", "tree"], cwd=tree)
    assert code == 0
    assert err == ""
    # a.txt 只有 10 字节，被滤掉；b.txt 有 2048 字节，留下
    assert "tree/a.txt" not in out
    assert "tree/b.txt" in out


def test_du_negative_threshold_keeps_small_entries(tree):
    """负阈值只留不大于它的条目。"""
    code, out, err = run_du(["-t", "-1024", "-a", "tree"], cwd=tree)
    assert code == 0
    assert err == ""
    assert "tree/a.txt" in out
    assert "tree/b.txt" not in out


def test_du_human_readable_rounds_up(tree):
    """-h 的尾数向上取整到一位小数。"""
    code, out, err = run_du(["-s", "-h", "tree"], cwd=tree)
    assert code == 0
    assert err == ""
    # 6259 字节 / 1024 = 6.115 -> 向上取整到一位小数是 6.2
    assert out == "6.2K\ttree\n"


def test_du_si_uses_1000_base(tree):
    """--si 用 1000 进制，单位字母是小写 k。"""
    code, out, err = run_du(["-s", "--si", "tree"], cwd=tree)
    assert code == 0
    assert err == ""
    # 6259 / 1000 = 6.259 -> 6.3
    assert out == "6.3k\ttree\n"


def test_du_block_size_option(tree):
    """-B 指定块大小，字节数向上取整到该块。"""
    code, out, err = run_du(["-s", "-B", "100", "tree"], cwd=tree)
    assert code == 0
    assert err == ""
    # ceil(6259 / 100) = 63
    assert out == "63\ttree\n"


def test_du_separate_dirs_excludes_subdirectories(tree):
    """-S 让目录大小不含子目录。"""
    code, out, err = run_du(["-s", "-S", "tree"], cwd=tree)
    assert code == 0
    assert err == ""
    # 只算 tree 里的文件：10 + 2048 + 100 + 0 = 2158 -> 3 块
    assert out == "3\ttree\n"


def test_du_same_tree_twice_is_counted_once(tree):
    """同一个目录被两个操作数覆盖时只算一次，第二次不输出。"""
    code, out, err = run_du(["tree", "tree"], cwd=tree)
    assert code == 0
    assert err == ""
    assert out.count("tree") == 4  # tree/empty、tree/sub/deeper、tree/sub、tree


def test_du_null_separator(tree):
    """-0 用 NUL 分隔输出。"""
    code, out, err = run_du(["-s", "-0", "tree"], cwd=tree)
    assert code == 0
    assert err == ""
    assert out == "7\ttree\x00"


def test_du_time_column(tree):
    """--time 多打一列最后修改时间。"""
    code, out, err = run_du(["-s", "--time", "tree"], cwd=tree)
    assert code == 0
    assert err == ""
    parts = out.strip().split("\t")
    assert len(parts) == 3
    assert parts[0] == "7"
    assert parts[2] == "tree"


def test_du_count_links_counts_twice(tree):
    """-l 让同一个文件被算两次，第二个操作数也会再给一份总数。"""
    code, out, err = run_du(["-s", "-l", "tree", "tree"], cwd=tree)
    assert code == 0
    assert err == ""
    # 两棵树各报一次自己的总数
    assert out == "7\ttree\n7\ttree\n"


# --------------------------------------------------------------------------
# 错误路径
# --------------------------------------------------------------------------


def test_du_missing_operand_is_error(tree):
    """操作数不存在时写 stderr 并返回 2。"""
    code, out, err = run_du(["nosuch"], cwd=tree)
    assert code == 2
    assert out == ""
    assert "nosuch" in err


def test_du_missing_operand_keeps_going(tree):
    """有一个操作数不存在时，其余操作数照常统计。"""
    code, out, err = run_du(["nosuch", "tree"], cwd=tree)
    assert code == 2
    assert "tree" in out
    assert "nosuch" in err


def test_du_summarize_with_all_is_usage_error(tree):
    """-s 与 -a 互相矛盾，报用法错误。"""
    with pytest.raises(UsageError):
        run_du(["-s", "-a", "tree"], cwd=tree)


def test_du_summarize_with_max_depth_is_usage_error(tree):
    """-s 等于 --max-depth=0，跟更大的层数冲突。"""
    with pytest.raises(UsageError):
        run_du(["-s", "-d", "1", "tree"], cwd=tree)


def test_du_negative_max_depth_is_usage_error(tree):
    """-d 不能是负数。"""
    with pytest.raises(UsageError):
        run_du(["-d", "-1", "tree"], cwd=tree)


def test_du_invalid_threshold_is_usage_error(tree):
    """-t 的取值认不出来时报用法错误。"""
    with pytest.raises(UsageError):
        run_du(["-t", "bogus", "tree"], cwd=tree)


def test_du_invalid_block_size_is_usage_error(tree):
    """-B 的取值认不出来时报用法错误。"""
    with pytest.raises(UsageError):
        run_du(["-B", "bogus", "tree"], cwd=tree)


def test_du_zero_block_size_is_usage_error(tree):
    """-B 0 没有意义（会除零）。"""
    with pytest.raises(UsageError):
        run_du(["-B", "0", "tree"], cwd=tree)


def test_du_everything_filtered_returns_one(tree):
    """全被阈值滤掉时按本项目约定返回 1（GNU 返回 0）。"""
    code, out, err = run_du(["-t", "1M", "tree"], cwd=tree)
    assert code == 1
    assert out == ""
    assert err == ""
