"""探针：argv 在两个方向上分别被谁改写。

要回答三个问题：
1. 原生 Python → MSYS 程序（printf.exe）：argv 里的反斜杠被谁吃了？
2. MSYS find → 原生 Python：argv 里的 ./a.txt 会不会被 MSYS 做路径转换？
3. 同一个 MSYS 程序（printf）在两种父进程下收到的 argv 是否相同？

★ 差分脚本要拿 -exec 的展开结果做比对，必须先知道 argv 在哪一层被改写，
否则比出来的是「运行时改写」的差异，不是 find 展开逻辑的差异。

用法: python AI/脚本/_t827_probe_find_argv_mangle.py
产出: AI/数据/find_fix/argv_mangle.txt
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
BASE = AI_DIR / "数据" / "find_fix"
ROOT = AI_DIR.parent


def main() -> int:
    BASE.mkdir(parents=True, exist_ok=True)
    tree = BASE / "tree11"
    tree.mkdir(parents=True, exist_ok=True)
    (tree / "a.txt").write_bytes(b"alpha\n")
    (tree / "sub").mkdir(exist_ok=True)

    # 一个原生的 dump 脚本：把收到的 argv 原样打印（repr）
    dump = BASE / "_t827_dump.py"
    dump.write_text(
        "import sys\n"
        "for a in sys.argv[1:]:\n"
        "    print(repr(a))\n",
        encoding="utf-8",
    )

    lines: list[str] = ["# 由 _t827_probe_find_argv_mangle.py 生成，勿手改"]
    bash = shutil.which("bash") or r"E:\software\Git\Git\bin\bash.exe"
    printf = (shutil.which("printf") or "").replace("\\", "/")

    # --- 1. 原生 Python → MSYS printf：反斜杠还在吗 ---
    proc = subprocess.run(
        [printf, "[%s]\\n", "A{}B"],
        capture_output=True,
    )
    lines.append(f"[原生 Python → MSYS printf] stdout={proc.stdout!r}")

    # --- 2. bash → MSYS printf：反斜杠还在吗 ---
    script = BASE / "_t827_printf.sh"
    script.write_text(f'"{printf}" "[%s]\\n" "A{{}}B"\n', encoding="utf-8")
    proc2 = subprocess.run([bash, str(script)], capture_output=True)
    lines.append(f"[bash → MSYS printf] stdout={proc2.stdout!r}")

    # --- 3. MSYS find → 原生 Python：路径会不会被转换 ---
    script3 = BASE / "_t827_find_dump.sh"
    script3.write_text(
        f"cd '{tree.as_posix()}'\n"
        f"/usr/bin/find . -exec '{sys.executable}' '{dump.as_posix()}' '{{}}' ';'\n",
        encoding="utf-8",
    )
    proc3 = subprocess.run([bash, str(script3)], capture_output=True)
    lines.append(f"[MSYS find → 原生 Python] stdout={proc3.stdout!r}")
    lines.append(f"  stderr={proc3.stderr!r}")

    # --- 4. 原生 Python → 原生 Python（对照组，无 MSYS 介入） ---
    proc4 = subprocess.run(
        [sys.executable, str(dump), "A{}B", "./a.txt"],
        capture_output=True,
    )
    lines.append(f"[原生 Python → 原生 Python] stdout={proc4.stdout!r}")

    (BASE / "argv_mangle.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
