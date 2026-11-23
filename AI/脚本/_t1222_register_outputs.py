#!/usr/bin/env python
"""把本轮产出登记到 E:\\1data\\过滤器\\索引\\索引.jsonl。

路径含中文，交给 Python 调 subprocess，避免 bash 的路径映射与转义问题。
登记失败不阻塞本轮产出，只打印报错。

用法: python AI/脚本/_t1222_register_outputs.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REGISTER = Path(r"E:\1data\过滤器\脚本\登记.py")
ROOT = Path(__file__).resolve().parent.parent.parent

ITEMS = [
    (
        str(ROOT / "w2l" / "encoding.py"),
        "Windows-to-Linux 编码判定共享模块（候选序/严格解码/文本打分/判定，七个指令共用）",
    ),
    (
        str(ROOT / "tests" / "test_encoding.py"),
        "Windows-to-Linux 编码判定共享模块单元测试（37 条）",
    ),
]


def main() -> int:
    failed = 0
    for path, title in ITEMS:
        cmd = [
            sys.executable, str(REGISTER),
            "--来源", "Linux命令",
            "--路径", path,
            "--标题", title,
            "--关联", "无",
        ]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"[失败] {path}: {exc}")
            failed += 1
            continue
        if done.returncode == 0:
            print(f"[成功] {path}")
            print((done.stdout or "").strip())
        else:
            print(f"[失败] {path} 退出码 {done.returncode}")
            print((done.stderr or done.stdout or "").strip())
            failed += 1
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
