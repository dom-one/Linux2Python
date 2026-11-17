"""跑一遍 find 教程要用的全部命令，把真实输出录下来。

教程里的预期输出必须来自实跑，不能凭印象写——
tick #8 就是因为预期输出凭印象写，19 处对不上。

用法:
    python AI/脚本/_t709_capture_find_tutorial.py

输出写到 AI/数据/find_tutorial_capture.txt。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = Path(ROOT) / "AI" / "数据" / "find_tutorial_capture.txt"
BASH = r"E:\software\Git\Git\bin\bash.exe"

# (步骤号, 说明, 命令)
STEPS = [
    ("01", "生成夹具", "python AI/脚本/_t700_make_find_demo.py"),
    ("02", "源码行数", "python main.py cat w2l/commands/find.py | wc -l"),
    ("03", "默认打印全部", "python main.py find AI/数据/find_demo"),
    ("04", "-name 区分大小写", "python main.py find AI/数据/find_demo -name '*.txt'"),
    ("05", "-name 大写不匹配", "python main.py find AI/数据/find_demo -name '*.TXT'"),
    ("06", "-iname 忽略大小写", "python main.py find AI/数据/find_demo -iname '*.TXT'"),
    ("07", "-type d", "python main.py find AI/数据/find_demo -type d"),
    ("08", "-type f", "python main.py find AI/数据/find_demo -type f"),
    ("09", "-size 默认 512 字节块", "python main.py find AI/数据/find_demo -size 1"),
    ("10", "-size 精确字节", "python main.py find AI/数据/find_demo -size 6c"),
    ("11", "-size 大于", "python main.py find AI/数据/find_demo -size +6c"),
    ("12", "-empty", "python main.py find AI/数据/find_demo -empty"),
    ("13", "-o 或", "python main.py find AI/数据/find_demo -name '*.md' -o -name '*.py'"),
    ("14", "括号分组", "python main.py find AI/数据/find_demo \\( -name '*.md' -o -name '*.py' \\)"),
    ("15", "! 非", "python main.py find AI/数据/find_demo ! -name '*.txt'"),
    ("16", "and 优先级高于 or",
     "python main.py find AI/数据/find_demo -type f -name '*.txt' -o -name '*.md'"),
    ("17", "-prune 挡下降",
     "python main.py find AI/数据/find_demo -type d -name sub -prune -o -print"),
    ("18", "-maxdepth 1", "python main.py find AI/数据/find_demo -maxdepth 1"),
    ("19", "-maxdepth 0", "python main.py find AI/数据/find_demo -maxdepth 0"),
    ("20", "-mindepth 2", "python main.py find AI/数据/find_demo -mindepth 2"),
    ("21", "-depth 后序", "python main.py find AI/数据/find_demo -depth -type d"),
    ("22", "-print0 用 NUL 分隔",
     "python main.py find AI/数据/find_demo -name '*.md' -print0 | od -c | tail -2"),
    ("23", "-printf 基本", "python main.py find AI/数据/find_demo -name '*.md' -printf '%f|%s|%y\\n'"),
    ("24", "-printf 所在目录", "python main.py find AI/数据/find_demo -name '*.txt' -printf '%h\\n'"),
    ("25", "-exec 单个", "python main.py find AI/数据/find_demo -name '*.md' -exec echo {} \\;"),
    ("26", "-exec 批量", "python main.py find AI/数据/find_demo -name '*.md' -exec echo {} +"),
    ("27", "-exec 占位符在参数中间",
     "python main.py find AI/数据/find_demo -name '*.md' -exec echo A{}B \\;"),
    ("28", "-delete",
     "python AI/脚本/_t707_make_delete_demo.py && "
     "python main.py find AI/数据/find_delete_demo -name '*.tmp' -delete && "
     "python main.py find AI/数据/find_delete_demo -type f"),
    ("29", "-mtime 超过 9 天", "python main.py find AI/数据/find_demo -type f -mtime +9"),
    ("30", "-mmin 1 命中刚建的文件",
     "python AI/脚本/_t708_make_mtime_demo.py && "
     "python main.py find AI/数据/find_mtime_demo -type f -mmin 1"),
    ("31", "-mmin 0 命中不到",
     "python AI/脚本/_t708_make_mtime_demo.py && "
     "python main.py find AI/数据/find_mtime_demo -type f -mmin 0"),
    ("32", "-newer",
     "python main.py find AI/数据/find_demo -type f -newer AI/数据/find_demo/old.txt"),
    ("33", "未知谓词", "python main.py find AI/数据/find_demo -没有这个谓词"),
    ("34", "操作数不存在", "python main.py find AI/数据/没有这个目录"),
    ("35", "路径写在表达式后", "python main.py find AI/数据/find_demo -name '*.md' 多余的操作数"),
    ("36", "括号没闭合", "python main.py find AI/数据/find_demo \\( -name '*.txt'"),
    ("37", "-type 非法取值", "python main.py find AI/数据/find_demo -type x"),
    ("38", "跑相关测试", "python -m pytest tests/test_find.py 2>&1 | tail -1"),
    ("39", "跑全量测试", "python -m pytest 2>&1 | tail -1"),
    ("40", "管道里本项目是 CRLF",
     "python main.py find AI/数据/find_demo -name '*.md' | od -c | tail -2"),
    ("41", "管道里 GNU 是 LF",
     "find AI/数据/find_demo -name '*.md' | od -c | tail -2"),
    ("42", "隐藏文件也能被 * 匹配",
     "python main.py find AI/数据/find_demo -name '.*'"),
    ("43", "隐式 -print 等价于显式",
     "python main.py find AI/数据/find_demo -name '*.md' -print"),
    ("44", "echo 到底是哪个",
     "where echo 2>&1 | head -3"),
]


def run(command: str) -> tuple[int, str]:
    full = 'cd "%s" && { %s ; } 2>&1' % (ROOT, command)
    proc = subprocess.run([BASH, "-c", full], capture_output=True)
    text = proc.stdout.decode("utf-8", errors="replace")
    return proc.returncode, text.rstrip("\n")


def main() -> None:
    chunks = []
    for no, title, command in STEPS:
        code, output = run(command)
        chunks.append(f"===== 第 {no} 步 · {title} =====")
        chunks.append(f"$ {command}")
        chunks.append(f"[退出码 {code}]")
        chunks.append(output if output else "(无输出)")
        chunks.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(chunks), encoding="utf-8")
    print(f"已写入 {OUT}")
    print("\n".join(chunks))


if __name__ == "__main__":
    main()
