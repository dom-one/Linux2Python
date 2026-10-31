"""把 README.md 拆成两版，好让两个提交各自只讲一件事。

背景：仓库里遗留了一份「dmlinux 全局启动器」的改动（未提交），本 tick 又要往
同一份 README 里加 ls 的文档。一份文件只能整体进一个提交，要么把两个功能混在
一个提交里，要么先把 README 拆开。

build_full: 从「只有启动器」那版出发，正向补上 ls 的文档，写进备份文件，
            原地 README 保持「只有启动器」那版（供提交一使用）
restore   : 用备份把完整版写回 README（供提交二使用）

写文件固定用 LF：仓库现有文件是 LF，Windows 的 CRLN 会让整份 README 变成一次
全文件改动。

用法：
    python AI/脚本/_t22_split_readme.py build_full
    python AI/脚本/_t22_split_readme.py restore
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
README = ROOT / "README.md"
BACKUP = ROOT / "AI" / "数据" / "README_full.md"

LS_SECTION = """## ls 能力清单

| 选项 | 含义 | 示例命令 |
| --- | --- | --- |
| （无） | 列出当前目录内容，按名字排序，每行一个条目 | `python main.py ls` |
| `-l` | 长格式：权限、大小、修改时间、名称 | `python main.py ls -l w2l` |
| `-a` | 显示全部条目，含 `.` 与 `..` | `python main.py ls -a w2l` |
| `-A` | 显示隐藏条目，但不含 `.` 与 `..` | `python main.py ls -A w2l` |
| `-h` | 大小按 1024 进制缩写（K/M/G），配合 `-l` 使用 | `python main.py ls -lh w2l/commands` |
| `-d` | 列出目录本身而不是它的内容 | `python main.py ls -d w2l/commands` |
| `-t` | 按修改时间排序，最新的在前 | `python main.py ls -t w2l` |
| `-S` | 按大小排序，最大的在前 | `python main.py ls -S w2l/commands` |
| `-r` | 反向输出排序结果 | `python main.py ls -r w2l` |
| `-F` | 名称后追加类型标记（目录 `/`、可执行 `*`、链接 `@`） | `python main.py ls -F w2l/commands` |
| `-R` | 递归列出子目录，每级目录带 `目录:` 标题 | `python main.py ls -R w2l/commands` |
| `-1` | 每行一个条目（默认行为，保留该选项只为兼容习惯用法） | `python main.py ls -1 w2l` |

行为细节对齐 GNU ls：

- **默认按名字排序**：字节序，大写字母在前（`Beta.txt` 排在 `alpha.txt` 前面），与 GNU 的 C 区域一致。
- **`-h` 不是 `--help`**：GNU 的 `-h` 是 `--human-readable`，所以本指令的用法说明只能用 `--help`。
- **每行一个条目**：输出不排成多列。GNU 在输出不是终端时也是这么做的，管道和脚本里行为一致。
- **多个操作数**：普通文件先统一排序输出，目录随后各自成块并带 `目录:` 标题，块之间空一行。
- **文件操作数按原样打印**：`python main.py ls w2l/cli.py` 输出完整路径，跟 GNU 一样不回退成文件名。

Windows 环境下的差异（都是平台本身没有对应概念，不是实现取巧）：

- **长格式只有四列**：没有链接数、属主、属组。Windows 没有 POSIX 的属主/属组语义，硬凑只会填一列假数字。
- **权限位来自 Windows 合成值**：普通文件显示 `-rw-rw-rw-`、只读文件 `-r--r--r--`、目录 `drwxrwxrwx`，是 Python `os.stat` 在 Windows 上合出来的，不等价于 POSIX 权限。
- **没有 `total N` 汇总行**：Windows 的 `stat` 没有 `st_blocks`，拿不到 GNU 的块数口径。
- **空目录返回退出码 1**（GNU 返回 0），遵循本项目统一的「无结果返回 1」约定，脚本里可直接用它判断目录是否为空。

"""

# 正向补上 ls 文档的改动：(定位串, 替换串)
FORWARDS: list[tuple[str, str]] = [
    (
        "当前实现：`grep`（GNU grep 风格子集）。后续指令按同一模式接入，主干代码不需要改动。",
        "当前实现：`grep`（GNU grep 风格子集）、`ls`（GNU ls 风格子集）。后续指令按同一模式接入，主干代码不需要改动。",
    ),
    (
        'python main.py grep -oE "https?://\\S+" notes.txt\n',
        'python main.py grep -oE "https?://\\S+" notes.txt\n'
        "python main.py ls                       # 列出当前目录\n"
        "python main.py ls -l w2l                # 长格式：权限、大小、时间、名称\n"
        "python main.py ls -R w2l/commands       # 递归列出目录树\n",
    ),
    (
        "## 目录结构\n",
        LS_SECTION + "## 目录结构\n",
    ),
    (
        "│       └── grep.py          # grep 实现\n",
        "│       ├── grep.py          # grep 实现\n"
        "│       └── ls.py            # ls 实现\n",
    ),
    (
        "│   ├── test_grep.py\n│   └── test_launcher.py     # 启动器端到端测试\n",
        "│   ├── test_grep.py\n│   ├── test_ls.py\n│   └── test_launcher.py     # 启动器端到端测试\n",
    ),
    (
        "`ls`、`cat`",
        "`ls`（已完成）、`cat`",
    ),
]


def read_text(path: Path) -> str:
    """读文件并统一成 LF，屏蔽 Windows 的 CRLF 干扰。"""
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def write_text(path: Path, text: str) -> None:
    """写文件时固定用 LF，跟仓库现有文件保持一致。"""
    path.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))


def build_full() -> None:
    text = read_text(README)
    if "## ls 能力清单" in text:
        raise SystemExit("当前 README 已含 ls 章节，不需要再补")
    for old, new in FORWARDS:
        if old not in text:
            raise SystemExit(f"README 里找不到定位串：{old[:40]!r}")
        text = text.replace(old, new, 1)
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    write_text(BACKUP, text)
    print(f"完整版已写入 {BACKUP}，长度 {len(text)} 字符")
    print("原地 README 仍是「只有启动器」那版")


def restore() -> None:
    if not BACKUP.is_file():
        raise SystemExit(f"找不到备份 {BACKUP}，无法还原")
    text = read_text(BACKUP)
    write_text(README, text)
    print(f"已还原完整版 README，长度 {len(text)} 字符")


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "build_full":
        build_full()
    elif action == "restore":
        restore()
    else:
        raise SystemExit("用法: python AI/脚本/_t22_split_readme.py [build_full|restore]")


if __name__ == "__main__":
    main()
