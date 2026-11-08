"""清理：删掉上一轮误建的文件名写错的探针脚本。

误建路径：AI/脚本/_t218_wc_width9.py（少了 probe 段，且语法有误）。
正确版本：AI/脚本/_t218_probe_wc_width9.py
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "_t218_wc_width9.py"

if TARGET.exists():
    TARGET.unlink()
    print(f"已删除: {TARGET}")
else:
    print(f"不存在，无需删除: {TARGET}")
