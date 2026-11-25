"""探针：ls -R 遇上 -a 时的递归行为（. 与 .. 会被当成子目录递归进去）。

要做两件事：
1. 复现现状：跑本项目的 ls -Ra，看是不是无限递归（RecursionError）。
2. 取基准：跑 GNU ls -Ra，看 GNU 是什么行为（. 与 .. 只出现在列表里，不递归进去）。

用法：python AI/脚本/_t1602_probe_ls_recursive.py
报告落盘到 AI/脚本/_t1602_ls_recursive_report.txt
"""

from __future__ import annotations

import io
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from w2l.commands.ls import build_parser as build_ls_parser  # noqa: E402
from w2l.commands.ls import ls  # noqa: E402
from w2l.context import RunContext  # noqa: E402

REPORT = Path(__file__).with_name("_t1602_ls_recursive_report.txt")

GNU_LS = r"E:\software\Git\Git\usr\bin\ls.exe"


def run_ls(argv: list[str], cwd: Path) -> tuple[int, str, str]:
    namespace = build_ls_parser().parse_args(list(argv))
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(cwd=cwd, stdout=out, stderr=err, stdin=io.StringIO(""))
    code = ls(namespace, ctx)
    return code, out.getvalue(), err.getvalue()


def build_fixture(root: Path) -> None:
    (root / "a.txt").write_bytes(b"hi\n")
    sub = root / "sub"
    sub.mkdir()
    (sub / "b.txt").write_bytes(b"hi\n")


def main() -> int:
    lines: list[str] = []
    with tempfile.TemporaryDirectory(prefix="w2l_lsra_") as tmp:
        root = Path(tmp)
        build_fixture(root)

        lines.append("=== GNU ls -Ra 的参考输出 ===")
        if Path(GNU_LS).is_file():
            proc = subprocess.run(
                [GNU_LS, "-Ra", "."],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            lines.append(f"exit={proc.returncode}")
            lines.append(proc.stdout.rstrip("\n"))
            lines.append("")
        else:
            lines.append("（没找到 GNU ls，跳过基准）")
            lines.append("")

        lines.append("=== 本项目 ls -Ra 的现状 ===")
        try:
            code, out, err = run_ls(["-Ra", "."], root)
            lines.append(f"exit={code}")
            lines.append(out.rstrip("\n"))
            if err.strip():
                lines.append("stderr: " + err.strip())
            lines.append("")
            lines.append("结论：正常返回，没有无限递归")
        except RecursionError as exc:
            lines.append(f"RecursionError: {exc}")
            lines.append("")
            lines.append("结论：无限递归——. 与 .. 被当成子目录又递归进去")
            lines.append("（. 递归回自己，.. 递归到上一级，两条都停不下来）")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[probe_ls_recursive] report={REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
