"""把本 tick 的交付文件登记进过滤器索引。

直接跑 登记.py 的 main()，路径与标题走 argv，
免得中文路径在 shell 里被 MSYS 改写。
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

REGISTER = Path(r"E:\1data\过滤器\脚本\登记.py")

ITEMS = [
    (
        str(ROOT / "w2l" / "commands" / "chmod.py"),
        "chmod：修改文件权限（GNU chmod 风格子集）",
    ),
    (
        str(ROOT / "w2l" / "perms.py"),
        "权限口径：Windows 合成权限位折算成 POSIX 常见口径（MSYS 同款）",
    ),
    (
        str(ROOT / "tests" / "test_chmod.py"),
        "chmod 指令的测试（正常路径、选项组合、错误路径）",
    ),
    (
        str(ROOT / "README.md"),
        "Windows-to-Linux 项目说明（含 chmod 能力清单）",
    ),
]


def main() -> int:
    failed = 0
    for path, title in ITEMS:
        argv = [
            "登记.py",
            "--来源",
            "Linux命令",
            "--路径",
            path,
            "--标题",
            title,
            "--关联",
            "无",
        ]
        sys.argv = argv
        try:
            runpy.run_path(str(REGISTER), run_name="__main__")
        except SystemExit as exc:
            if exc.code:
                failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
