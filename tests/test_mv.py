"""mv 指令的测试。

覆盖三块：正常路径、选项组合、错误路径。

语义基线来自 GNU coreutils 8.32 的 mv（Git Bash 的 /usr/bin/mv）实跑对照，
探针脚本 AI/脚本/_t500_probe_mv.py、_t502_probe_mv_edges.py、
_t504_probe_mv_options.py、_t505_probe_ni_order.py：

- 目标是已存在的目录时，源落成「目录/源名」；目标不存在时，目标就是新名字本身
- 多个源时目标必须是已存在的目录，这条检查先于逐个源的存在性检查
- **GNU 的 mv 不合并目录**：目标下同名目录已存在且非空时报「Directory not empty」
- 目标下同名目录已存在但是空的时，移动照常进行（rename 覆盖空目录）
- -v 打印「renamed '源' -> '目标'」，带备份时追加「(backup: '备份')」
- -n 跳过已存在的目标、-u 只在源更新时才动、-i 覆盖前问一句
- -i 与 -n 同时给时互相清掉对方：后给的那个赢（GNU 的 cp 与 mv 都一样）
- -b 把旧目标改名加后缀备份，-S 指定后缀并隐含开备份
"""

import os

import pytest

from conftest import run_mv


@pytest.fixture
def workdir(tmp_path):
    """一个待移动的现场：三个文件、一个两层目录、一个目标目录。"""
    (tmp_path / "a.txt").write_bytes(b"hello mv\r\nsecond line\r\n")
    (tmp_path / "b.txt").write_bytes(b"old content\r\n")
    (tmp_path / "bin.dat").write_bytes(bytes(range(256)))
    src = tmp_path / "dir1"
    src.mkdir()
    (src / "inner.txt").write_bytes(b"inner\r\n")
    (src / "sub").mkdir()
    (src / "sub" / "deep.txt").write_bytes(b"deep\r\n")
    dest = tmp_path / "destdir"
    dest.mkdir()
    (dest / "b.txt").write_bytes(b"existing in destdir\r\n")
    return tmp_path


# ---------- 正常路径 ----------


def test_move_file_to_new_name(workdir):
    code, out, err = run_mv(["a.txt", "copy.txt"], cwd=workdir)
    assert code == 0
    assert err == ""
    assert out == ""
    assert (workdir / "copy.txt").read_bytes() == b"hello mv\r\nsecond line\r\n"
    assert not (workdir / "a.txt").exists()


def test_move_file_overwrites_existing(workdir):
    code, _, _ = run_mv(["a.txt", "b.txt"], cwd=workdir)
    assert code == 0
    assert (workdir / "b.txt").read_bytes() == b"hello mv\r\nsecond line\r\n"
    assert not (workdir / "a.txt").exists()


def test_move_file_into_existing_directory(workdir):
    code, _, _ = run_mv(["a.txt", "destdir"], cwd=workdir)
    assert code == 0
    assert (workdir / "destdir" / "a.txt").read_bytes() == b"hello mv\r\nsecond line\r\n"
    assert not (workdir / "a.txt").exists()


def test_move_directory_into_existing_directory(workdir):
    code, _, _ = run_mv(["dir1", "destdir"], cwd=workdir)
    assert code == 0
    assert (workdir / "destdir" / "dir1" / "inner.txt").read_bytes() == b"inner\r\n"
    assert (workdir / "destdir" / "dir1" / "sub" / "deep.txt").read_bytes() == b"deep\r\n"
    assert not (workdir / "dir1").exists()


def test_move_directory_to_new_name(workdir):
    code, _, _ = run_mv(["dir1", "newdest"], cwd=workdir)
    assert code == 0
    assert (workdir / "newdest" / "inner.txt").read_bytes() == b"inner\r\n"
    assert not (workdir / "dir1").exists()


def test_move_directory_into_empty_same_name_directory(workdir):
    """目标下同名目录已存在但是空的时，移动照常进行。"""
    (workdir / "destdir" / "dir1").mkdir()

    code, _, err = run_mv(["dir1", "destdir"], cwd=workdir)
    assert code == 0, err
    assert (workdir / "destdir" / "dir1" / "inner.txt").read_bytes() == b"inner\r\n"
    assert not (workdir / "dir1").exists()


def test_move_several_sources_into_directory(workdir):
    code, _, _ = run_mv(["a.txt", "b.txt", "destdir"], cwd=workdir)
    assert code == 0
    assert (workdir / "destdir" / "a.txt").read_bytes() == b"hello mv\r\nsecond line\r\n"
    assert (workdir / "destdir" / "b.txt").read_bytes() == b"old content\r\n"
    assert not (workdir / "a.txt").exists()
    assert not (workdir / "b.txt").exists()


def test_move_several_sources_into_directory_with_a_directory_source(workdir):
    code, _, _ = run_mv(["dir1", "b.txt", "destdir"], cwd=workdir)
    assert code == 0
    assert (workdir / "destdir" / "dir1" / "inner.txt").exists()
    assert (workdir / "destdir" / "b.txt").read_bytes() == b"old content\r\n"


def test_binary_content_is_moved_byte_for_byte(workdir):
    code, _, _ = run_mv(["bin.dat", "bin.copy"], cwd=workdir)
    assert code == 0
    assert (workdir / "bin.copy").read_bytes() == bytes(range(256))


def test_move_empty_file(workdir):
    (workdir / "empty.txt").write_bytes(b"")
    code, _, _ = run_mv(["empty.txt", "empty.copy"], cwd=workdir)
    assert code == 0
    assert (workdir / "empty.copy").read_bytes() == b""
    assert not (workdir / "empty.txt").exists()


def test_move_empty_directory(workdir):
    (workdir / "emptydir").mkdir()
    code, _, _ = run_mv(["emptydir", "destdir"], cwd=workdir)
    assert code == 0
    assert (workdir / "destdir" / "emptydir").is_dir()


def test_source_trailing_slash_does_not_change_landing(workdir):
    code, _, _ = run_mv(["dir1/", "destdir"], cwd=workdir)
    assert code == 0
    assert (workdir / "destdir" / "dir1" / "inner.txt").exists()


def test_move_onto_readonly_target_succeeds(workdir):
    """GNU 的 mv 直接 rename 过去，不看目标文件的权限位。"""
    target = workdir / "b.txt"
    target.chmod(0o444)
    try:
        code, _, _ = run_mv(["a.txt", "b.txt"], cwd=workdir)
        assert code == 0
        assert target.read_bytes() == b"hello mv\r\nsecond line\r\n"
    finally:
        target.chmod(0o666)


# ---------- 选项组合 ----------


def test_verbose_prints_renamed_pair(workdir):
    code, out, _ = run_mv(["-v", "a.txt", "copy.txt"], cwd=workdir)
    assert code == 0
    assert out == "renamed 'a.txt' -> 'copy.txt'\n"


def test_verbose_prints_directory_pair(workdir):
    code, out, _ = run_mv(["-v", "dir1", "destdir"], cwd=workdir)
    assert code == 0
    assert out == "renamed 'dir1' -> 'destdir/dir1'\n"


def test_verbose_prints_several_pairs(workdir):
    code, out, _ = run_mv(["-v", "a.txt", "b.txt", "destdir"], cwd=workdir)
    assert code == 0
    assert out == (
        "renamed 'a.txt' -> 'destdir/a.txt'\n"
        "renamed 'b.txt' -> 'destdir/b.txt'\n"
    )


def test_no_clobber_keeps_existing_target(workdir):
    code, out, err = run_mv(["-n", "a.txt", "b.txt"], cwd=workdir)
    assert code == 0
    assert out == ""
    assert err == ""
    assert (workdir / "b.txt").read_bytes() == b"old content\r\n"
    assert (workdir / "a.txt").exists()


def test_no_clobber_still_moves_to_new_target(workdir):
    code, _, _ = run_mv(["-n", "a.txt", "copy.txt"], cwd=workdir)
    assert code == 0
    assert (workdir / "copy.txt").exists()
    assert not (workdir / "a.txt").exists()


def test_no_clobber_skips_non_empty_directory_merge(workdir):
    """-n 时目标同名目录非空也不报错，直接跳过。"""
    target = workdir / "destdir" / "dir1"
    target.mkdir()
    (target / "stale.txt").write_bytes(b"stale\r\n")

    code, _, err = run_mv(["-n", "dir1", "destdir"], cwd=workdir)
    assert code == 0
    assert err == ""
    assert (workdir / "dir1").exists()
    assert (target / "stale.txt").exists()


def test_update_skips_older_source(workdir):
    stamp = 1_000_000_000
    os.utime(workdir / "a.txt", (stamp, stamp))
    os.utime(workdir / "b.txt", (stamp + 5, stamp + 5))

    code, _, _ = run_mv(["-u", "a.txt", "b.txt"], cwd=workdir)
    assert code == 0
    assert (workdir / "b.txt").read_bytes() == b"old content\r\n"
    assert (workdir / "a.txt").exists()


def test_update_moves_newer_source(workdir):
    stamp = 1_000_000_000
    os.utime(workdir / "a.txt", (stamp, stamp))
    os.utime(workdir / "b.txt", (stamp + 5, stamp + 5))

    code, _, _ = run_mv(["-u", "b.txt", "a.txt"], cwd=workdir)
    assert code == 0
    assert (workdir / "a.txt").read_bytes() == b"old content\r\n"
    assert not (workdir / "b.txt").exists()


def test_update_skips_equal_timestamp(workdir):
    stamp = 1_000_000_000
    os.utime(workdir / "a.txt", (stamp, stamp))
    os.utime(workdir / "b.txt", (stamp, stamp))

    code, _, _ = run_mv(["-u", "a.txt", "b.txt"], cwd=workdir)
    assert code == 0
    assert (workdir / "b.txt").read_bytes() == b"old content\r\n"
    assert (workdir / "a.txt").exists()


def test_interactive_answers_yes_moves(workdir):
    code, _, err = run_mv(["-i", "a.txt", "b.txt"], cwd=workdir, stdin_text="y\n")
    assert code == 0
    assert "覆盖" in err
    assert (workdir / "b.txt").read_bytes() == b"hello mv\r\nsecond line\r\n"
    assert not (workdir / "a.txt").exists()


def test_interactive_answers_no_skips(workdir):
    code, _, err = run_mv(["-i", "a.txt", "b.txt"], cwd=workdir, stdin_text="n\n")
    assert code == 0
    assert "覆盖" in err
    assert (workdir / "b.txt").read_bytes() == b"old content\r\n"
    assert (workdir / "a.txt").exists()


def test_interactive_empty_answer_skips(workdir):
    code, _, _ = run_mv(["-i", "a.txt", "b.txt"], cwd=workdir, stdin_text="\n")
    assert code == 0
    assert (workdir / "b.txt").read_bytes() == b"old content\r\n"


def test_interactive_does_not_prompt_for_new_target(workdir):
    code, _, err = run_mv(["-i", "a.txt", "copy.txt"], cwd=workdir, stdin_text="y\n")
    assert code == 0
    assert err == ""
    assert (workdir / "copy.txt").exists()


def test_no_clobber_wins_when_given_last(workdir):
    """GNU 里 -i 与 -n 互相清掉对方：后给的那个赢。"""
    code, _, err = run_mv(["-i", "-n", "a.txt", "b.txt"], cwd=workdir, stdin_text="y\n")
    assert code == 0
    assert err == ""
    assert (workdir / "b.txt").read_bytes() == b"old content\r\n"
    assert (workdir / "a.txt").exists()


def test_interactive_wins_when_given_last(workdir):
    code, _, err = run_mv(["-n", "-i", "a.txt", "b.txt"], cwd=workdir, stdin_text="y\n")
    assert code == 0
    assert "覆盖" in err
    assert (workdir / "b.txt").read_bytes() == b"hello mv\r\nsecond line\r\n"
    assert not (workdir / "a.txt").exists()


def test_repeated_options_take_the_last_occurrence(workdir):
    """GNU 里 -n -i -n 是 -n 赢：重复给时取最后一次出现，不是第一次。"""
    code, _, err = run_mv(["-n", "-i", "-n", "a.txt", "b.txt"], cwd=workdir, stdin_text="y\n")
    assert code == 0
    assert err == ""
    assert (workdir / "b.txt").read_bytes() == b"old content\r\n"
    assert (workdir / "a.txt").exists()


def test_combined_short_options_keep_their_order(workdir):
    """合并短选项 -ni 是 -i 赢，-in 是 -n 赢。"""
    code, _, err = run_mv(["-ni", "a.txt", "b.txt"], cwd=workdir, stdin_text="y\n")
    assert code == 0
    assert "覆盖" in err
    assert not (workdir / "a.txt").exists()

    # 上面那步把 a.txt 移走了，换一个还在的源来测 -in
    (workdir / "c.txt").write_bytes(b"third\r\n")
    code, _, err = run_mv(["-in", "c.txt", "bin.dat"], cwd=workdir, stdin_text="y\n")
    assert code == 0
    assert err == ""
    assert (workdir / "bin.dat").read_bytes() == bytes(range(256))
    assert (workdir / "c.txt").exists()


def test_backup_renames_the_old_target(workdir):
    code, _, _ = run_mv(["-b", "a.txt", "b.txt"], cwd=workdir)
    assert code == 0
    assert (workdir / "b.txt").read_bytes() == b"hello mv\r\nsecond line\r\n"
    assert (workdir / "b.txt~").read_bytes() == b"old content\r\n"


def test_backup_suffix_option(workdir):
    code, _, _ = run_mv(["-b", "-S", ".bak", "a.txt", "b.txt"], cwd=workdir)
    assert code == 0
    assert (workdir / "b.txt.bak").read_bytes() == b"old content\r\n"


def test_suffix_alone_enables_backup(workdir):
    """GNU 里 -S 单独给就等于隐含开备份。"""
    code, _, _ = run_mv(["-S", ".bak", "a.txt", "b.txt"], cwd=workdir)
    assert code == 0
    assert (workdir / "b.txt.bak").read_bytes() == b"old content\r\n"


def test_verbose_mentions_the_backup(workdir):
    code, out, _ = run_mv(["-b", "-v", "a.txt", "b.txt"], cwd=workdir)
    assert code == 0
    assert out == "renamed 'a.txt' -> 'b.txt' (backup: 'b.txt~')\n"


def test_backup_of_a_directory(workdir):
    """备份目录时是把旧目录改名成「目录名~」。"""
    (workdir / "destdir" / "dir1").mkdir()

    code, _, _ = run_mv(["-b", "dir1", "destdir"], cwd=workdir)
    assert code == 0
    assert (workdir / "destdir" / "dir1" / "inner.txt").read_bytes() == b"inner\r\n"
    assert (workdir / "destdir" / "dir1~").is_dir()


def test_target_directory_option(workdir):
    code, _, _ = run_mv(["-t", "destdir", "a.txt"], cwd=workdir)
    assert code == 0
    assert (workdir / "destdir" / "a.txt").exists()
    assert not (workdir / "a.txt").exists()


def test_target_directory_takes_several_sources(workdir):
    code, _, _ = run_mv(["-t", "destdir", "a.txt", "b.txt"], cwd=workdir)
    assert code == 0
    assert (workdir / "destdir" / "a.txt").exists()
    assert (workdir / "destdir" / "b.txt").exists()


def test_no_target_directory_treats_target_as_a_file(workdir):
    """-T 把目标当普通文件：目标是目录时报错。"""
    code, _, err = run_mv(["-T", "a.txt", "destdir"], cwd=workdir)
    assert code == 2
    assert "覆盖目录" in err
    assert (workdir / "a.txt").exists()


def test_no_target_directory_moves_directory_itself(workdir):
    """-T 时目录源落到目标本身，不再套一层同名目录。"""
    code, _, _ = run_mv(["-T", "dir1", "newdest"], cwd=workdir)
    assert code == 0
    assert (workdir / "newdest" / "inner.txt").exists()
    assert not (workdir / "newdest" / "dir1").exists()


def test_force_overwrites_readonly_target(workdir):
    target = workdir / "b.txt"
    target.chmod(0o444)
    try:
        code, _, _ = run_mv(["-f", "a.txt", "b.txt"], cwd=workdir)
        assert code == 0
        assert target.read_bytes() == b"hello mv\r\nsecond line\r\n"
    finally:
        target.chmod(0o666)


# ---------- 错误路径 ----------


def test_missing_source_reports_error(workdir):
    code, _, err = run_mv(["nosuch.txt", "copy.txt"], cwd=workdir)
    assert code == 2
    assert "nosuch.txt" in err
    assert not (workdir / "copy.txt").exists()


def test_no_operand_is_usage_error(workdir):
    code, _, err = run_mv([], cwd=workdir)
    assert code == 2
    assert "缺少文件操作数" in err


def test_single_operand_is_usage_error(workdir):
    code, _, err = run_mv(["a.txt"], cwd=workdir)
    assert code == 2
    assert "缺少目标文件操作数" in err
    assert "a.txt" in err


def test_multiple_sources_require_a_directory_target(workdir):
    code, _, err = run_mv(["a.txt", "b.txt", "copy.txt"], cwd=workdir)
    assert code == 2
    assert "不是目录" in err
    assert (workdir / "a.txt").exists()


def test_missing_target_directory_option_reports_error(workdir):
    code, _, err = run_mv(["-t", "nosuchdir", "a.txt"], cwd=workdir)
    assert code == 2
    assert "nosuchdir" in err


def test_moving_a_file_onto_itself_is_refused(workdir):
    code, _, err = run_mv(["a.txt", "a.txt"], cwd=workdir)
    assert code == 2
    assert "同一个文件" in err
    assert (workdir / "a.txt").exists()


def test_moving_a_file_onto_itself_by_another_path_is_refused(workdir):
    code, _, err = run_mv(["a.txt", "./a.txt"], cwd=workdir)
    assert code == 2
    assert "同一个文件" in err


def test_moving_a_directory_into_itself_is_refused(workdir):
    code, _, err = run_mv(["dir1", "dir1/sub"], cwd=workdir)
    assert code == 2
    assert "子目录" in err
    assert (workdir / "dir1" / "inner.txt").exists()


def test_moving_a_directory_onto_a_file_is_refused(workdir):
    code, _, err = run_mv(["dir1", "b.txt"], cwd=workdir)
    assert code == 2
    assert "覆盖非目录" in err
    assert (workdir / "b.txt").read_bytes() == b"old content\r\n"


def test_moving_a_file_onto_a_directory_is_refused(workdir):
    code, _, err = run_mv(["-T", "a.txt", "destdir"], cwd=workdir)
    assert code == 2
    assert "覆盖目录" in err


def test_moving_a_directory_onto_non_empty_directory_is_refused(workdir):
    """GNU 的 mv 不合并目录：目标同名目录非空时直接报错。"""
    target = workdir / "destdir" / "dir1"
    target.mkdir()
    (target / "stale.txt").write_bytes(b"stale\r\n")

    code, _, err = run_mv(["dir1", "destdir"], cwd=workdir)
    assert code == 2
    assert "目录非空" in err
    assert (workdir / "dir1" / "inner.txt").exists()
    assert (target / "stale.txt").exists()


def test_missing_parent_directory_is_refused(workdir):
    code, _, err = run_mv(["a.txt", "nodir/out.txt"], cwd=workdir)
    assert code == 2
    assert "没有那个文件或目录" in err
    assert (workdir / "a.txt").exists()


def test_no_target_directory_rejects_extra_operand(workdir):
    code, _, err = run_mv(["-T", "a.txt", "b.txt", "c.txt"], cwd=workdir)
    assert code == 2
    assert "多余的操作数" in err
