# w2l/registry.py — 指令注册表

`w2l/registry.py` 用一个字典和 `@command` 装饰器把所有指令集中登记起来，是「加指令不改主干」这条规则的落点。

## 为什么这么创建

需求是：加一个新命令，只写一个文件 `w2l/commands/<名字>.py`，`main.py` 和分发层一行都不改。

最直接的实现是在 `w2l/cli.py` 里写一串 `if name == "grep": ... elif name == "ls": ...`。但这个写法有两个坏处：

- 每加一个指令要动一次主干文件，主干成了所有人都会碰的公共文件，冲突频繁。
- 分发层会随指令数线性膨胀，越长越难读。

改成注册表后，指令模块在**被导入时**把自己登记进 `REGISTRY`，分发层只负责查字典。注册表里的值不是函数本身，而是一个 `Command` 数据类，字段是 `name` / `summary` / `parser_factory` / `handler`。

为什么 `parser_factory` 存**工厂**而不是 `ArgumentParser` 实例：短选项在不同指令里含义冲突。`grep -c` 是「只输出计数」，`wc -c` 很可能是「字节数」；如果共用一个解析器实例，选项定义会互相覆盖。工厂保证每次调用都新建一个解析器，`grep --help` 里永远只有 grep 自己的选项。

`Command` 用 `@dataclass(frozen=True)`：登记之后不允许改。注册表是全局状态，一旦某个指令在运行期偷偷改了 `summary`，帮助输出和实际行为就对不上了，排查起来很费时间。

## 这个文件是做什么

对外提供三样东西：

| 名字 | 类型 | 作用 |
|---|---|---|
| `Command` | frozen dataclass | 一条指令的登记信息 |
| `REGISTRY` | `dict[str, Command]` | 全局注册表 |
| `command(name, summary, parser_factory)` | 装饰器 | 把处理函数登记成指令 |

另有一个内部函数 `load_commands()`，由 `w2l/cli.py` 调用，触发 `w2l/commands/` 包的自动导入。

装饰器 `command` 的完整逻辑：

```python
def command(name: str, summary: str, parser_factory: ParserFactory):
    def decorator(func: CommandHandler) -> CommandHandler:
        if name in REGISTRY:
            raise RuntimeError(f"指令重复注册: {name}")
        REGISTRY[name] = Command(name, summary, parser_factory, func)
        return func
    return decorator
```

两个设计点：

- 装饰器**返回原函数**（`return func`），不返回包装器。处理函数被装饰后仍然是原来的函数，可以在测试里直接 import 调用——`tests/conftest.py` 的 `from w2l.commands.grep import build_parser, grep` 就是这么用的。
- 重复注册直接 `raise RuntimeError(f"指令重复注册: {name}")`。宁可启动失败，也不要两条指令抢同一个名字：后者会出现「谁先被导入谁生效」这种随机行为。

`load_commands()` 的短路条件是 `if REGISTRY: return`。这样同一个进程里第二次调用不会再走一遍导入。

不负责：解析参数、指令的具体实现、参数校验。

## 有什么用

- **主干稳定**：新指令是纯增量文件，不碰 `main.py`、`w2l/cli.py`。
- **帮助输出自动生成**：`python main.py` 的指令列表直接来自 `REGISTRY`，不会出现「实现了但没列出来」。
- **行为可预测**：注册表是显式数据，不是散在代码里的分支，找一个指令存在不存在只要查字典。
- **测试友好**：处理函数保持原样，可以脱离 CLI 直接调用。

## 怎么用（过程教程）

### 第 1 步：查当前注册了什么

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py
```

输出的「可用指令」列表就是 `REGISTRY` 的键，按字母序排序，右侧是 `Command.summary`。

### 第 2 步：在 Python 里直接查注册表

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q tests/test_grep.py::test_cli_help_lists_commands
```

这条用例断言 `main(["--help"])` 的输出里含 `grep`，等于间接验证了注册表里有 `grep` 这一项。

想直接看字典内容，可以临时开一个 REPL：

```bash
cd E:\1\NULL\Windows-to-Linux
python
```

```python
>>> from w2l.registry import load_commands, REGISTRY
>>> load_commands()
>>> sorted(REGISTRY)
['grep']
>>> REGISTRY['grep'].summary
'搜索包含 PATTERN 的行（GNU grep 风格子集）'
>>> REGISTRY['grep'].parser_factory
<function build_parser at 0x...>
```

### 第 3 步：用 `@command` 登记一个处理函数

新建 `w2l/commands/ls.py`（这一步属于「新增指令」，完整流程见 `13-新增一个指令的完整过程.md`）：

```python
import argparse

from ..context import RunContext
from ..registry import command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python main.py ls")
    parser.add_argument("path", nargs="?", default=".")
    return parser


@command("ls", "列出目录内容", build_parser)
def ls(args: argparse.Namespace, ctx: RunContext) -> int:
    for entry in sorted(ctx.cwd.joinpath(args.path).iterdir()):
        ctx.stdout.write(f"{entry.name}\n")
    return 0
```

三件事各归其位：

- `build_parser()` 只描述参数，不含逻辑，可以单独拿来测。
- `@command("ls", "列出目录内容", build_parser)` 把名字、帮助里的一句话说明、解析器工厂绑在一起。
- 处理函数签名固定为 `(args: argparse.Namespace, ctx: RunContext) -> int`。

### 第 4 步：验证自动生效

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py
```

预期：可用指令列表里多出 `ls`。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py ls w2l
```

预期输出：

```
__init__.py
cli.py
commands
context.py
errors.py
registry.py
```

### 第 5 步：确认重复注册会被挡住

如果两个模块用同一个名字，第二个模块被导入时就会抛异常，进程启动直接失败：

```text
RuntimeError: 指令重复注册: ls
```

这条检查的价值在于：它把「名字冲突」变成启动期的确定性错误，而不是运行期的随机行为（两个模块都注册成功时，取决于导入顺序，后来者覆盖先来者）。

### 第 6 步：注意 `REGISTRY` 是模块级全局

`REGISTRY` 在 `w2l/registry.py` 里是模块级字典，所有 import 它的地方共享同一份。测试里如果想隔离状态，可以这样：

```python
from w2l import registry

def test_isolated_registry(monkeypatch):
    monkeypatch.setattr(registry, "REGISTRY", {})
    ...
```

但通常不需要——`load_commands()` 的短路条件让「已导入就不再导入」的行为很稳定，重复导入不会造成重复注册。
