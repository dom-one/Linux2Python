# w2l/commands/__init__.py — 指令自动发现

`w2l/commands/__init__.py` 只有 12 行，负责在指令分发前把该目录下的所有指令模块导入一遍，从而触发它们完成注册。

## 为什么这么创建

需求是「加指令只加文件，主干不动」。分发的第一步是查 `REGISTRY`，但 `REGISTRY` 只有在指令模块**被导入**之后才会有内容。所以需要一个「把目录里的东西都导进来」的机制。

有三种做法：

- **显式 import**：`from . import grep, ls, cat`。每加一个指令要改这个文件，等于把注册表又维护了一遍，和需求冲突。
- **包目录自动发现**：用 `pkgutil.iter_modules` 扫目录，挨个 `importlib.import_module`。新增文件自动生效，不用改任何已有代码。
- **入口点机制**（`importlib.metadata` entry points）：更规范，但要求用户先 `pip install`，与「clone 就能跑」的目标冲突。

选了第二种。代价是：目录里的 `.py` 文件只要语法有问题，整个 CLI 启动就失败——没有「只导入部分模块」的机会。但这个代价可以接受，因为 `w2l/commands/` 里只放指令实现，出错概率低，出错时也容易定位。

## 这个文件是做什么

完整实现：

```python
"""指令模块集合。

把新指令写成同目录下的 .py 文件即可，load_all 会自动导入并完成注册。
"""

import importlib
import pkgutil


def load_all() -> None:
    for module in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{module.name}")
```

- `pkgutil.iter_modules(__path__)` 列出本包目录下的子模块，产出 `(finder, name, ispkg)`，`name` 是文件名主干（`grep.py` → `grep`）。
- `importlib.import_module("w2l.commands.grep")` 执行该模块的顶层代码，模块里的 `@command(...)` 装饰器在导入时执行，于是 `REGISTRY` 里就有了这一项。
- `__name__` 在这个包里是 `"w2l.commands"`，所以拼出来的全名带包前缀。

调用链：`w2l/cli.py` 的 `main()` → `load_commands()`（`w2l/registry.py`）→ `commands.load_all()` → 逐个 import。

不负责：指令注册的具体逻辑（在 `w2l/registry.py` 的装饰器里）、参数解析、业务逻辑。

## 有什么用

- 新指令是纯增量：`w2l/commands/<名字>.py` 一放进去就生效，不改 `main.py`、不改 `w2l/cli.py`、不改这个 `__init__.py`。
- 少写一份清单：不需要维护「指令列表」这个第二份真相源。
- 导入顺序无关：注册表是字典，指令之间不互相依赖，加哪个先导都行。

## 怎么用（过程教程）

### 第 1 步：确认自动发现确实在工作

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py
```

输出的「可用指令」列表来自 `REGISTRY`，而 `REGISTRY` 的内容来自这个文件的导入过程。

### 第 2 步：看自动发现扫到了什么

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q
```

预期：`36 passed`。这一步会导入 `w2l.commands.grep` 并执行注册。

### 第 3 步：加一个新文件试试（验证流程，验完可删）

新建 `w2l/commands/echo.py`：

```python
import argparse

from ..context import RunContext
from ..registry import command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python main.py echo")
    parser.add_argument("text", nargs="?", default="")
    return parser


@command("echo", "回显一段文字", build_parser)
def echo(args: argparse.Namespace, ctx: RunContext) -> int:
    ctx.stdout.write(args.text + "\n")
    return 0
```

立刻验证，不需要重启什么、不需要改任何其它文件：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py echo "hello"
```

预期输出：

```
hello
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py
```

预期：可用指令列表变成两行，`echo` 和 `grep`。

验完删掉：

```bash
rm -- w2l/commands/echo.py
```

### 第 4 步：模块文件名和指令名是两件事

自动发现用的是**文件名**，`@command("...")` 的第一个参数才是**指令名**。两者可以不同。

开发任务的命令队列（`cron.md`）里有一项叫 `awk-lite`，带连字符。实现它时建议：

- 模块文件命名 `w2l/commands/awk_lite.py`（Python 模块名用下划线）
- 装饰器写 `@command("awk-lite", "按字段取值", build_parser)`
- 用户敲 `python main.py awk-lite ...`

这样模块名保持 Python 惯例，指令名保持 Linux 习惯。

### 第 5 步：知道自动发现的三个坑

**坑一：新文件语法错误会让整个 CLI 起不来。**

`load_all()` 里没有 try/except，任何导入异常都会直接冒到 `main()` 外面。所以 `w2l/commands/` 里放一个写坏的 `.py`，`python main.py` 立刻 traceback，连 `grep` 都用不了。改完新指令后除了跑 `python main.py grep --help`，最好也跑一次 `python main.py` 确认整体能启动。

**坑二：目录里放的任何 `.py` 都会被导入。**

`pkgutil.iter_modules` 不区分「这是不是一个指令模块」。往 `w2l/commands/` 里放一个临时脚本、或者放一个 `__pycache__` 之外的大工具文件，它都会被执行一次。临时验证文件用完要删掉。

**坑三：`pkgutil.iter_modules` 只扫本层，不递归子包。**

它列出的是 `w2l/commands/` 这一层的模块。子目录不会自动被当成指令集合处理。

### 第 6 步：注册表是全局的，别在导入期做重活

模块顶层代码在导入时执行，除了 `@command` 装饰，模块顶层还会跑一遍。所以模块顶层只放定义，别放「打开文件」「读配置」这类动作——它们会在每次进程启动时执行，哪怕你敲的是别的指令。

需要初始化的话，放在处理函数里。
