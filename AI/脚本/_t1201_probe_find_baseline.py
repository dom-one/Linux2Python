#!/usr/bin/env python
"""探针：find 的基线耗时与树结构画像。

用途：
1. 记录 find 串行在大目录树上的耗时（预热后再量，Windows Defender 会扫新文件）；
2. 记录树的结构画像（顶层条目数、各层条目数分布），用来定并行切片的粒度；
3. 查 GNU find 是否自带 -j（决定 README 里怎么写「本项目扩展选项」）。

产物写进 AI/数据/，不在 stdout 打印大段内容。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = HERE.parent / "数据"
DATA.mkdir(parents=True, exist_ok=True)

MAIN = str(ROOT / "main.py")
GIT_BASH = r"E:\software\Git\Git\bin\bash.exe"


def find_gnu() -> str | None:
    """找 Git Bash 里的 GNU find。"""
    if not os.path.exists(GIT_BASH):
        return None
    return r"E:\software\Git\Git\usr\bin\find.exe"


def run(cmd: list[str], cwd: str | None = None) -> tuple[int, float, str]:
    """跑一条命令，掐表，返回 (退出码, 耗时秒, stdout)。"""
    start = time.perf_counter()
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode, time.perf_counter() - start, proc.stdout


def tree_profile(root: str) -> dict:
    """统计树的形状：顶层条目数、每层的目录数与文件数、总条目数。"""
    levels: list[dict] = []
    total = 0
    frontier = [root]
    for depth in range(6):
        dirs = 0
        files = 0
        next_frontier: list[str] = []
        for current in frontier:
            try:
                with os.scandir(current) as scanner:
                    for entry in scanner:
                        try:
                            is_dir = entry.is_dir(follow_symlinks=False)
                        except OSError:
                            continue
                        if is_dir:
                            dirs += 1
                            if depth < 5:
                                next_frontier.append(entry.path)
                        else:
                            files += 1
            except OSError:
                continue
        levels.append({"depth": depth, "dirs": dirs, "files": files})
        total += dirs + files
        frontier = next_frontier
        if not frontier:
            break
    return {"levels": levels, "total_entries": total}


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "E:/1"
    report: dict = {"target": target, "cpu_count": os.cpu_count()}

    if not os.path.exists(target):
        report["error"] = f"目标不存在: {target}"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    report["profile"] = tree_profile(target)

    # 本项目 find：预热一次丢弃，再量两次取较小值
    runs = []
    for index in range(3):
        code, elapsed, out = run([sys.executable, MAIN, "find", target, "-type", "f"])
        runs.append({"round": index, "code": code, "seconds": round(elapsed, 3), "lines": out.count("\n")})
    report["w2l_find"] = runs

    gnu = find_gnu()
    if gnu:
        gruns = []
        for index in range(2):
            code, elapsed, out = run([gnu, target, "-type", "f"])
            gruns.append({"round": index, "code": code, "seconds": round(elapsed, 3), "lines": out.count("\n")})
        report["gnu_find"] = gruns

        # GNU find 自己有没有 -j？
        code, _, out = run([gnu, "--help"])
        report["gnu_has_jobs"] = "-j" in out or "--jobs" in out
        report["gnu_version"] = run([gnu, "--version"])[2].splitlines()[:1]

    out_path = DATA / "t1201_find_baseline.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[写入] {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
