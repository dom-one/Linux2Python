"""核对 README 里 head 章节的每个示例命令都能真跑。

顺带核对快速开始段落里的 head 示例。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
README = ROOT / "README.md"

# 只取 head 章节与快速开始里的 head 示例
HEAD_COMMANDS = [
    "python main.py head w2l/cli.py",
    "python main.py head -n 20 w2l/registry.py",
    "python main.py head -c 512 w2l/context.py",
    "python main.py head -q w2l/cli.py w2l/context.py",
    "python main.py head -v w2l/cli.py",
    "python main.py head -z w2l/registry.py",
    "python main.py head -20 w2l/cli.py",
    "python main.py head w2l/cli.py          # 打印文件开头 10 行",
    "python main.py head -n 20 w2l/registry.py  # 打印开头 20 行",
    "python main.py head -c 512 w2l/context.py   # 打印开头 512 字节",
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    text = README.read_text(encoding="utf-8")

    # README 里 head 章节的示例表格行
    section = text.split("## head 能力清单", 1)
    if len(section) != 2:
        print("找不到 head 能力清单章节")
        return 1
    body = section[1].split("## 目录结构", 1)[0]
    examples = re.findall(r"`(python main\.py head[^`]+)`", body)

    print(f"表格里的示例 {len(examples)} 条")
    all_cmds = examples + HEAD_COMMANDS
    failed = 0
    for cmd in all_cmds:
        parts = cmd.split("#", 1)[0].strip()
        proc = subprocess.run(
            parts, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        status = "OK" if proc.returncode == 0 else f"退出码 {proc.returncode}"
        if proc.returncode != 0:
            failed += 1
        first = proc.stdout.decode("utf-8", "replace").splitlines()[:1]
        print(f"  [{status:>10}] {parts}")
        print(f"               首行输出: {first[0] if first else '(空)'}")

    print()
    print(f"合计 {len(all_cmds)} 条，失败 {failed} 条")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
