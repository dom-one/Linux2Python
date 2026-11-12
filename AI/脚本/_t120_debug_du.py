"""调试：看 du 扫描时每个文件到底记了什么。"""

from __future__ import annotations

import os
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "AI" / "数据" / "du_diff"

lines: list[str] = []
tree = BASE / "tree"

lines.append("### os.scandir 的 stat（follow_symlinks=False）")
with os.scandir(tree) as scanner:
    for item in scanner:
        st = item.stat(follow_symlinks=False)
        lines.append(
            f"{item.name}: size={st.st_size} dev={st.st_dev} ino={st.st_ino} "
            f"isdir={stat.S_ISDIR(st.st_mode)}"
        )

lines.append("")
lines.append("### os.stat / os.lstat 对比")
for name in ("a.txt", "b.txt", "c.txt", "zero.txt"):
    p = tree / name
    st_l = p.lstat()
    st_s = p.stat()
    lines.append(
        f"{name}: lstat(size={st_l.st_size} dev={st_l.st_dev} ino={st_l.st_ino}) "
        f"stat(size={st_s.st_size} dev={st_s.st_dev} ino={st_s.st_ino})"
    )

lines.append("")
lines.append("### 主进程看到的 stat（走 w2l 的路径解析）")
from w2l.commands.du import build_parser, du  # noqa: E402
from w2l.context import RunContext  # noqa: E402
import io  # noqa: E402

ns = build_parser().parse_args(["-a", "tree"])
out, err = io.StringIO(), io.StringIO()
ctx = RunContext(cwd=BASE, stdout=out, stderr=err, stdin=io.StringIO(""))
code = du(ns, ctx)
lines.append(f"exit={code}")
lines.append(f"stdout={out.getvalue()!r}")
lines.append(f"stderr={err.getvalue()!r}")

out_file = ROOT / "AI" / "数据" / "du_diff" / "debug_out.txt"
out_file.write_text("\n".join(lines), encoding="utf-8")
print(f"written: {out_file}")
