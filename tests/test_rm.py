"""rm 指令的测试。

覆盖三块：正常路径、选项组合、错误路径。

语义基线来自 GNU coreutils 8.32 的 rm（Git Bash 的 /usr/bin/rm）实跑对照，
探针脚本 AI/脚本/_t600_probe_rm.py ~ _t611_probe_rm12.py，
差分对照脚本 AI/脚本/_t620_diff_rm.py（48 个场景逐条比）：

- 不给 -r 时目录删不掉，报「是一个目录」；-f 也不抑制这一条
- -r 递归删除；-d 删空目录（-d 遇到普通文件也照删）
- -v 打印「removed 'X'」/「removed directory 'X'」，文件先于目录，标签保留 ./ 前缀
- -f 忽略不存在的文件，缺操作数时也静默返回 0
- -i 逐项询问：进目录 → 删文件 → 删目录；拒绝删文件不影响父目录的询问，
  拒绝进入子目录则父目录不再询问
- -I 只在操作数超过三个或递归时问一次；三个文件时不问
- --interactive[=WHEN] 里的 WHEN 只认 never/no/none、once、always/yes
- **后给的那个赢**：-f -i 等于 -i，-i -f 等于 -f
- 命令行参数的最后一段是 . 或 .. 时拒绝删除（POSIX 要求）
"""

import pytest

from conftest import run_rm


@pytest.fixture
def workdir(tmp_path):
    """一个待删除的现场：三个文件、一个两层目录、一个空目录。"""
    (tmp_path / "a.txt").write_bytes(b"alpha\r\n")
    (tmp_path / "b.txt").write_bytes(b"beta\r\n")
    (tmp_path / "c.txt").write_bytes(b"gamma\r\n")
    (tmp_path / "d.txt").write_bytes(b"delta\r\n")
    src = tmp_path / "dir"
    src.mkdir()
    (src / "inner.txt").write_bytes(b"inner\r\n")
    (src / "sub").mkdir()
    (src / "sub" / "deep.txt").write_bytes(b"deep\r\n")
    (tmp_path / "empty").mkdir()
    return tmp_path


# ---------- 正常路径 ----------


def test_remove_regular_file(workdir):
    code, out, err = run_rm(["a.txt"], cwd=workdir)
    assert code == 0
    assert out == ""
    assert err == ""
    assert not (workdir / "a.txt").exists()


def test_remove_several_files(workdir):
    code, _, _ = run_rm(["a.txt", "b.txt", "c.txt"], cwd=workdir)
    assert code == 0
    assert not (workdir / "a.txt").exists()
    assert not (workdir / "b.txt").exists()
    assert not (workdir / "c.txt").exists()


def test_remove_directory_recursively(workdir):
    code, _, _ = run_rm(["-r", "dir"], cwd=workdir)
    assert code == 0
    assert not (workdir / "dir").exists()


def test_remove_empty_directory_with_dir_option(workdir):
    code, _, _ = run_rm(["-d", "empty"], cwd=workdir)
    assert code == 0
    assert not (workdir / "empty").exists()


def test_dir_option_also_removes_regular_file(workdir):
    """GNU 的 -d 遇到普通文件也照删。"""
    code, _, _ = run_rm(["-d", "a.txt"], cwd=workdir)
    assert code == 0
    assert not (workdir / "a.txt").exists()


def test_verbose_prints_removed_line(workdir):
    code, out, _ = run_rm(["-v", "a.txt"], cwd=workdir)
    assert code == 0
    assert out == "removed 'a.txt'\n"


def test_verbose_recursive_prints_files_before_directories(workdir):
    code, out, _ = run_rm(["-v", "-r", "dir"], cwd=workdir)
    assert code == 0
    assert out == (
        "removed 'dir/inner.txt'\n"
        "removed 'dir/sub/deep.txt'\n"
        "removed directory 'dir/sub'\n"
        "removed directory 'dir'\n"
    )


def test_verbose_keeps_the_dot_prefix(workdir):
    code, out, _ = run_rm(["-v", "-r", "./dir"], cwd=workdir)
    assert code == 0
    assert out == (
        "removed './dir/inner.txt'\n"
        "removed './dir/sub/deep.txt'\n"
        "removed directory './dir/sub'\n"
        "removed directory './dir'\n"
    )


def test_readonly_file_is_removed(workdir):
    """POSIX 的 rm 只看目录的写权限，文件自身只读照样能删。"""
    target = workdir / "a.txt"
    target.chmod(0o444)
    try:
        code, _, _ = run_rm(["a.txt"], cwd=workdir)
        assert code == 0
        assert not target.exists()
    finally:
        if target.exists():
            target.chmod(0o666)


def test_remove_empty_file(workdir):
    (workdir / "zero.txt").write_bytes(b"")
    code, _, _ = run_rm(["zero.txt"], cwd=workdir)
    assert code == 0
    assert not (workdir / "zero.txt").exists()


# ---------- 选项组合 ----------


def test_force_ignores_missing_file(workdir):
    code, out, err = run_rm(["-f", "nosuch.txt"], cwd=workdir)
    assert code == 0
    assert out == ""
    assert err == ""


def test_force_without_operand_is_silent(workdir):
    """GNU：给了 -f 时缺操作数不算错。"""
    code, out, err = run_rm(["-f"], cwd=workdir)
    assert code == 0
    assert out == ""
    assert err == ""


def test_force_does_not_suppress_the_directory_error(workdir):
    """-f 只忽略「文件不存在」，目录没给 -r 照样报错。"""
    code, _, err = run_rm(["-f", "dir"], cwd=workdir)
    assert code == 2
    assert "是一个目录" in err
    assert (workdir / "dir").exists()


def test_interactive_answers_yes_removes(workdir):
    code, _, err = run_rm(["-i", "a.txt"], cwd=workdir, stdin_text="y\n")
    assert code == 0
    assert "删除普通文件 'a.txt'?" in err
    assert not (workdir / "a.txt").exists()


def test_interactive_answers_no_keeps_the_file(workdir):
    code, _, err = run_rm(["-i", "a.txt"], cwd=workdir, stdin_text="n\n")
    assert code == 0
    assert "删除普通文件 'a.txt'?" in err
    assert (workdir / "a.txt").exists()


def test_interactive_empty_answer_keeps_the_file(workdir):
    code, _, _ = run_rm(["-i", "a.txt"], cwd=workdir, stdin_text="\n")
    assert code == 0
    assert (workdir / "a.txt").exists()


def test_interactive_leading_space_means_no(workdir):
    """GNU 的 yesno 只看第一个字符，前面有空格就不算同意。"""
    code, _, _ = run_rm(["-i", "a.txt"], cwd=workdir, stdin_text=" y\n")
    assert code == 0
    assert (workdir / "a.txt").exists()


def test_interactive_declines_the_first_of_two(workdir):
    """拒绝了第一个照样问第二个。"""
    code, _, err = run_rm(["-i", "a.txt", "b.txt"], cwd=workdir, stdin_text="n\ny\n")
    assert code == 0
    assert err.count("? ") == 2
    assert (workdir / "a.txt").exists()
    assert not (workdir / "b.txt").exists()


def test_interactive_recursive_prompt_order(workdir):
    """顺序是：进目录 → 删文件 → 删目录。"""
    code, _, err = run_rm(
        ["-i", "-r", "dir"], cwd=workdir, stdin_text="y\ny\ny\ny\ny\ny\n"
    )
    assert code == 0
    assert err == (
        "rm: 进入目录 'dir'? "
        "rm: 删除普通文件 'dir/inner.txt'? "
        "rm: 进入目录 'dir/sub'? "
        "rm: 删除普通文件 'dir/sub/deep.txt'? "
        "rm: 删除目录 'dir/sub'? "
        "rm: 删除目录 'dir'? "
    )
    assert not (workdir / "dir").exists()


def test_interactive_declining_to_descend_keeps_the_tree(workdir):
    code, _, err = run_rm(["-i", "-r", "dir"], cwd=workdir, stdin_text="n\n")
    assert code == 0
    assert err == "rm: 进入目录 'dir'? "
    assert (workdir / "dir" / "inner.txt").exists()


def test_interactive_declining_a_child_directory_stops_the_parent_prompt(workdir):
    """拒绝进入子目录后，父目录不再询问，整棵子树留下。"""
    code, _, err = run_rm(
        ["-i", "-r", "dir"], cwd=workdir, stdin_text="y\ny\nn\n"
    )
    assert code == 0
    assert err == (
        "rm: 进入目录 'dir'? "
        "rm: 删除普通文件 'dir/inner.txt'? "
        "rm: 进入目录 'dir/sub'? "
    )
    assert (workdir / "dir" / "sub" / "deep.txt").exists()
    assert not (workdir / "dir" / "inner.txt").exists()


def test_interactive_declining_a_file_still_asks_the_parent(workdir):
    """拒绝了某个文件，父目录照样问；父目录非空，于是 rmdir 失败报错。"""
    code, _, err = run_rm(
        ["-i", "-r", "dir"], cwd=workdir, stdin_text="y\nn\ny\ny\ny\ny\n"
    )
    assert code == 2
    assert "无法删除 'dir'" in err
    assert (workdir / "dir" / "inner.txt").exists()
    assert not (workdir / "dir" / "sub").exists()


def test_interactive_does_not_prompt_for_a_missing_file(workdir):
    """文件不存在时直接报错，不问。"""
    code, _, err = run_rm(["-i", "nosuch.txt"], cwd=workdir, stdin_text="y\n")
    assert code == 2
    assert "无法删除 'nosuch.txt'" in err
    assert "?" not in err


def test_force_then_interactive_last_wins(workdir):
    """GNU 里这几个开关共用一组变量：后给的那个赢。"""
    code, _, err = run_rm(["-f", "-i", "a.txt"], cwd=workdir, stdin_text="n\n")
    assert code == 0
    assert "删除普通文件 'a.txt'?" in err
    assert (workdir / "a.txt").exists()


def test_interactive_then_force_last_wins(workdir):
    code, _, err = run_rm(["-i", "-f", "a.txt"], cwd=workdir, stdin_text="n\n")
    assert code == 0
    assert err == ""
    assert not (workdir / "a.txt").exists()


def test_prompt_once_is_not_asked_for_three_files(workdir):
    code, _, err = run_rm(["-I", "a.txt", "b.txt", "c.txt"], cwd=workdir)
    assert code == 0
    assert err == ""
    assert not (workdir / "a.txt").exists()


def test_prompt_once_is_asked_for_four_files(workdir):
    code, _, err = run_rm(
        ["-I", "a.txt", "b.txt", "c.txt", "d.txt"], cwd=workdir, stdin_text="y\n"
    )
    assert code == 0
    assert err == "rm: 删除 4 个参数? "
    assert not (workdir / "a.txt").exists()


def test_prompt_once_is_asked_when_recursive(workdir):
    code, _, err = run_rm(["-I", "-r", "dir"], cwd=workdir, stdin_text="y\n")
    assert code == 0
    assert err == "rm: 递归删除 1 个参数? "
    assert not (workdir / "dir").exists()


def test_prompt_once_declined_removes_nothing(workdir):
    code, _, err = run_rm(["-I", "-r", "dir"], cwd=workdir, stdin_text="n\n")
    assert code == 0
    assert err == "rm: 递归删除 1 个参数? "
    assert (workdir / "dir" / "inner.txt").exists()


def test_interactive_never_asks_nothing(workdir):
    code, _, err = run_rm(["--interactive=never", "a.txt"], cwd=workdir)
    assert code == 0
    assert err == ""
    assert not (workdir / "a.txt").exists()


def test_interactive_once_asks_nothing_for_a_single_file(workdir):
    code, _, err = run_rm(["--interactive=once", "a.txt"], cwd=workdir)
    assert code == 0
    assert err == ""
    assert not (workdir / "a.txt").exists()


def test_interactive_always_asks_every_item(workdir):
    code, _, err = run_rm(
        ["--interactive=always", "a.txt", "b.txt"], cwd=workdir, stdin_text="y\ny\n"
    )
    assert code == 0
    assert err.count("? ") == 2
    assert not (workdir / "a.txt").exists()
    assert not (workdir / "b.txt").exists()


def test_bare_interactive_means_always(workdir):
    code, _, err = run_rm(["--interactive", "a.txt"], cwd=workdir, stdin_text="n\n")
    assert code == 0
    assert "删除普通文件 'a.txt'?" in err
    assert (workdir / "a.txt").exists()


def test_interactive_never_keeps_the_force_flag(workdir):
    """GNU 里 --interactive=never 不动「忽略不存在的文件」这一位。"""
    code, _, err = run_rm(
        ["-f", "--interactive=never", "nosuch.txt"], cwd=workdir
    )
    assert code == 0
    assert err == ""


def test_interactive_never_after_force_still_ignores_missing(workdir):
    code, _, err = run_rm(
        ["--interactive=never", "-f", "nosuch.txt"], cwd=workdir
    )
    assert code == 0
    assert err == ""


def test_interactive_always_turns_off_the_force_flag(workdir):
    """--interactive=always 会把「忽略不存在的文件」关掉。"""
    code, _, err = run_rm(["--interactive=always", "nosuch.txt"], cwd=workdir)
    assert code == 2
    assert "无法删除 'nosuch.txt'" in err


def test_long_option_can_be_abbreviated(workdir):
    """GNU 的 getopt_long 允许长选项缩写。"""
    code, _, err = run_rm(["--inter=once", "a.txt"], cwd=workdir)
    assert code == 0
    assert err == ""
    assert not (workdir / "a.txt").exists()


def test_interactive_value_must_use_the_equals_form(workdir):
    """GNU 只认 --interactive=WHEN；写成 --interactive WHEN 时 WHEN 是文件名。"""
    (workdir / "once").write_bytes(b"once\r\n")
    code, _, err = run_rm(["--interactive", "once"], cwd=workdir, stdin_text="n\n")
    assert code == 0
    assert "删除普通文件 'once'?" in err
    assert (workdir / "once").exists()


def test_recursive_and_dir_option_together(workdir):
    code, _, _ = run_rm(["-r", "-d", "dir"], cwd=workdir)
    assert code == 0
    assert not (workdir / "dir").exists()


# ---------- 错误路径 ----------


def test_missing_operand_is_usage_error(workdir):
    code, _, err = run_rm([], cwd=workdir)
    assert code == 2
    assert "缺少文件操作数" in err


def test_missing_file_reports_error(workdir):
    code, _, err = run_rm(["nosuch.txt"], cwd=workdir)
    assert code == 2
    assert "无法删除 'nosuch.txt'" in err


def test_directory_without_recursive_is_refused(workdir):
    code, _, err = run_rm(["dir"], cwd=workdir)
    assert code == 2
    assert "是一个目录" in err
    assert (workdir / "dir" / "inner.txt").exists()


def test_dir_option_on_non_empty_directory_is_refused(workdir):
    code, _, err = run_rm(["-d", "dir"], cwd=workdir)
    assert code == 2
    assert "目录非空" in err
    assert (workdir / "dir" / "inner.txt").exists()


def test_dot_directory_is_refused(workdir):
    """POSIX：命令行的最后一段是 . 或 .. 时拒绝删除。"""
    code, _, err = run_rm(["-r", "."], cwd=workdir)
    assert code == 2
    assert "拒绝删除" in err
    assert (workdir / "a.txt").exists()


def test_dot_inside_a_subdirectory_is_refused(workdir):
    code, _, err = run_rm(["-r", "dir/sub/."], cwd=workdir)
    assert code == 2
    assert "拒绝删除" in err
    assert (workdir / "dir" / "sub" / "deep.txt").exists()


def test_invalid_interactive_value_is_usage_error(workdir):
    code, _, err = run_rm(["--interactive=bad", "a.txt"], cwd=workdir)
    assert code == 2
    assert "--interactive" in err
    assert "bad" in err


def test_same_file_twice_reports_the_second_miss(workdir):
    code, _, err = run_rm(["a.txt", "a.txt"], cwd=workdir)
    assert code == 2
    assert "无法删除 'a.txt'" in err
    assert not (workdir / "a.txt").exists()


def test_unknown_option_is_usage_error():
    with pytest.raises(SystemExit) as excinfo:
        run_rm(["--bogus"])
    assert excinfo.value.code == 2


def test_help_flag_exits_zero(capsys):
    with pytest.raises(SystemExit) as excinfo:
        run_rm(["--help"])
    assert excinfo.value.code == 0
