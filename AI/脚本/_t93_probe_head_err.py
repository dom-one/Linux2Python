"""探针四：值长得像已知选项时，改写前后的报错信息差在哪。

用法:
    python AI/脚本/_t93_probe_head_err.py

产出:
    AI/数据/_t93_head_err.txt
"""

from __future__ import annotations

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "数据", "_t93_head_err.txt")

BASH_CANDIDATES = [
    r"E:\software\Git\Git\bin\bash.exe",
    r"C:\Program Files\Git\bin\bash.exe",
    r"C:\Program Files (x86)\Git\bin\bash.exe",
]
BASH_BIN = next((p for p in BASH_CANDIDATES if os.path.isfile(p)), None)

CASES = [
    ("值像已知选项 -v", "python main.py head -n -v w2l/registry.py; echo \"退出码=$?\""),
    ("值像未知选项 --bogus", "python main.py head -n --bogus w2l/registry.py; echo \"退出码=$?\""),
    ("GNU 对照 -n -v", "head -n -v w2l/registry.py; echo \"退出码=$?\""),
    ("GNU 对照 -n --bogus", "head -n --bogus w2l/registry.py; echo \"退出码=$?\""),
    ("本项目 -c -5", "python main.py head -c -5 w2l/registry.py | wc -l; echo \"退出码=$?\""),
    ("GNU -c -5", "head -c -5 w2l/registry.py | wc -l; echo \"退出码=$?\""),
]


def main() -> int:
    if BASH_BIN is None:
        print("找不到 Git Bash")
        return 2
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        for label, command in CASES:
            proc = subprocess.run(
                [BASH_BIN, "-c", command],
                cwd=ROOT,
                capture_output=True,
                timeout=120,
            )
            handle.write("=" * 72 + "\n")
            handle.write(f"[{label}]\n$ {command}\n")
            handle.write(f"退出码={proc.returncode}\n")
            handle.write("--- stdout ---\n")
            handle.write(proc.stdout.decode("utf-8", errors="replace"))
            handle.write("--- stderr ---\n")
            handle.write(proc.stderr.decode("utf-8", errors="replace"))
    print(f"探针输出写到 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
