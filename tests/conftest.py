import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from w2l.commands.grep import build_parser, grep  # noqa: E402
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
