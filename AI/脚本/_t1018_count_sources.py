"""统计 w2l/commands/ 各实现的行数与 tests/ 各文件的用例数。

给 teach/00 的结构树用。teach/00 里的行数与用例数是「只有文字佐证」的数字，
核对器查不到，得现算。

用法：python AI/脚本/_t1018_count_sources.py
"""
from __future__ import annotations

import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def main() -> None:
    print("一、w2l/commands/ 各实现的行数")
    for path in sorted((ROOT / "w2l" / "commands").glob("*.py")):
        n = len(path.read_text(encoding="utf-8").splitlines())
        print("  %-16s %5d 行" % (path.name, n))

    print("\n二、tests/ 各文件的用例数")
    total = 0
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        n = len([x.name for x in tree.body
                 if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and x.name.startswith("test_")])
        total += n
        print("  %-20s %5d 个用例" % (path.name, n))
    print("  合计 %d 个用例" % total)


if __name__ == "__main__":
    main()
