"""tail 指令测试。

对照的是 Git Bash 里 GNU coreutils 8.32 的 tail 实测输出：
默认末 10 行、-n 指定行数、-c 指定字节数（两个都给时后写的生效）、
计数带正负号（`+N` 是「从第 N 个开始」，这与 head 相反；`-N` 与 `N` 同义；
0 与 +0 含义不同）、乘数后缀（b=512、k/K=1024、kB=1000、KiB=K）、
多文件的 `==> 文件名 <==` 标题与标题前的空行、-q 不打标题、
-v 强制打标题（两者同开时后写的生效）、打不开的文件不打标题只报错、
目录先打标题再报「是一个目录」、- 表示标准输入、不给操作数读标准输入、
-z 用 NUL 当行分隔符、CRLF 原样转交、末行无换行不补换行、
紧凑写法 -NUM、-f 跟随时半行要等换行符到了才输出。
"""

import io
import subprocess
import sys
import threading
import time

import pytest

from conftest import ROOT, build_tail_namespace, run_tail
from w2l.commands.tail import (
    _Follower,
    _follow_loop,
    _Options,
    tail,
)
from w2l.context import RunContext
from w2l.errors import UsageError


class _RecordingStream(io.StringIO):
    """记下 flush 被调用了几次的 StringIO。"""

    def __init__(self) -> None:
        super().__init__()
        self.flushes = 0

    def flush(self) -> None:
        self.flushes += 1
        super().flush()


@pytest.fixture
def tail_tree(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"l1\nl2\nl3\nl4\nl5\n")
    (tmp_path / "b.txt").write_bytes(b"x\n")
    (tmp_path / "nonl.txt").write_bytes(b"p1\np2\np3")
    (tmp_path / "empty.txt").write_bytes(b"")
    (tmp_path / "blank.txt").write_bytes(b"b1\n\nb3\n")
    (tmp_path / "crlf.txt").write_bytes(b"c1\r\nc2\r\nc3\r\n")
    (tmp_path / "zeros.bin").write_bytes(b"z1\x00z2\x00z3\x00")
    (tmp_path / "bin.dat").write_bytes(bytes(range(256)))
    sub = tmp_path / "sub"
    sub.mkdir()
    return tmp_path


def _follow_options(**overrides):
    """跟随时用的选项对象。"""
    base = dict(
        mode="lines",
        direction="last",
        amount=10,
        header_mode=None,
        zero_terminated=False,
        follow="descriptor",
        sleep_interval=0.0,
        pid=None,
        retry=False,
    )
    base.update(overrides)
    return _Options(**base)


def _make_follower(path, delimiter=b"\n"):
    """造一个跟随时用的 _Follower，并让它从文件末尾开始盯。"""
    handle = path.open("rb")
    follower = _Follower(path.name, path, handle, by_name=False, delimiter=delimiter)
    follower.position = path.stat().st_size
    follower.encoding = "utf-8"
    return follower, handle


# ---------- 正常路径 ----------


def test_prints_last_ten_lines_by_default(tail_tree):
    code, out, err = run_tail([str(tail_tree / "a.txt")])
    assert code == 0
    assert out == "l1\nl2\nl3\nl4\nl5\n"
    assert err == ""


def test_lines_option_limits_output(tail_tree):
    code, out, _ = run_tail(["-n", "2", str(tail_tree / "a.txt")])
    assert code == 0
    assert out == "l4\nl5\n"


def test_bytes_option_limits_output(tail_tree):
    code, out, _ = run_tail(["-c", "5", str(tail_tree / "a.txt")])
    assert code == 0
    assert out == "4\nl5\n"


def test_reads_stdin_when_no_operand(tail_tree):
    code, out, _ = run_tail([], cwd=tail_tree, stdin_text="from stdin\n")
    assert code == 0
    assert out == "from stdin\n"


def test_dash_means_stdin(tail_tree):
    code, out, _ = run_tail(["-"], cwd=tail_tree, stdin_text="from stdin\n")
    assert code == 0
    assert out == "from stdin\n"


def test_crlf_is_passed_through(tail_tree):
    """CRLF 文件的 \\r 属于行内容，必须原样转交。"""
    code, out, _ = run_tail(["-n", "2", str(tail_tree / "crlf.txt")])
    assert code == 0
    assert out == "c2\r\nc3\r\n"


def test_last_line_without_newline_is_not_padded(tail_tree):
    code, out, _ = run_tail([str(tail_tree / "nonl.txt")])
    assert code == 0
    assert out == "p1\np2\np3"


def test_empty_file_produces_no_output(tail_tree):
    code, out, err = run_tail([str(tail_tree / "empty.txt")])
    assert code == 0
    assert out == ""
    assert err == ""


def test_binary_content_is_passed_through(tail_tree):
    code, out, _ = run_tail([str(tail_tree / "bin.dat")])
    assert code == 0
    assert out.encode("utf-8", errors="surrogateescape") == bytes(range(256))


def test_blank_line_counts_as_a_line(tail_tree):
    code, out, _ = run_tail(["-n", "2", str(tail_tree / "blank.txt")])
    assert code == 0
    assert out == "\nb3\n"


# ---------- 选项组合 ----------


def test_multiple_files_get_headers(tail_tree):
    """第二个及以后的标题前先空一行。"""
    code, out, _ = run_tail([str(tail_tree / "a.txt"), str(tail_tree / "b.txt")])
    assert code == 0
    assert out == "==> %s <==\nl1\nl2\nl3\nl4\nl5\n\n==> %s <==\nx\n" % (
        tail_tree / "a.txt",
        tail_tree / "b.txt",
    )


def test_quiet_suppresses_headers(tail_tree):
    code, out, _ = run_tail(["-q", str(tail_tree / "a.txt"), str(tail_tree / "b.txt")])
    assert code == 0
    assert out == "l1\nl2\nl3\nl4\nl5\nx\n"


def test_verbose_forces_header_for_single_file(tail_tree):
    code, out, _ = run_tail(["-v", str(tail_tree / "a.txt")])
    assert code == 0
    assert out.startswith("==> ")


def test_quiet_and_verbose_last_one_wins(tail_tree):
    """GNU 里 -q 与 -v 同时给时，后写的那个生效。"""
    code, out, _ = run_tail(["-q", "-v", str(tail_tree / "a.txt"), str(tail_tree / "b.txt")])
    assert code == 0
    assert "==>" in out

    code, out, _ = run_tail(["-v", "-q", str(tail_tree / "a.txt"), str(tail_tree / "b.txt")])
    assert code == 0
    assert "==>" not in out


def test_lines_and_bytes_last_one_wins(tail_tree):
    """-c 7 -n 2 取 2 行，-n 2 -c 7 取 7 字节。"""
    code, out, _ = run_tail(["-c", "7", "-n", "2", str(tail_tree / "a.txt")])
    assert code == 0
    assert out == "l4\nl5\n"

    code, out, _ = run_tail(["-n", "2", "-c", "7", str(tail_tree / "a.txt")])
    assert code == 0
    assert out == "\nl4\nl5\n"


def test_plus_sign_means_start_from_that_line(tail_tree):
    """tail 的 +N 是「从第 N 行开始」，与 head 相反。"""
    code, out, _ = run_tail(["-n", "+2", str(tail_tree / "a.txt")])
    assert code == 0
    assert out == "l2\nl3\nl4\nl5\n"


def test_plus_zero_means_everything(tail_tree):
    code, out, _ = run_tail(["-n", "+0", str(tail_tree / "a.txt")])
    assert code == 0
    assert out == "l1\nl2\nl3\nl4\nl5\n"


def test_plus_beyond_end_of_file_gives_nothing(tail_tree):
    code, out, _ = run_tail(["-n", "+99", str(tail_tree / "a.txt")])
    assert code == 0
    assert out == ""


def test_negative_count_is_same_as_positive(tail_tree):
    """tail 里 -N 与 N 同义，都是取末尾 N 个。"""
    code, out, _ = run_tail(["-n", "-2", str(tail_tree / "a.txt")])
    assert code == 0
    assert out == "l4\nl5\n"


def test_zero_and_plus_zero_differ(tail_tree):
    """-n 0 一个不要，-n +0 全部都要。"""
    code, out, _ = run_tail(["-n", "0", str(tail_tree / "a.txt")])
    assert code == 0
    assert out == ""

    code, out, _ = run_tail(["-n", "+0", str(tail_tree / "a.txt")])
    assert code == 0
    assert out == "l1\nl2\nl3\nl4\nl5\n"


def test_bytes_plus_means_start_from_that_byte(tail_tree):
    code, out, _ = run_tail(["-c", "+5", str(tail_tree / "a.txt")])
    assert code == 0
    assert out == "2\nl3\nl4\nl5\n"


def test_bytes_plus_zero_means_everything(tail_tree):
    code, out, _ = run_tail(["-c", "+0", str(tail_tree / "a.txt")])
    assert code == 0
    assert out == "l1\nl2\nl3\nl4\nl5\n"


def test_compact_numeric_option(tail_tree):
    """GNU 的 -NUM 紧凑写法等价于 -n NUM。"""
    code, out, _ = run_tail(["-2", str(tail_tree / "a.txt")])
    assert code == 0
    assert out == "l4\nl5\n"


def test_long_option_forms(tail_tree):
    code, out, _ = run_tail(["--lines=2", str(tail_tree / "a.txt")])
    assert code == 0
    assert out == "l4\nl5\n"

    code, out, _ = run_tail(["--bytes=5", str(tail_tree / "a.txt")])
    assert code == 0
    assert out == "4\nl5\n"

    code, out, _ = run_tail(["--lines=+2", str(tail_tree / "a.txt")])
    assert code == 0
    assert out == "l2\nl3\nl4\nl5\n"


def test_multiplier_suffixes(tail_tree):
    """b=512、k/K=1024、kB=1000、KiB=K。"""
    (tail_tree / "big.txt").write_bytes(b"X" * 2000)

    code, out, _ = run_tail(["-c", "1b", str(tail_tree / "big.txt")])
    assert code == 0
    assert len(out) == 512

    code, out, _ = run_tail(["-c", "1k", str(tail_tree / "big.txt")])
    assert code == 0
    assert len(out) == 1024

    code, out, _ = run_tail(["-c", "1kB", str(tail_tree / "big.txt")])
    assert code == 0
    assert len(out) == 1000

    code, out, _ = run_tail(["-c", "1KiB", str(tail_tree / "big.txt")])
    assert code == 0
    assert len(out) == 1024


def test_lines_suffix_multiplies_line_count(tail_tree):
    """-n 的后缀乘的是行数：1b 就是 512 行。"""
    (tail_tree / "many.txt").write_bytes(b"".join(b"n%03d\n" % i for i in range(600)))

    code, out, _ = run_tail(["-n", "1b", str(tail_tree / "many.txt")])
    assert code == 0
    assert out.count("\n") == 512


def test_zero_terminated_uses_nul_as_delimiter(tail_tree):
    code, out, _ = run_tail(["-z", "-n", "2", str(tail_tree / "zeros.bin")])
    assert code == 0
    assert out == "z2\x00z3\x00"


def test_stdin_header_uses_standard_input(tail_tree):
    code, out, _ = run_tail(["-v", "-"], cwd=tail_tree, stdin_text="s1\ns2\n")
    assert code == 0
    assert out == "==> standard input <==\ns1\ns2\n"


def test_options_may_follow_operands(tail_tree):
    """GNU 的选项重排：选项写在操作数后面照样生效。"""
    code, out, _ = run_tail([str(tail_tree / "a.txt"), "-n", "2"])
    assert code == 0
    assert out == "l4\nl5\n"


# ---------- 跟随模式 ----------


def test_follow_outputs_appended_lines(tmp_path):
    target = tmp_path / "log.txt"
    target.write_bytes(b"first\n")
    follower, handle = _make_follower(target)
    out = io.StringIO()
    ctx = RunContext(
        cwd=tmp_path, stdout=out, stderr=io.StringIO(), stdin=io.StringIO("")
    )
    try:
        with target.open("ab") as writer:
            writer.write(b"second\n")
        _follow_loop([follower], _follow_options(), ctx, max_iterations=1)
        assert out.getvalue() == "second\n"
    finally:
        handle.close()


def test_follow_holds_back_partial_line(tmp_path):
    """写了一半的行要等换行符到了才输出。"""
    target = tmp_path / "log.txt"
    target.write_bytes(b"first\n")
    follower, handle = _make_follower(target)
    out = io.StringIO()
    ctx = RunContext(
        cwd=tmp_path, stdout=out, stderr=io.StringIO(), stdin=io.StringIO("")
    )
    try:
        with target.open("ab") as writer:
            writer.write(b"half")
        _follow_loop([follower], _follow_options(), ctx, max_iterations=1)
        assert out.getvalue() == ""

        with target.open("ab") as writer:
            writer.write(b" done\n")
        _follow_loop([follower], _follow_options(), ctx, max_iterations=1)
        assert out.getvalue() == "half done\n"
    finally:
        handle.close()


def test_follow_option_is_parsed_as_descriptor_by_default(tmp_path):
    """单独一个 -f 表示按文件描述符跟随，不吃掉后面的文件名。"""
    namespace = build_tail_namespace(["-f", "a.txt"])
    assert namespace.follow == "descriptor"
    assert namespace.files == ["a.txt"]


def test_follow_name_variant(tmp_path):
    namespace = build_tail_namespace(["-F", "a.txt"])
    assert namespace.follow_name is True


def test_follow_flushes_output_after_each_chunk(tmp_path):
    """跟随时必须刷缓冲：接管道时 Python 默认块缓冲，不刷就看不见。"""
    target = tmp_path / "log.txt"
    target.write_bytes(b"first\n")
    follower, handle = _make_follower(target)
    stream = _RecordingStream()
    ctx = RunContext(
        cwd=tmp_path, stdout=stream, stderr=io.StringIO(), stdin=io.StringIO("")
    )
    try:
        with target.open("ab") as writer:
            writer.write(b"second\n")
        _follow_loop([follower], _follow_options(), ctx, max_iterations=1)
        assert stream.getvalue() == "second\n"
        assert stream.flushes > 0
    finally:
        handle.close()


def test_follow_by_name_picks_up_replaced_file(tmp_path):
    """按文件名跟随时，文件被轮转掉要跟到新文件。"""
    target = tmp_path / "rotate.log"
    target.write_bytes(b"old1\nold2\n")
    follower = _Follower("rotate.log", target, None, by_name=True)
    follower.position = target.stat().st_size
    follower.encoding = "utf-8"
    out = io.StringIO()
    ctx = RunContext(
        cwd=tmp_path, stdout=out, stderr=io.StringIO(), stdin=io.StringIO("")
    )

    # 先轮询一次，让跟随器记住原文件的样子
    assert follower.poll() == b""

    # 轮转：改名 + 建新文件
    target.rename(tmp_path / "rotate.log.1")
    target.write_bytes(b"new1\n")

    assert follower.poll() == b"new1\n"


def test_follow_command_streams_output_immediately(tmp_path):
    """端到端验一次：`tail -f` 接管道时新行要马上出现。

    这条守的是块缓冲那个坑——不刷缓冲时输出会一直卡在 Python 的
    8KB 缓冲区里，用户看半天没反应。
    """
    target = tmp_path / "log.txt"
    target.write_bytes(b"first\n")
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "main.py"), "tail", "-f", str(target)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    collected = bytearray()

    def reader():
        while True:
            chunk = proc.stdout.read(1)
            if not chunk:
                break
            collected.extend(chunk)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    try:
        with target.open("ab") as writer:
            writer.write(b"second\n")
        deadline = time.time() + 15
        while time.time() < deadline and b"second\n" not in collected:
            time.sleep(0.1)
        assert b"first\n" in bytes(collected)
        assert b"second\n" in bytes(collected)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# ---------- 错误路径 ----------


def test_missing_file_reports_error_and_returns_two(tail_tree):
    code, out, err = run_tail([str(tail_tree / "nope.txt")])
    assert code == 2
    assert out == ""
    assert "nope.txt" in err


def test_missing_file_gets_no_header(tail_tree):
    """打不开的文件不打标题。"""
    code, out, err = run_tail(
        ["-v", str(tail_tree / "a.txt"), str(tail_tree / "nope.txt")]
    )
    assert code == 2
    assert out.count("==>") == 1
    assert "nope.txt" not in out
    assert "nope.txt" in err


def test_directory_reports_error_but_keeps_going(tail_tree):
    """目录会先打标题再报读取错误，后面的文件照常输出。"""
    code, out, err = run_tail(
        [str(tail_tree / "a.txt"), str(tail_tree / "sub"), str(tail_tree / "b.txt")]
    )
    assert code == 2
    assert out.startswith("==> ")
    assert "是一个目录" in err
    assert "x\n" in out


def test_invalid_count_is_usage_error(tail_tree):
    namespace = build_tail_namespace(["-n", "abc", str(tail_tree / "a.txt")])
    ctx = RunContext(
        cwd=tail_tree, stdout=io.StringIO(), stderr=io.StringIO(), stdin=io.StringIO("")
    )
    with pytest.raises(UsageError):
        tail(namespace, ctx)


def test_invalid_suffix_is_usage_error(tail_tree):
    namespace = build_tail_namespace(["-c", "1kb", str(tail_tree / "a.txt")])
    ctx = RunContext(
        cwd=tail_tree, stdout=io.StringIO(), stderr=io.StringIO(), stdin=io.StringIO("")
    )
    with pytest.raises(UsageError):
        tail(namespace, ctx)


def test_out_of_range_count_is_usage_error(tail_tree):
    namespace = build_tail_namespace(["-n", "99999999999999999999", str(tail_tree / "a.txt")])
    ctx = RunContext(
        cwd=tail_tree, stdout=io.StringIO(), stderr=io.StringIO(), stdin=io.StringIO("")
    )
    with pytest.raises(UsageError):
        tail(namespace, ctx)


def test_missing_option_value_is_usage_error():
    with pytest.raises(SystemExit) as excinfo:
        run_tail(["-n"])
    assert excinfo.value.code == 2


def test_unknown_option_is_usage_error():
    with pytest.raises(SystemExit) as excinfo:
        run_tail(["--bogus"])
    assert excinfo.value.code == 2


def test_help_flag_exits_zero(capsys):
    with pytest.raises(SystemExit) as excinfo:
        run_tail(["--help"])
    assert excinfo.value.code == 0
    assert "打印文件末尾部分" in capsys.readouterr().out
