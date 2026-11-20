"""分诊：上一轮两个探针对同一条命令给出过矛盾结论，到底哪个错？

矛盾点：
  - AI/数据/find_fix/eval_table.txt 的「测试-o-动作」(`-name *.txt -o -printf R\\n`) 报 1 个 R
  - AI/数据/find_fix/gnu_truth.txt 的「eval-o-左测试右动作」（同一条命令）报 2 个 R

判据：把每条用例的**原始 .out 字节**与报告里写的 stdout 逐条比对。
  - 若 .out 字节与报告一致 → 报告没错，是两次探针的**夹具/命令**不同，结论不矛盾
  - 若 .out 字节与报告不一致 → 报告生成逻辑有 bug，报告不可信
另外把两种夹具的目录清单打出来，看两次探针的夹具是不是同一个形状。

用法: python AI/脚本/_t823_probe_find_report_audit.py
产出: AI/数据/find_fix/report_audit.txt
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
BASE = AI_DIR / "数据" / "find_fix"


def parse_report(path: Path, prefix: str) -> list[tuple[str, str]]:
    """从探针报告里解析出 (标题, stdout 的 repr 字面量)。"""
    text = path.read_text(encoding="utf-8")
    out: list[tuple[str, str]] = []
    title = None
    for line in text.splitlines():
        if line.startswith("### "):
            title = line[4:].strip()
        if line.startswith("stdout: ") and title is not None:
            literal = line[len("stdout: "):].strip()
            out.append((title, literal))
            title = None
    return out


def main() -> int:
    lines: list[str] = ["# 由 _t823_probe_find_report_audit.py 生成，勿手改", ""]

    for report_name, prefix in (("eval_table.txt", "evaltable"), ("gnu_truth.txt", "gnucase")):
        report = BASE / report_name
        if not report.exists():
            lines.append(f"## {report_name}: 文件不存在")
            continue
        lines.append("=" * 72)
        lines.append(f"## {report_name}")
        entries = parse_report(report, prefix)
        lines.append(f"报告条目数: {len(entries)}")
        for index, (title, literal) in enumerate(entries):
            raw_path = BASE / f"{prefix}_{index:02d}.out"
            raw = raw_path.read_bytes() if raw_path.exists() else None
            try:
                claimed = ast.literal_eval(literal)
            except (ValueError, SyntaxError):
                claimed = f"<无法解析: {literal}>"
            if raw is None:
                lines.append(f"{index:02d} {title}: 缺 .out 文件")
                continue
            actual = raw.decode("utf-8", "replace")
            mark = "一致" if actual == claimed else "★不一致★"
            lines.append(
                f"{index:02d} {title}: {mark}"
                f"  报告={claimed!r} 实际字节={actual!r} 字节数={len(raw)}"
            )

    # 两次探针的夹具形状对比
    lines.append("=" * 72)
    lines.append("## 两次探针的夹具")
    for tree in sorted(BASE.glob("tree*")):
        if not tree.is_dir():
            continue
        entries = sorted(
            p.relative_to(tree).as_posix() + ("/" if p.is_dir() else "")
            for p in tree.rglob("*")
        )
        lines.append(f"{tree.name}: {entries}")

    (BASE / "report_audit.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"审计 -> {BASE / 'report_audit.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
