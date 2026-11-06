"""探针：把 head 教程里要用的命令逐条真跑，捕获精确输出。

用法:
    python AI/脚本/_t90_probe_head.py

为什么用 Git Bash:
    教程里的命令是 bash 风格（printf、管道、exit code），cmd.exe 里没有这些。
    用 bash 跑才对得上读者看到的写法。

为什么输出重定向到文件再读:
    Windows 控制台输出是 GBK，直接解码会报错。这里用 capture_output
    拿字节，再按 UTF-8 解。

产出:
    AI/数据/_t90_head_probe.txt
"""

from __future__ import annotations

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "数据", "_t90_head_probe.txt")

BASH_CANDIDATES = [
    r"E:\software\Git\Git\bin\bash.exe",
    r"C:\Program Files\Git\bin\bash.exe",
    r"C:\Program Files (x86)\Git\bin\bash.exe",
]
BASH_BIN = next((p for p in BASH_CANDIDATES if os.path.isfile(p)), None)

# (标签, 命令)
CASES: list[tuple[str, str]] = [
    ("函数清单", "python main.py grep -n 'def ' w2l/commands/head.py"),
    ("类与常量清单", "python main.py grep -n 'class \\|^_[A-Z]' w2l/commands/head.py"),
    ("文件行数", "python main.py head -n 1 w2l/commands/head.py"),
    ("帮助", "python main.py head --help"),
    ("默认10行", "python main.py head w2l/registry.py"),
    ("默认行数条数", "python main.py head w2l/registry.py | wc -l"),
    ("-n 3", "python main.py head -n 3 w2l/registry.py"),
    ("紧凑 -3", "python main.py head -3 w2l/registry.py"),
    ("紧凑 -3 行数", "python main.py head -3 w2l/registry.py | wc -l"),
    ("-n -3 除末3行", "python main.py head -n -3 w2l/registry.py | wc -l"),
    ("-n -3 内容", "python main.py head -n -3 w2l/registry.py"),
    ("-n +3", "python main.py head -n +3 w2l/registry.py"),
    ("-n +3 行数", "python main.py head -n +3 w2l/registry.py | wc -l"),
    ("-n 0", "python main.py head -n 0 w2l/registry.py"),
    ("-n 0 行数", "python main.py head -n 0 w2l/registry.py | wc -l"),
    ("-n -0 行数", "python main.py head -n -0 w2l/registry.py | wc -l"),
    ("-c 20", "python main.py head -c 20 w2l/registry.py"),
    ("-c 20 repr", "python main.py head -c 20 w2l/registry.py | od -c | head -3"),
    ("-c 7 -n 2", "python main.py head -c 7 -n 2 w2l/registry.py"),
    ("-n 2 -c 7", "python main.py head -n 2 -c 7 w2l/registry.py"),
    ("-n 1b 行数", "python main.py head -n 1b w2l/commands/head.py | wc -l"),
    ("-n 1b 字节", "python main.py head -n 1b w2l/commands/head.py | wc -c"),
    ("-c 1b 字节", "python main.py head -c 1b w2l/commands/head.py | wc -c"),
    ("-c 1k 字节", "python main.py head -c 1k w2l/commands/head.py | wc -c"),
    ("-c 1kB 字节", "python main.py head -c 1kB w2l/commands/head.py | wc -c"),
    ("-c 1KiB 字节", "python main.py head -c 1KiB w2l/commands/head.py | wc -c"),
    ("多文件标题", "python main.py head -n 1 w2l/context.py w2l/errors.py"),
    ("多文件-完整", "python main.py head -n 2 w2l/context.py w2l/errors.py"),
    ("-q 去标题", "python main.py head -q -n 1 w2l/context.py w2l/errors.py"),
    ("-v 强制标题", "python main.py head -v -n 1 w2l/context.py"),
    ("-q -v 顺序", "python main.py head -q -v -n 1 w2l/context.py w2l/errors.py"),
    ("-v -q 顺序", "python main.py head -v -q -n 1 w2l/context.py w2l/errors.py"),
    ("stdin 管道", "printf 's1\\ns2\\ns3\\n' | python main.py head -n 2"),
    ("stdin 减号", "printf 's1\\ns2\\ns3\\n' | python main.py head -n 2 -"),
    ("stdin -v 标题", "printf 's1\\ns2\\n' | python main.py head -v -"),
    ("CRLF 原样", "printf 'c1\\r\\nc2\\r\\nc3\\r\\n' | python main.py head -n 2 - | od -c | head -3"),
    ("末行无换行", "printf 'p1\\np2\\np3' | python main.py head - - | od -c"),
    ("NUL 分隔", "printf 'z1\\x00z2\\x00z3\\x00' | python main.py head -z -n 2 - | od -c"),
    ("二进制透传", "printf 'a\\x00b\\xff' | python main.py head - - | od -c"),
    ("GBK 中文", "printf '\\xd6\\xd0\\xce\\xc4\\n' | python main.py head -"),
    ("不存在文件", "python main.py head w2l/nope.txt; echo \"退出码=$?\""),
    ("目录当文件", "python main.py head w2l; echo \"退出码=$?\""),
    ("多文件一个不存在", "python main.py head -v -n 1 w2l/context.py w2l/nope.txt; echo \"退出码=$?\""),
    ("非法计数", "python main.py head -n abc w2l/registry.py; echo \"退出码=$?\""),
    ("非法后缀", "python main.py head -c 1g w2l/registry.py; echo \"退出码=$?\""),
    ("缺值", "python main.py head -n; echo \"退出码=$?\""),
    ("未知选项", "python main.py head --bogus; echo \"退出码=$?\""),
    ("GNU 对照 默认", "head -n 3 w2l/registry.py"),
    ("GNU 对照 -n -3", "head -n -3 w2l/registry.py | wc -l"),
    ("GNU 对照 0 与 -0", "head -n 0 w2l/registry.py | wc -l; head -n -0 w2l/registry.py | wc -l"),
    ("GNU 对照 -n 1b", "head -n 1b w2l/commands/head.py | wc -l"),
    ("GNU 对照 -c 1b", "head -c 1b w2l/commands/head.py | wc -c"),
    ("GNU 对照 紧凑 -3", "head -3 w2l/registry.py | wc -l"),
    ("GNU 对照 多文件标题", "head -n 1 w2l/context.py w2l/errors.py"),
    ("head 测试用例数", "python -m pytest tests/test_head.py 2>&1 | tail -2"),
    ("全量测试", "python -m pytest 2>&1 | tail -2"),
]


def main() -> int:
    if BASH_BIN is None:
        print("找不到 Git Bash，无法跑探针")
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
            handle.write("--- stdout repr ---\n")
            handle.write(repr(proc.stdout) + "\n")
            handle.write("--- stderr repr ---\n")
            handle.write(repr(proc.stderr) + "\n")

    print(f"探针输出写到 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
