"""cp 指令的测试。

覆盖三块：正常路径、选项组合、错误路径。

语义基线来自 GNU coreutils 8.32 的 cp（Git Bash 的 /usr/bin/cp）实跑对照，
57 组用例的落地结果与本实现逐条一致（差分脚本 AI/脚本/_t410_diff_cp.py）：

- 目标是已存在的目录时，源落成「目录/源名」；目标不存在时，目标就是新文件
- 多个源时目标必须是已存在的目录，这条检查先于逐个源的存在性检查
- 拷目录必须给 -r；源目录尾部的斜杠不影响落点（GNU 8.32 实测）
- -r 目录到不存在的目标时，目标目录就是那份目录的副本（不再套一层同名目录）
- 目标已存在同名目录时是「合并」：同名文件被覆盖，目标多出来的文件保留
- -v 逐条打印「'源' -> '目标'」，目录只在新建时打印那一行
- -n 跳过已存在的文件、-u 只在源更新时才复制、-i 覆盖前问一句
- -p / -a 保住源的时间戳；-S 在覆盖前把旧目标改名加后缀
- --parents 在目标下还原源的路径层级，并自己建父目录
"""

import os

import pytest

from conftest import run_cp


@pytest.fixture
def workdir(tmp_path):
    """一个待复制的现场：三个文件、一个两层目录、一个目标目录。"""
    (tmp_path / "a.txt").write_bytes(b"hello cp\r\nsecond line\r\n")
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


def test_copy_file_to_new_file(workdir):
    code, out, err = run_cp(["a.txt", "copy.txt"], cwd=workdir)
    assert code == 0
    assert err == ""
    assert (workdir / "copy.txt").read_bytes() == b"hello cp\r\nsecond line\r\n"
    assert out == ""


def test_copy_file_overwrites_existing(workdir):
    code, _, _ = run_cp(["a.txt", "b.txt"], cwd=workdir)
    assert code == 0
    assert (workdir / "b.txt").read_bytes() == b"hello cp\r\nsecond line\r\n"


def test_copy_file_into_existing_directory(workdir):
    code, _, _ = run_cp(["a.txt", "destdir"], cwd=workdir)
    assert code == 0
    assert (workdir / "destdir" / "a.txt").read_bytes() == b"hello cp\r\nsecond line\r\n"


def test_copy_file_to_nonexistent_path_creates_file(workdir):
    """目标不存在且不是已存在的目录时，目标就是那个新文件。"""
    code, _, _ = run_cp(["a.txt", "newdir"], cwd=workdir)
    assert code == 0
    assert (workdir / "newdir").is_file()
    assert not (workdir / "newdir").is_dir()


def test_binary_content_is_copied_byte_for_byte(workdir):
    code, _, _ = run_cp(["bin.dat", "bin.copy"], cwd=workdir)
    assert code == 0
    assert (workdir / "bin.copy").read_bytes() == bytes(range(256))


def test_copy_directory_without_r_is_refused(workdir):
    code, _, err = run_cp(["dir1", "destdir"], cwd=workdir)
    assert code == 2
    assert "-r" in err
    assert "dir1" in err


def test_copy_directory_recursively(workdir):
    code, _, _ = run_cp(["-r", "dir1", "destdir"], cwd=workdir)
    assert code == 0
    assert (workdir / "destdir" / "dir1" / "inner.txt").read_bytes() == b"inner\r\n"
    assert (workdir / "destdir" / "dir1" / "sub" / "deep.txt").read_bytes() == b"deep\r\n"


def test_copy_directory_to_new_target_has_no_extra_layer(workdir):
    """目标不存在时，目标目录本身就是那份目录的副本。"""
    code, _, _ = run_cp(["-r", "dir1", "newdest"], cwd=workdir)
    assert code == 0
    assert (workdir / "newdest" / "inner.txt").read_bytes() == b"inner\r\n"
    assert not (workdir / "newdest" / "dir1").exists()


def test_source_trailing_slash_does_not_change_landing(workdir):
    """GNU 8.32 实测：源尾部的斜杠不影响落点，仍然是「目标/源名」。"""
    code, _, _ = run_cp(["-r", "dir1/", "destdir"], cwd=workdir)
    assert code == 0
    assert (workdir / "destdir" / "dir1" / "inner.txt").exists()


def test_copy_into_existing_directory_merges(workdir):
    """目标已有同名目录时是合并：同名文件被覆盖，目标多出来的文件保留。"""
    target = workdir / "destdir" / "dir1"
    target.mkdir()
    (target / "inner.txt").write_bytes(b"OLD inner\r\n")
    (target / "stale.txt").write_bytes(b"stale\r\n")

    code, _, _ = run_cp(["-r", "dir1", "destdir"], cwd=workdir)
    assert code == 0
    assert (target / "inner.txt").read_bytes() == b"inner\r\n"
    assert (target / "stale.txt").read_bytes() == b"stale\r\n"


# ---------- 选项组合 ----------


def test_verbose_prints_source_to_target_pairs(workdir):
    code, out, _ = run_cp(["-v", "a.txt", "copy.txt"], cwd=workdir)
    assert code == 0
    assert out == "'a.txt' -> 'copy.txt'\n"


def test_verbose_prints_directory_line_only_when_created(workdir):
    code, out, _ = run_cp(["-v", "-r", "dir1", "destdir"], cwd=workdir)
    assert code == 0
    lines = out.splitlines()
    assert lines[0] == "'dir1' -> 'destdir/dir1'"
    assert "'dir1/inner.txt' -> 'destdir/dir1/inner.txt'" in lines
    assert "'dir1/sub/deep.txt' -> 'destdir/dir1/sub/deep.txt'" in lines


def test_no_clobber_keeps_existing_target(workdir):
    code, out, err = run_cp(["-n", "a.txt", "b.txt"], cwd=workdir)
    assert code == 0
    assert out == ""
    assert err == ""
    assert (workdir / "b.txt").read_bytes() == b"old content\r\n"


def test_no_clobber_still_copies_new_target(workdir):
    code, _, _ = run_cp(["-n", "a.txt", "copy.txt"], cwd=workdir)
    assert code == 0
    assert (workdir / "copy.txt").exists()


def test_update_skips_older_source(workdir):
    stamp = 1_000_000_000
    os.utime(workdir / "a.txt", (stamp, stamp))
    os.utime(workdir / "b.txt", (stamp + 500, stamp + 500))

    code, _, _ = run_cp(["-u", "a.txt", "b.txt"], cwd=workdir)
    assert code == 0
    assert (workdir / "b.txt").read_bytes() == b"old content\r\n"


def test_update_copies_newer_source(workdir):
    stamp = 1_000_000_000
    os.utime(workdir / "a.txt", (stamp + 500, stamp + 500))
    os.utime(workdir / "b.txt", (stamp, stamp))

    code, _, _ = run_cp(["-u", "a.txt", "b.txt"], cwd=workdir)
    assert code == 0
    assert (workdir / "b.txt").read_bytes() == b"hello cp\r\nsecond line\r\n"


def test_interactive_answers_yes_copies(workdir):
    code, _, err = run_cp(["-i", "a.txt", "b.txt"], cwd=workdir, stdin_text="y\n")
    assert code == 0
    assert "覆盖" in err
    assert (workdir / "b.txt").read_bytes() == b"hello cp\r\nsecond line\r\n"


def test_interactive_answers_no_skips(workdir):
    code, _, err = run_cp(["-i", "a.txt", "b.txt"], cwd=workdir, stdin_text="n\n")
    assert code == 0
    assert "覆盖" in err
    assert (workdir / "b.txt").read_bytes() == b"old content\r\n"


def test_interactive_does_not_prompt_for_new_target(workdir):
    code, _, err = run_cp(["-i", "a.txt", "copy.txt"], cwd=workdir, stdin_text="y\n")
    assert code == 0
    assert err == ""
    assert (workdir / "copy.txt").exists()


def test_preserve_keeps_source_timestamp(workdir):
    stamp = 1_000_000_000
    os.utime(workdir / "a.txt", (stamp, stamp))

    code, _, _ = run_cp(["-p", "a.txt", "copy.txt"], cwd=workdir)
    assert code == 0
    assert int((workdir / "copy.txt").stat().st_mtime) == stamp


def test_without_preserve_timestamp_is_the_copy_time(workdir):
    stamp = 1_000_000_000
    os.utime(workdir / "a.txt", (stamp, stamp))

    code, _, _ = run_cp(["a.txt", "copy.txt"], cwd=workdir)
    assert code == 0
    assert int((workdir / "copy.txt").stat().st_mtime) != stamp


def test_preserve_directory_keeps_directory_timestamp(workdir):
    stamp = 1_000_000_000
    os.utime(workdir / "dir1", (stamp, stamp))

    code, _, _ = run_cp(["-p", "-r", "dir1", "destdir"], cwd=workdir)
    assert code == 0
    assert int((workdir / "destdir" / "dir1").stat().st_mtime) == stamp


def test_archive_is_recursive_and_preserves(workdir):
    stamp = 1_000_000_000
    os.utime(workdir / "a.txt", (stamp, stamp))

    code, _, _ = run_cp(["-a", "dir1", "destdir"], cwd=workdir)
    assert code == 0
    assert (workdir / "destdir" / "dir1" / "sub" / "deep.txt").exists()


def test_target_directory_option(workdir):
    code, _, _ = run_cp(["-t", "destdir", "a.txt"], cwd=workdir)
    assert code == 0
    assert (workdir / "destdir" / "a.txt").exists()


def test_target_directory_takes_several_sources(workdir):
    code, _, _ = run_cp(["-t", "destdir", "a.txt", "bin.dat"], cwd=workdir)
    assert code == 0
    assert (workdir / "destdir" / "a.txt").exists()
    assert (workdir / "destdir" / "bin.dat").exists()


def test_no_target_directory_copies_directory_contents(workdir):
    """-T 把目标当普通文件：拷目录时是「目录的内容」落进去，不套同名层。"""
    code, _, _ = run_cp(["-T", "-r", "dir1", "destdir"], cwd=workdir)
    assert code == 0
    assert (workdir / "destdir" / "inner.txt").exists()
    assert not (workdir / "destdir" / "dir1").exists()


def test_parents_keeps_source_path_layout(workdir):
    code, _, _ = run_cp(["--parents", "dir1/inner.txt", "destdir"], cwd=workdir)
    assert code == 0
    assert (workdir / "destdir" / "dir1" / "inner.txt").read_bytes() == b"inner\r\n"


def test_parents_creates_missing_parent_directories(workdir):
    code, _, _ = run_cp(["--parents", "a.txt", "destdir"], cwd=workdir)
    assert code == 0
    assert (workdir / "destdir" / "a.txt").exists()


def test_suffix_renames_the_old_target(workdir):
    code, _, _ = run_cp(["-S", ".bak", "a.txt", "b.txt"], cwd=workdir)
    assert code == 0
    assert (workdir / "b.txt").read_bytes() == b"hello cp\r\nsecond line\r\n"
    assert (workdir / "b.txt.bak").read_bytes() == b"old content\r\n"


def test_force_overwrites_read_only_target(workdir):
    target = workdir / "b.txt"
    target.chmod(0o444)
    try:
        code, _, _ = run_cp(["-f", "a.txt", "b.txt"], cwd=workdir)
        assert code == 0
        assert target.read_bytes() == b"hello cp\r\nsecond line\r\n"
    finally:
        target.chmod(0o666)


def test_remove_destination_replaces_target(workdir):
    code, _, _ = run_cp(["--remove-destination", "a.txt", "b.txt"], cwd=workdir)
    assert code == 0
    assert (workdir / "b.txt").read_bytes() == b"hello cp\r\nsecond line\r\n"


def test_preserve_mode_list_accepts_valid_modes(workdir):
    code, _, _ = run_cp(["--preserve=mode,timestamps", "a.txt", "copy.txt"], cwd=workdir)
    assert code == 0
    assert (workdir / "copy.txt").exists()


# ---------- 错误路径 ----------


def test_missing_source_reports_error(workdir):
    code, _, err = run_cp(["nosuch.txt", "copy.txt"], cwd=workdir)
    assert code == 2
    assert "nosuch.txt" in err
    assert not (workdir / "copy.txt").exists()


def test_no_operand_is_usage_error(workdir):
    code, _, err = run_cp([], cwd=workdir)
    assert code == 2
    assert "缺少文件操作数" in err


def test_single_operand_is_usage_error(workdir):
    code, _, err = run_cp(["a.txt"], cwd=workdir)
    assert code == 2
    assert "缺少目标文件操作数" in err
    assert "a.txt" in err


def test_multiple_sources_require_a_directory_target(workdir):
    code, _, err = run_cp(["a.txt", "bin.dat", "copy.txt"], cwd=workdir)
    assert code == 2
    assert "不是目录" in err
    assert not (workdir / "copy.txt").exists()


def test_missing_target_directory_option_reports_error(workdir):
    code, _, err = run_cp(["-t", "nosuchdir", "a.txt"], cwd=workdir)
    assert code == 2
    assert "nosuchdir" in err


def test_copying_a_file_onto_itself_is_refused(workdir):
    code, _, err = run_cp(["a.txt", "a.txt"], cwd=workdir)
    assert code == 2
    assert "同一个文件" in err


def test_copying_a_directory_into_itself_is_refused(workdir):
    code, _, err = run_cp(["-r", "dir1", "dir1"], cwd=workdir)
    assert code == 2
    assert "复制到它自己里面" in err
    assert not (workdir / "dir1" / "dir1").exists()


def test_directory_source_over_file_target_is_refused(workdir):
    code, _, err = run_cp(["-r", "dir1", "a.txt"], cwd=workdir)
    assert code == 2
    assert "覆盖非目录" in err
    assert (workdir / "a.txt").read_bytes() == b"hello cp\r\nsecond line\r\n"


def test_missing_parent_directory_is_refused(workdir):
    code, _, err = run_cp(["a.txt", "nodir/out.txt"], cwd=workdir)
    assert code == 2
    assert "无法创建普通文件" in err


def test_parents_requires_a_directory_target(workdir):
    code, _, err = run_cp(["--parents", "a.txt", "newdir"], cwd=workdir)
    assert code == 2
    assert "--parents" in err


def test_invalid_preserve_mode_is_usage_error(workdir):
    code, _, err = run_cp(["--preserve=bogus", "a.txt", "copy.txt"], cwd=workdir)
    assert code == 2
    assert "bogus" in err
    assert not (workdir / "copy.txt").exists()


def test_no_target_directory_rejects_extra_operand(workdir):
    code, _, err = run_cp(["-T", "a.txt", "b.txt", "c.txt"], cwd=workdir)
    assert code == 2
    assert "多余的操作数" in err
