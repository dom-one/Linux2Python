#!/usr/bin/env python
"""探针：w2l find 与 GNU find 在同一棵树上的差异定位。

基线探针发现两处不一致：
- w2l find 的退出码是 2（GNU 是 0），说明有错误被报出来；
- 行数 17268 vs 16820，差 448 行。

先分诊是「错误消息来自哪里」还是「两边枚举的条目集合不同」。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = HERE.parent / "数据"
DATA.mkdir(parents=True, exist_ok=True)

MAIN = str(ROOT / "main.py")
GNU_FIND = r"E:\software\Git\Git\usr\bin\find.exe"


def run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "E:/1"

    code, out, err = run([sys.executable, MAIN, "find", target, "-type", "f"])
    (DATA / "t1202_w2l.out").write_text(out, encoding="utf-8")
    (DATA / "t1202_w2l.err").write_text(err, encoding="utf-8")
    print(f"[w2l] code={code} stdout_lines={out.count(chr(10))} stderr_lines={err.count(chr(10))}")
    if err:
        print("--- stderr 前 20 行 ---")
        for line in err.splitlines()[:20]:
            print("  " + line)
        print("--- stderr 去重计数（前 5 类）---")
        kinds: dict[str, int] = {}
        for line in err.splitlines():
            key = line.split(":")[0][:120]
            kinds[key] = kinds.get(key, 0) + 1
        for key, count in sorted(kinds.items(), key=lambda kv: -kv[1])[:5]:
            print(f"  {count:6d}  {key}")

    if not os.path.exists(GNU_FIND):
        print("[gnu] 找不到 GNU find，跳过对照")
        return 0

    gcode, gout, gerr = run([GNU_FIND, target, "-type", "f"])
    (DATA / "t1202_gnu.out").write_text(gout, encoding="utf-8")
    (DATA / "t1202_gnu.err").write_text(gerr, encoding="utf-8")
    print(f"[gnu] code={gcode} stdout_lines={gout.count(chr(10))} stderr_lines={gerr.count(chr(10))}")

    w2l_set = set(out.splitlines())
    gnu_set = set(gout.splitlines())
    only_w2l = sorted(w2l_set - gnu_set)
    only_gnu = sorted(gnu_set - w2l_set)
    print(f"[集合] 只在 w2l 的 {len(only_w2l)} 条，只在 gnu 的 {len(only_gnu)} 条")
    for line in only_w2l[:10]:
        print("  + " + line)
    for line in only_gnu[:10]:
        print("  - " + line)

    # 重复行（同一路径被打印两次）
    seen: dict[str, int] = {}
    for line in out.splitlines():
        seen[line] = seen.get(line, 0) + 1
    dups = {k: v for k, v in seen.items() if v > 1}
    print(f"[w2l 重复行] {len(dups)} 条路径被打印多次")
    for key, count in sorted(dups.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  x{count}  {key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
