"""chmod 指令的测试。

口径说明（与 GNU 在本机的实测行为一致）：
- 当前模式：可写文件 0644、只读文件 0444、目录 0755
- 落盘只有「只读属性」这一位，属主写位没了就设只读，有写位就清掉
- 报数沿用 GNU 原文：changed / retained as / failed to change
"""

import os
import stat

import pytest

from conftest import run_chmod, run_ls


@pytest.fixture
def workdir(tmp_path):
    """给每个用例一个干净的目录，结束后把只读属性清掉再让 pytest 删。"""
    yield tmp_path
    for item in tmp_path.rglob("*"):
        try:
            os.chmod(item, stat.S_IREAD | stat.S_IWRITE)
        except OSError:
            pass
    try:
        os.chmod(tmp_path, stat.S_IREAD | stat.S_IWRITE)
    except OSError:
        pass


def _is_readonly(path) -> bool:
    """看文件是不是只读（Windows 上就是那一个能落盘的权限位）。"""
    mode = os.stat(path).st_mode
    return not (mode & stat.S_IWRITE)


def _can_write(path) -> bool:
    try:
        with open(path, "a", encoding="utf-8"):
            pass
    except OSError:
        return False
    return True


# ---------- 正常路径 ----------


def test_chmod_octal_sets_readonly(workdir):
    target = workdir / "a.txt"
    target.write_text("hello\n", encoding="utf-8")

    code, out, err = run_chmod(["444", "a.txt"], cwd=workdir)

    assert code == 0
    assert out == ""
    assert err == ""
    assert _is_readonly(target)
    assert not _can_write(target)


def test_chmod_octal_clears_readonly(workdir):
    target = workdir / "a.txt"
    target.write_text("hello\n", encoding="utf-8")
    os.chmod(target, stat.S_IREAD)

    code, _, _ = run_chmod(["644", "a.txt"], cwd=workdir)

    assert code == 0
    assert not _is_readonly(target)
    assert _can_write(target)


def test_chmod_symbolic_u_minus_w(workdir):
    target = workdir / "a.txt"
    target.write_text("hello\n", encoding="utf-8")

    code, _, _ = run_chmod(["u-w", "a.txt"], cwd=workdir)

    assert code == 0
    assert _is_readonly(target)


def test_chmod_symbolic_a_plus_w(workdir):
    target = workdir / "a.txt"
    target.write_text("hello\n", encoding="utf-8")
    os.chmod(target, stat.S_IREAD)

    code, _, _ = run_chmod(["a+w", "a.txt"], cwd=workdir)

    assert code == 0
    assert not _is_readonly(target)


def test_chmod_multiple_files(workdir):
    first = workdir / "a.txt"
    second = workdir / "b.txt"
    first.write_text("1\n", encoding="utf-8")
    second.write_text("2\n", encoding="utf-8")

    code, _, _ = run_chmod(["400", "a.txt", "b.txt"], cwd=workdir)

    assert code == 0
    assert _is_readonly(first)
    assert _is_readonly(second)


def test_chmod_directory(workdir):
    sub = workdir / "sub"
    sub.mkdir()
    inner = sub / "inner.txt"
    inner.write_text("x\n", encoding="utf-8")

    code, _, _ = run_chmod(["-R", "400", "sub"], cwd=workdir)

    assert code == 0
    assert _is_readonly(sub)
    assert _is_readonly(inner)


def test_chmod_reference_uses_reference_mode(workdir):
    template = workdir / "template.txt"
    other = workdir / "other.txt"
    template.write_text("t\n", encoding="utf-8")
    other.write_text("o\n", encoding="utf-8")
    os.chmod(template, stat.S_IREAD)

    code, _, _ = run_chmod(["--reference=template.txt", "other.txt"], cwd=workdir)

    assert code == 0
    assert _is_readonly(other)


def test_chmod_group_bits_are_not_stored(workdir):
    """Windows 只有只读属性可存：600 与 644 落盘后状态一样。"""
    target = workdir / "a.txt"
    target.write_text("hello\n", encoding="utf-8")

    run_chmod(["600", "a.txt"], cwd=workdir)
    assert not _is_readonly(target)

    run_chmod(["644", "a.txt"], cwd=workdir)
    assert not _is_readonly(target)


def test_chmod_write_bit_of_any_class_keeps_writable(workdir):
    """只要还有任何一个写位，文件就不是只读（GNU 的判据）。"""
    target = workdir / "a.txt"
    target.write_text("hello\n", encoding="utf-8")

    run_chmod(["002", "a.txt"], cwd=workdir)
    assert not _is_readonly(target)

    run_chmod(["007", "a.txt"], cwd=workdir)
    assert not _is_readonly(target)


def test_chmod_without_any_write_bit_is_readonly(workdir):
    target = workdir / "a.txt"
    target.write_text("hello\n", encoding="utf-8")

    run_chmod(["040", "a.txt"], cwd=workdir)
    assert _is_readonly(target)


def test_chmod_empty_permission_list_is_accepted(workdir):
    """o= / u= / a= 是合法的：清掉那一类权限。"""
    target = workdir / "a.txt"
    target.write_text("hello\n", encoding="utf-8")

    code, out, err = run_chmod(["-v", "o=", "a.txt"], cwd=workdir)

    assert code == 0
    assert err == ""
    assert out == "mode of 'a.txt' changed from 0644 (rw-r--r--) to 0640 (rw-r-----)\n"


def test_chmod_missing_file_reports_previous_file_mode(workdir):
    """GNU 的口径：打不开的文件报的原模式是上一个处理过的文件的模式。"""
    target = workdir / "a.txt"
    target.write_text("hello\n", encoding="utf-8")
    os.chmod(target, stat.S_IREAD)

    code, out, err = run_chmod(["-v", "644", "a.txt", "missing.txt"], cwd=workdir)

    assert code == 2
    assert (
        "failed to change mode of 'missing.txt' from 0444 (r--r--r--) to 0644 (rw-r--r--)"
        in out
    )
    assert "无法访问 'missing.txt'" in err


# ---------- 选项组合 ----------


def test_chmod_verbose_reports_changed(workdir):
    target = workdir / "a.txt"
    target.write_text("hello\n", encoding="utf-8")

    code, out, err = run_chmod(["-v", "444", "a.txt"], cwd=workdir)

    assert code == 0
    assert err == ""
    assert out == "mode of 'a.txt' changed from 0644 (rw-r--r--) to 0444 (r--r--r--)\n"


def test_chmod_verbose_reports_retained(workdir):
    target = workdir / "a.txt"
    target.write_text("hello\n", encoding="utf-8")

    code, out, _ = run_chmod(["-v", "644", "a.txt"], cwd=workdir)

    assert code == 0
    assert out == "mode of 'a.txt' retained as 0644 (rw-r--r--)\n"


def test_chmod_changes_only_reports_real_change(workdir):
    target = workdir / "a.txt"
    other = workdir / "b.txt"
    target.write_text("hello\n", encoding="utf-8")
    other.write_text("world\n", encoding="utf-8")
    os.chmod(other, stat.S_IREAD)

    code, out, _ = run_chmod(["-c", "444", "a.txt", "b.txt"], cwd=workdir)

    assert code == 0
    assert "a.txt" in out
    assert "b.txt" not in out


def test_chmod_verbose_and_changes_together(workdir):
    target = workdir / "a.txt"
    target.write_text("hello\n", encoding="utf-8")

    code, out, _ = run_chmod(["-v", "-c", "444", "a.txt"], cwd=workdir)

    assert code == 0
    assert "changed from 0644" in out


def test_chmod_silent_suppresses_error(workdir):
    code, out, err = run_chmod(["-f", "644", "missing.txt"], cwd=workdir)

    assert code == 2
    assert out == ""
    assert err == ""


def test_chmod_verbose_reports_missing_file(workdir):
    code, out, err = run_chmod(["-v", "644", "missing.txt"], cwd=workdir)

    assert code == 2
    assert "failed to change mode of 'missing.txt' from 0644 (rw-r--r--) to 0644 (rw-r--r--)" in out
    assert "无法访问 'missing.txt'" in err


def test_chmod_recursive_verbose_lists_children(workdir):
    sub = workdir / "sub"
    sub.mkdir()
    (sub / "inner.txt").write_text("x\n", encoding="utf-8")

    code, out, _ = run_chmod(["-v", "-R", "444", "sub"], cwd=workdir)

    assert code == 0
    assert "mode of 'sub' changed from 0755 (rwxr-xr-x) to 0444 (r--r--r--)" in out
    assert "mode of 'sub/inner.txt' changed from 0644 (rw-r--r--) to 0444 (r--r--r--)" in out


def test_chmod_ls_shows_the_same_permissions(workdir):
    """chmod 之后 ls -l 的权限列要和 chmod 的报数对得上。"""
    target = workdir / "a.txt"
    target.write_text("hello\n", encoding="utf-8")

    run_chmod(["444", "a.txt"], cwd=workdir)
    code, out, _ = run_ls(["-l", "a.txt"], cwd=workdir)

    assert code == 0
    assert out.startswith("-r--r--r--")


def test_chmod_ls_shows_writable_permissions(workdir):
    target = workdir / "a.txt"
    target.write_text("hello\n", encoding="utf-8")

    code, out, _ = run_ls(["-l", "a.txt"], cwd=workdir)

    assert code == 0
    assert out.startswith("-rw-r--r--")


# ---------- 错误路径 ----------


def test_chmod_missing_file(workdir):
    code, out, err = run_chmod(["644", "missing.txt"], cwd=workdir)

    assert code == 2
    assert out == ""
    assert "无法访问 'missing.txt'" in err


def test_chmod_invalid_mode(workdir):
    target = workdir / "a.txt"
    target.write_text("hello\n", encoding="utf-8")

    code, _, err = run_chmod(["999", "a.txt"], cwd=workdir)

    assert code == 2
    assert "非法模式: '999'" in err


def test_chmod_invalid_octal_digit(workdir):
    target = workdir / "a.txt"
    target.write_text("hello\n", encoding="utf-8")

    code, _, err = run_chmod(["08", "a.txt"], cwd=workdir)

    assert code == 2
    assert "非法模式: '08'" in err


def test_chmod_invalid_symbolic_mode(workdir):
    target = workdir / "a.txt"
    target.write_text("hello\n", encoding="utf-8")

    code, _, err = run_chmod(["u+rw,q", "a.txt"], cwd=workdir)

    assert code == 2
    assert "非法模式" in err


def test_chmod_without_mode(workdir):
    code, _, err = run_chmod([], cwd=workdir)

    assert code == 2
    assert "缺少操作数" in err


def test_chmod_mode_without_file(workdir):
    code, _, err = run_chmod(["644"], cwd=workdir)

    assert code == 2
    assert "缺少操作数" in err


def test_chmod_reference_missing_file(workdir):
    target = workdir / "a.txt"
    target.write_text("hello\n", encoding="utf-8")

    code, _, err = run_chmod(["--reference=missing.txt", "a.txt"], cwd=workdir)

    assert code == 2
    assert "无法访问 'missing.txt'" in err
    assert not _is_readonly(target)


def test_chmod_refuses_filesystem_root(workdir):
    """根目录默认拒绝操作（比 GNU 的默认更保守）。"""
    root = str(workdir.anchor)

    code, _, err = run_chmod(["-R", "755", root], cwd=workdir)

    assert code == 2
    assert "拒绝操作根目录" in err
