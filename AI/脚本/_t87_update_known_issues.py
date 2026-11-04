"""更新 AI/教程进度.md 的「已知问题与未决项」段。

在 2026-10-30 那批结论之后**追加** 2026-11-05 这轮的结论，
不删改旧条目（历史结论留着有用：能看出哪些一直没修）。

本轮结论：
1. 2026-10-30 记的 A 类 9 处里，B 类「等 ls 实现」已经实现了，
   于是 ls 的示例全部对上了，但同批暴露出更多过期点
2. 核对器差点把磁盘写满（裸 python 进 REPL），已修工具
3. teach/00 索引页整页过期（只有 grep 的时代），已修

按规矩先写 .preview，断言过了再 os.replace 覆盖。

跑法：
    python AI/脚本/_t87_update_known_issues.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TARGET = os.path.join(ROOT, "AI", "教程进度.md")
PREVIEW = TARGET + ".preview"

ANCHOR = """**C. 已知噪声（不改）**

- `grep` 不带路径时现在会递归搜当前目录，所以 `07` 里「只搜当前目录文件」的示例会扫到 `build/`、`teach/` 自身。这是 `feat(grep): 不给路径时终端默认递归搜索当前目录` 带来的行为变化，属有意为之。
- `pytest` 耗时每次不同，核对器已把 `in 0.15s` 这类归一化后再比对。
"""

NEW_SECTION = """**C. 已知噪声（不改）**

- `grep` 不带路径时现在会递归搜当前目录，所以 `07` 里「只搜当前目录文件」的示例会扫到 `build/`、`teach/` 自身。这是 `feat(grep): 不给路径时终端默认递归搜索当前目录` 带来的行为变化，属有意为之。
- `pytest` 耗时每次不同，核对器已把 `in 0.15s` 这类归一化后再比对。

---

### 2026-11-05 全量复核（tick #4）

用修好的核对器跑完全部 20 篇教程。上一轮记的 B 类「等 `ls` 实现」已经实现了
（`ls`/`cat`/`head`/`tail` 四个指令 + `bin/` 启动器 + `w2l/entry.py` 都已落地），
所以 B 类自动对上；但同批暴露出下面这些新的过期点。

**D. 本轮已修**

| 教程 | 现象 | 处理 |
|---|---|---|
| `00-项目总览与阅读顺序.md` | 整页停在「只有 grep」的世界：可用指令只列 1 个、结构树缺 `bin/`、`entry.py` 和 4 个新指令、测试文件只有 1 个 | 已更新；第 2 步的命令从 `grep -rl "" .` 换成依次 `ls` 四个关键目录（原命令现在会递归扫进 `.git`/`build`/`dist`，输出 561 行没法看） |
| `03-w2l-registry.py-指令注册表.md` | `ls w2l` 的预期输出缺 `entry.py` 和 `__pycache__`；REPL 对话里的 `sorted(REGISTRY)` 还是 `['grep']` | 已更新；REPL 段改成等价的 `python -c` 写法（见 E 类） |
| `AI/脚本/_t12_verify_teach.py` | 全量核对时把磁盘写满，临时文件涨到 3.2 GB | 已修工具，见 E 类 |

**E. 核对器差点写满磁盘（本轮最严重的问题，已修）**

- **现象**：跑全量核对时，`%TEMP%` 下的临时文件涨到 **3.2 GB**，内容是 Python 3.14 交互 REPL 的崩溃 traceback。实测裸 `python` 命令块 **6 秒写 281.9 MB**（~47 MB/s）。
- **根因**：`teach/03` 里有一段「敲 `python` 进 REPL」的示例。命令被管道接走后 `python` 读不到控制台句柄，Python 3.13+ 的新 REPL 在 `_pyrepl/windows_console.py getheightwidth` 上抛 `OSError: [WinError 6] 句柄无效`，REPL 崩溃重启继续刷，无限循环。
- **放大器**：核对器原来用 `subprocess.run(timeout=60)`，超时只杀 `bash.exe`；bash 拉起的 `python.exe` 是**孙进程**，不会被一起杀，继续往已被删除（Windows 上删除失败又被 `except OSError` 吞掉）的文件里写。所以「核对器返回了，磁盘还在涨」。
- **已修三处**（`fix(ai): 核对器加输出上限与进程树清理`）：
  1. 单条命令输出上限 4 MB，**边跑边看文件大小**，超了立刻 `taskkill /T` 杀整棵进程树
  2. 超时改用 `taskkill /F /T` 杀进程树，不留孤儿
  3. 进交互 REPL 的命令块（裸 `python`/`python3`/`py -3`）默认跳过，按 `&&`/`;`/`|` 分段判定，`cd X && python` 也挡得住
  4. 临时文件删不掉时打印路径，不再静默吞掉
- **验证**：修完再跑全量核对，`%TEMP%` 稳定在 320 MB，无遗留 python 进程；裸 python 块正确判为 risky 并跳过。

**F. 仍未修的过期点（下个 tick 处理）**

| 教程 | 现象 |
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


def main() -> None:
    with open(TARGET, "r", encoding="utf-8", newline="") as fh:
        original = fh.read()

    text = original

    if ANCHOR not in text:
        raise SystemExit("找不到 C 类锚点")
    if text.count(ANCHOR) != 1:
        raise SystemExit("C 类锚点出现多次")
    text = text.replace(ANCHOR, NEW_SECTION, 1)

    # 断言：新段落都在，旧的三个 tick 日志没动
    for marker in ("### 2026-11-05 全量复核（tick #4）",
                   "**D. 本轮已修**",
                   "**E. 核对器差点写满磁盘（本轮最严重的问题，已修）**",
                   "**F. 仍未修的过期点（下个 tick 处理）**"):
        assert marker in text, "新段落缺：%s" % marker
    assert text.count("#### tick #") == 3, "tick 段落数量变了"
    for stamp in ("#### tick #1（2026-10-28 22:18）",
                  "#### tick #2（2026-10-29 09:17）",
                  "#### tick #3（2026-10-30 12:27）"):
        assert stamp in text, "历史 tick 段落被弄丢：%s" % stamp
    # 旧结论保留
    assert "2026-10-30 用 `AI/脚本/_t12_verify_teach.py` 跑完全部 19 篇教程" in text
    assert "**B. 前向引用（不是错，等 `ls` 实现后自动对）**" in text

    with open(PREVIEW, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    with open(PREVIEW, "r", encoding="utf-8", newline="") as fh:
        check = fh.read()
    assert check == text, "预览文件和写入内容不一致"

    os.replace(PREVIEW, TARGET)
    print("已更新 %s" % TARGET)
    print("  追加 2026-11-05 复核结论（D/E/F 三类）")
    print("  旧的 A/B/C 结论和 3 段 tick 日志保持原样")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
