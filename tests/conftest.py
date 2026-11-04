import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from w2l.commands.cat import build_parser as build_cat_parser  # noqa: E402
from w2l.commands.cat import cat  # noqa: E402
from w2l.commands.grep import build_parser, grep  # noqa: E402
from w2l.commands.head import build_parser as build_head_parser  # noqa: E402
from w2l.commands.head import head  # noqa: E402
from w2l.commands.ls import build_parser as build_ls_parser  # noqa: E402
from w2l.commands.ls import ls  # noqa: E402
from w2l.commands.tail import build_parser as build_tail_parser  # noqa: E402
from w2l.commands.tail import tail  # noqa: E402
from w2l.context import RunContext  # noqa: E402


class _Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


def run_grep(argv, cwd=None, stdin_text=""):
    namespace = build_parser().parse_args(list(argv))
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(
        cwd=Path(cwd or ROOT),
        stdout=out,
        stderr=err,
        stdin=io.StringIO(stdin_text),
    )
    code = grep(namespace, ctx)
    return code, out.getvalue(), err.getvalue()


def run_ls(argv, cwd=None):
    """跑一次 ls 指令，返回 (退出码, 标准输出, 标准输出)。"""
    namespace = build_ls_parser().parse_args(list(argv))
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(
        cwd=Path(cwd or ROOT),
        stdout=out,
        stderr=err,
        stdin=io.StringIO(""),
    )
    code = ls(namespace, ctx)
    return code, out.getvalue(), err.getvalue()


def run_cat(argv, cwd=None, stdin_text=""):
    """跑一次 cat 指令，返回 (退出码, 标准输出, 标准错误)。"""
    namespace = build_cat_parser().parse_args(list(argv))
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(
        cwd=Path(cwd or ROOT),
        stdout=out,
        stderr=err,
        stdin=io.StringIO(stdin_text),
    )
    code = cat(namespace, ctx)
    return code, out.getvalue(), err.getvalue()


def run_head(argv, cwd=None, stdin_text=""):
    """跑一次 head 指令，返回 (退出码, 标准输出, 标准错误)。"""
    namespace = build_head_parser().parse_args(list(argv))
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(
        cwd=Path(cwd or ROOT),
        stdout=out,
        stderr=err,
        stdin=io.StringIO(stdin_text),
    )
    code = head(namespace, ctx)
    return code, out.getvalue(), err.getvalue()


def build_head_namespace(argv):
    """只解析 head 的参数，不执行指令，用于检查用法错误。"""
    return build_head_parser().parse_args(list(argv))


def run_tail(argv, cwd=None, stdin_text=""):
    """跑一次 tail 指令，返回 (退出码, 标准输出, 标准错误)。"""
    namespace = build_tail_parser().parse_args(list(argv))
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(
        cwd=Path(cwd or ROOT),
        stdout=out,
        stderr=err,
        stdin=io.StringIO(stdin_text),
    )
    code = tail(namespace, ctx)
    return code, out.getvalue(), err.getvalue()


def build_tail_namespace(argv):
    """只解析 tail 的参数，不执行指令，用于检查用法错误。"""
    return build_tail_parser().parse_args(list(argv))


@pytest.fixture
def sample_tree(tmp_path):
    (tmp_path / "app.log").write_text(
        "INFO start\nERROR failed\nwarn retry\nERROR again\n", encoding="utf-8"
    )
    (tmp_path / "notes.txt").write_text("alpha\nBeta\ngamma\n", encoding="utf-8")
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "deep.txt").write_text("error in deep\nnothing here\n", encoding="utf-8")
    return tmp_path
