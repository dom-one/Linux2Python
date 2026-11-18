"""排查：chmod a+w 为什么没把只读属性清掉。"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from w2l.commands.chmod import build_parser  # noqa: E402
from w2l.context import RunContext  # noqa: E402
import io  # noqa: E402


def run(argv, cwd):
    namespace = build_parser().parse_args(list(argv))
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(cwd=cwd, stdout=out, stderr=err, stdin=io.StringIO(""))
    code = namespace and None
    from w2l.commands.chmod import chmod

    code = chmod(namespace, ctx)
    return code, out.getvalue(), err.getvalue()


def show(label, path: Path) -> None:
    st = os.stat(path)
    print(f"  {label}: mode={oct(st.st_mode)} S_IWRITE={'有' if st.st_mode & stat.S_IWRITE else '无'}")


def main() -> int:
    work = ROOT / "AI" / "数据" / "chmod_debug"
    work.mkdir(parents=True, exist_ok=True)
    target = work / "a.txt"
    target.write_text("hello\n", encoding="utf-8")

    print("初始：")
    show("a.txt", target)

    os.chmod(target, stat.S_IREAD)
    print("os.chmod(S_IREAD) 之后：")
    show("a.txt", target)

    code, out, err = run(["a+w", "a.txt"], work)
    print(f"chmod a+w -> rc={code} out={out!r} err={err!r}")
    show("a.txt", target)

    print()
    print("直接试 os.chmod(S_IREAD|S_IWRITE)：")
    os.chmod(target, stat.S_IREAD | stat.S_IWRITE)
    show("a.txt", target)

    os.chmod(target, stat.S_IREAD)
    show("再设只读", target)
    os.chmod(target, stat.S_IREAD | stat.S_IWRITE)
    show("再清只读", target)

    os.chmod(target, stat.S_IREAD)
    show("再设只读", target)
    os.chmod(target, 0o666)
    show("os.chmod(0o666)", target)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
