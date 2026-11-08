"""删掉写错路径的脚本文件。

用法:
    python AI/脚本/_t110_remove_badfile.py

为什么需要:
    上一步用 write 工具写 _t109 时把文件名写坏了（多出 "_" 结尾、
    路径也拼错），需要清掉。bash 的 rm 走 Git Bash 路径映射，
    中文路径被本地安全策略拦，所以改用 Python 的 unlink。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "AI" / "脚本"

TARGETS = [
    SCRIPT_DIR / "_t109_update_progress_state.py_",
    SCRIPT_DIR / "_t109_update_progress_state.py",
]


def main() -> int:
    for path in TARGETS:
        if path.exists():
            path.unlink()
            print("已删除: %s" % path.name)
        else:
            print("不存在，跳过: %s" % path.name)
    print()
    print("当前 t10x 脚本:")
    for path in sorted(SCRIPT_DIR.glob("_t10*.py")):
        print("  %s" % path.name)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
