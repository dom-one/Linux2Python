"""把 AI/教程进度.md 的 F 类清单改成与实际 25 处不匹配一一对应。

上一版按印象写，漏了 01 / 05 / 06 三篇。这版按核对器实际输出的
25 个不匹配块重列，一篇一行，不合并。

按规矩先写 .preview，断言过了再 os.replace 覆盖。

跑法：
    python AI/脚本/_t88_fix_f_list.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TARGET = os.path.join(ROOT, "AI", "教程进度.md")
PREVIEW = TARGET + ".preview"

OLD_F = """| 教程 | 现象 |
|---|---|
| `02-w2l-cli.py` | `grep "def "` 的行号过期（`14:`/`18:`/`25:`/`45:`/`56:`/`61:` → `15:`/`20:`/`27:`/`47:`/`58:`/`63:`） |
| `07-w2l-commands-grep.py` | `grep "def grep"` 示例现在会扫到 `build/`、`teach/` 自身多出 6 行；行号也过期 |
| `08-tests-测试怎么写怎么跑.md` | 用例数从 36 变 180；`-k "word or count"` 从 4 passed 变 15 passed；`--collect-only` 现在列 6 个测试文件；`-k ignore_case_with_line_number` 是 180 deselected（真名 `test_ignore_case`） |
| `09-pyproject.toml-打包与入口点.md` | `w2l --help` 的可用指令列表只有 grep |
| `11-github-actions-ci.yml` / `13-新增一个指令的完整过程.md` / `17-AGENTS.md-项目守则.md` | `python -m pytest -q` 的预期输出仍写 36 条 |
| `13-新增一个指令的完整过程.md` | `ls --help` 的选项列表整个变了（多了 `-l/-A/-h/-d/-t/-S/-r/-F/-R/-1`）；`ls` / `ls -a` 的输出缺 `bin`/`build`/`dist`；不存在的目录报错文案变成了 GNU 风格 |
| `15-AI目录与脚本约定.md` | `ls -1 AI` 的输出缺 `数据/` 目录和 80 多个探针脚本 |
| `18-w2l-__init__.py-包标记与版本号.md` | `python main.py --version` 的「可用指令」只有 grep |
"""

NEW_F = """全量核对 177 个命令块、76 个带预期输出，其中 **25 处对不上**，按篇目列：

| 教程 | 处数 | 现象 |
|---|---|---|
| `01-main.py-入口薄壳.md` | 1 | `python main.py` 的可用指令列表只有 grep，实际有 5 个 |
| `02-w2l-cli.py-分发层.md` | 2 | `grep "错误"` 没带 `-n` 却被写成 `8:` 行号（实际无行号）；`grep -r "def "` 的行号也过期 |
| `05-w2l-errors.py-异常与退出码.md` | 1 | 不存在的文件示例只写了一行错误，实际还有 `退出码=2` 一行 |
| `06-w2l-commands-指令自动发现.md` | 1 | `echo "hello"` 那个示例，`echo` 指令始终没实现（不是前向引用） |
| `07-w2l-commands-grep.py-检索实现.md` | 4 | `grep "def "` 和 `grep -n -w "def"` 的行号过期；`grep "def grep"` 不带路径现在会扫到 `build/`、`teach/` 自身，多出 6 行 |
| `08-tests-测试怎么写怎么跑.md` | 4 | 用例数 36 → 180；`-k "word or count"` 4 passed → 15 passed；`--collect-only` 现在列 6 个测试文件；`-k ignore_case_with_line_number` 是 180 deselected（真名 `test_ignore_case`） |
| `09-pyproject.toml-打包与入口点.md` | 1 | `w2l --help` 的可用指令列表只有 grep |
| `11-github-actions-ci.yml-持续集成.md` | 1 | `python -m pytest -q` 的预期输出仍写 36 条 |
| `13-新增一个指令的完整过程.md` | 7 | `python main.py` 指令列表、`ls --help` 的选项（多了 `-l/-A/-h/-d/-t/-S/-r/-F/-R/-1`）、`ls` / `ls -a` 的输出（缺 `bin`/`build`/`dist`）、`ls w2l`（缺 `entry.py`/`__pycache__`）、不存在目录的报错文案（改成 GNU 风格了）、`pytest -q` 的条数 |
| `15-AI目录与脚本约定.md` | 1 | `ls -1 AI` 的输出缺 `数据/` 目录和 80 多个探针脚本 |
| `17-AGENTS.md-项目守则.md` | 1 | `python -m pytest -q` 的预期输出仍写 36 条 |
| `18-w2l-__init__.py-包标记与版本号.md` | 1 | `python main.py --version` 的「可用指令」只有 grep |

合计 25 处。其中「可用指令列表只有 grep」这一类（01/09/13/18 共 6 处）
是 4 个新指令落地后统一要改的，改一次能消掉多处。
"""


def main() -> None:
    with open(TARGET, "r", encoding="utf-8", newline="") as fh:
        original = fh.read()

    text = original

    if OLD_F not in text:
        raise SystemExit("找不到旧 F 清单")
    if text.count(OLD_F) != 1:
        raise SystemExit("旧 F 清单出现多次")
    text = text.replace(OLD_F, NEW_F, 1)

    # 断言：12 篇都在，处数加起来是 25
    assert "**25 处对不上**" in text
    assert "合计 25 处" in text
    for name in ("01-main.py-入口薄壳.md", "02-w2l-cli.py-分发层.md",
                 "05-w2l-errors.py-异常与退出码.md",
                 "06-w2l-commands-指令自动发现.md",
                 "07-w2l-commands-grep.py-检索实现.md",
                 "08-tests-测试怎么写怎么跑.md",
                 "09-pyproject.toml-打包与入口点.md",
                 "11-github-actions-ci.yml-持续集成.md",
                 "13-新增一个指令的完整过程.md",
                 "15-AI目录与脚本约定.md",
                 "17-AGENTS.md-项目守则.md",
                 "18-w2l-__init__.py-包标记与版本号.md"):
        assert name in text, "F 清单缺：%s" % name

    # 历史段落没动
    assert text.count("#### tick #") == 3
    for stamp in ("#### tick #1（2026-10-28 22:18）",
                  "#### tick #2（2026-10-29 09:17）",
                  "#### tick #3（2026-10-30 12:27）"):
        assert stamp in text

    with open(PREVIEW, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    with open(PREVIEW, "r", encoding="utf-8", newline="") as fh:
        check = fh.read()
    assert check == text, "预览文件和写入内容不一致"

    os.replace(PREVIEW, TARGET)
    print("已更新 %s" % TARGET)
    print("  F 清单改成 12 篇逐篇列，处数合计 25，与核对器实际输出一致")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
