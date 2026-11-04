"""修 teach/00-项目总览与阅读顺序.md 里已经过期的事实。

背景：上一轮开发任务落地了 ls / cat / head / tail 四个指令和 bin/ 启动器、
w2l/entry.py，索引页还停留在「只有 grep」的世界里，核对器已经报出
「预期输出与实际不符」。

改四处：
1. 第 1 步的预期输出：可用指令从 1 个变 5 个
2. 第 2 步的命令：原来的 `grep -rl "" .` 现在会递归扫进 .git/build/dist，
   输出 561 行没法看；换成依次 ls 四个关键目录
3. 第 2 步的结构树：补 bin/、w2l/entry.py、5 个指令、6 个测试文件
4. 「为什么这么创建」里的 grep.py 行数 345 -> 347

按规矩先写 .preview，断言过了再 os.replace 覆盖。

跑法：
    python AI/脚本/_t79_fix_index_stale.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TARGET = os.path.join(ROOT, "teach", "00-项目总览与阅读顺序.md")
PREVIEW = TARGET + ".preview"


OLD_HELP = """用法: python main.py <指令> [参数]

可用指令:
  grep  搜索包含 PATTERN 的行（GNU grep 风格子集）

查看具体用法: python main.py <指令> --help
"""

NEW_HELP = """用法: python main.py <指令> [参数]

可用指令:
  cat   连接文件内容并输出到标准输出（GNU cat 风格子集）
  grep  搜索包含 PATTERN 的行（GNU grep 风格子集）
  head  打印文件开头部分（GNU head 风格子集）
  ls    列出目录内容（GNU ls 风格子集）
  tail  打印文件末尾部分（GNU tail 风格子集）

查看具体用法: python main.py <指令> --help
"""

OLD_CMD = """python main.py grep -rl "" .
```

这条命令会列出项目里所有文件（空模式匹配每一行）。实际结构是这样：
"""

NEW_CMD = """python main.py ls w2l/ && python main.py ls w2l/commands/ && python main.py ls tests/ && python main.py ls bin/
```

这条命令依次列出四个关键目录的内容。整理成结构图是这样：
"""

OLD_TREE = """Windows-to-Linux/
├── main.py                 # 入口薄壳，只调 w2l.cli:main
├── w2l/
│   ├── __init__.py         # 包声明 + __version__ = "0.1.0"
│   ├── cli.py              # 分发层：帮助输出、编码、异常→退出码
│   ├── registry.py         # 注册表 + @command 装饰器
│   ├── context.py          # RunContext（cwd / stdout / stderr / stdin）
│   ├── errors.py           # UsageError / CommandError
│   └── commands/
│       ├── __init__.py     # load_all() 自动导入子模块
│       └── grep.py         # grep 实现（345 行）
├── tests/
│   ├── conftest.py         # run_grep 辅助函数 + sample_tree fixture
│   └── test_grep.py        # 36 个用例
├── .github/workflows/ci.yml
├── .gitignore
├── pyproject.toml
├── README.md               # 对外说明与演进路线
├── AGENTS.md               # 项目守则
├── cron.md                 # 开发任务的 cron prompt
├── AI/                     # 脚本、进度、锁、任务 prompt
└── teach/                  # 本教程目录
"""

NEW_TREE = """Windows-to-Linux/
├── main.py                 # 入口薄壳，只调 w2l.cli:main
├── bin/
│   ├── dmlinux.cmd         # Windows 启动器（cmd / PowerShell）
│   └── dmlinux             # POSIX shell 启动器（git-bash / WSL）
├── w2l/
│   ├── __init__.py         # 包声明 + __version__ = "0.1.0"
│   ├── cli.py              # 分发层：帮助输出、编码、异常→退出码
│   ├── registry.py         # 注册表 + @command 装饰器
│   ├── context.py          # RunContext（cwd / stdout / stderr / stdin）
│   ├── errors.py           # UsageError / CommandError
│   ├── entry.py            # 入口名跟随调用方式
│   └── commands/
│       ├── __init__.py     # load_all() 自动导入子模块
│       ├── grep.py         # grep 实现（347 行）
│       ├── ls.py           # ls 实现（308 行）
│       ├── cat.py          # cat 实现（392 行）
│       ├── head.py         # head 实现（642 行）
│       └── tail.py         # tail 实现（1140 行）
├── tests/
│   ├── conftest.py         # run_* 辅助函数 + sample_tree fixture
│   ├── test_grep.py        # 36 个用例
│   ├── test_ls.py          # 23 个用例
│   ├── test_cat.py         # 34 个用例
│   ├── test_head.py        # 32 个用例
│   ├── test_tail.py        # 45 个用例
│   └── test_launcher.py    # 10 个用例（启动器端到端）
├── .github/workflows/ci.yml
├── .gitignore
├── pyproject.toml
├── README.md               # 对外说明与演进路线
├── AGENTS.md               # 项目守则
├── cron.md                 # 开发任务的 cron prompt
├── AI/                     # 脚本、进度、锁、任务 prompt
└── teach/                  # 本教程目录
"""


def main() -> None:
    with open(TARGET, "r", encoding="utf-8", newline="") as fh:
        original = fh.read()

    text = original

    for old, new, label in (
        (OLD_HELP, NEW_HELP, "第 1 步预期输出"),
        (OLD_CMD, NEW_CMD, "第 2 步命令"),
        (OLD_TREE, NEW_TREE, "第 2 步结构树"),
    ):
        if old not in text:
            raise SystemExit("找不到片段：%s" % label)
        if text.count(old) != 1:
            raise SystemExit("片段出现多次，跳过：%s" % label)
        text = text.replace(old, new, 1)

    # grep.py 行数
    old_len = "`w2l/commands/grep.py` 有 345 行、36 个测试用例、9 个选项"
    new_len = "`w2l/commands/grep.py` 有 347 行、36 个测试用例、9 个选项"
    if old_len not in text:
        raise SystemExit("找不到 grep.py 行数片段")
    text = text.replace(old_len, new_len, 1)

    # 断言
    assert "  grep  搜索包含 PATTERN 的行（GNU grep 风格子集）\n\n查看具体用法" not in text
    assert "  tail  打印文件末尾部分（GNU tail 风格子集）" in text
    assert "python main.py grep -rl \"\" ." not in text
    assert "python main.py ls w2l/ && python main.py ls w2l/commands/" in text
    assert "│   ├── entry.py            # 入口名跟随调用方式" in text
    assert "│   ├── dmlinux.cmd         # Windows 启动器（cmd / PowerShell）" in text
    assert "│   └── test_launcher.py    # 10 个用例（启动器端到端）" in text
    assert "有 347 行" in text
    assert "有 345 行" not in text
    for heading in ("## 为什么这么创建", "## 这个文件是做什么",
                    "## 有什么用", "## 怎么用（过程教程）"):
        assert heading in text, "小节标题丢了：%s" % heading
    # 依赖表那行是上一轮加的，别弄丢
    assert "| 19 | `w2l/entry.py` 入口名跟随调用方式 | 02、09 |" in text

    with open(PREVIEW, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    with open(PREVIEW, "r", encoding="utf-8", newline="") as fh:
        check = fh.read()
    assert check == text, "预览文件和写入内容不一致"

    os.replace(PREVIEW, TARGET)
    print("已更新 %s" % TARGET)
    print("  预期输出 1->5 个指令，第 2 步命令换掉，结构树补全，grep.py 行数改对")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
