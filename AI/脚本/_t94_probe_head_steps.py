"""探针五：教程正文里那几条 od / printf 命令的精确输出。

用法:
    python AI/脚本/_t94_probe_head_steps.py

产出:
    AI/数据/_t94_head_steps.txt
"""

from __future__ import annotations

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "数据", "_t94_head_steps.txt")

BASH_CANDIDATES = [
    r"E:\software\Git\Git\bin\bash.exe",
    r"C:\Program Files\Git\bin\bash.exe",
    r"C:\Program Files (x86)\Git\bin\bash.exe",
]
BASH_BIN = next((p for p in BASH_CANDIDATES if os.path.isfile(p)), None)

CASES = [
    ("cat 自己的行数", "python main.py cat w2l/commands/head.py | wc -l"),
    ("默认10行 条数", "python main.py head w2l/registry.py | wc -l"),
    ("-c 7 纯ASCII", "printf 'abcdefghij\\n' | python main.py head -c 7 -"),
    ("-c 7 跨行", "printf 'l1\\nl2\\nl3\\n' | python main.py head -c 7 - | od -c"),
    ("-n 2 跨行", "printf 'l1\\nl2\\nl3\\n' | python main.py head -n 2 -"),
    ("-c 7 取中文", "python main.py head -c 7 w2l/registry.py | od -c"),
    ("-n -3 与 GNU 对照", "python main.py head -n -3 w2l/registry.py | wc -l; head -n -3 w2l/registry.py | wc -l"),
    ("-n 1b 与 GNU 对照", "python main.py head -n 1b w2l/commands/head.py | wc -l; head -n 1b w2l/commands/head.py | wc -l"),
    ("-n 0 与 -0", "python main.py head -n 0 w2l/registry.py | wc -l; python main.py head -n -0 w2l/registry.py | wc -l"),
    ("CRLF od", "printf 'c1\\r\\nc2\\r\\nc3\\r\\n' | python main.py head -n 2 - | od -c"),
    ("末行无换行 od", "printf 'p1\\np2\\np3' | python main.py head - | od -c"),
    ("NUL od", "printf 'z1\\x00z2\\x00z3\\x00' | python main.py head -z -n 2 - | od -c"),
    ("二进制 od", "printf 'a\\x00b\\xff' | python main.py head - | od -c"),
    ("GBK 本项目 od", "printf '\\xd6\\xd0\\xce\\xc4\\n' | python main.py head - | od -c"),
    ("GBK GNU od", "printf '\\xd6\\xd0\\xce\\xc4\\n' | head - | od -c"),
    ("GBK 字节数对照", "printf '\\xd6\\xd0\\xce\\xc4\\n' | python main.py head -c 2 - | wc -c; printf '\\xd6\\xd0\\xce\\xc4\\n' | head -c 2 | wc -c"),
    ("不存在文件 合并", "python main.py head w2l/nope.txt; echo \"退出码=$?\""),
    ("目录 合并", "python main.py head w2l; echo \"退出码=$?\""),
    ("多文件 标题空行", "python main.py head -n 1 w2l/context.py w2l/errors.py"),
    ("stdin -v", "printf 's1\\ns2\\n' | python main.py head -v -"),
    ("后缀表", "for s in 1b 1k 1kB 1KiB 1m 1M; do printf '%s=' \"$s\"; python main.py head -c $s w2l/commands/head.py | wc -c; done"),
    ("后缀表 GNU", "for s in 1b 1k 1kB 1KiB 1m 1M; do printf '%s=' \"$s\"; head -c $s w2l/commands/head.py | wc -c; done"),
    ("测试用例数", "python -m pytest tests/test_head.py 2>&1 | tail -1"),
    ("全量测试", "python -m pytest 2>&1 | tail -1"),
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
