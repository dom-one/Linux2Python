# w2l/cli.py — 分发层

`w2l/cli.py` 是指令分发的中枢：解析指令名、构造运行上下文、把异常翻译成退出码，并在 Windows 上把控制台编码强制成 UTF-8。

## 为什么这么创建

有几件事必须在**一个地方**做，而不是分散到每个指令里：

- **Windows 控制台编码**。Windows 中文版控制台默认代码页是 GBK，直接 `print` 中文可能抛 `UnicodeEncodeError`。如果每个指令自己处理，十个指令就有十处补丁，漏一处就崩一处。所以在 `_configure_streams()` 里统一做：调 `SetConsoleOutputCP(65001)` 把控制台切到 UTF-8，再把 `sys.stdout` / `sys.stderr` / `sys.stdin` 三个流 `reconfigure(encoding="utf-8", errors="replace")`。
- **异常到退出码的映射**。指令层只抛 `UsageError` / `CommandError`，具体该是退出码 2 还是 1 由分发层决定。这样「退出码约定」只有一处定义，加新指令不用重新讨论。
- **帮助输出**。`python main.py` 不带参数时列可用指令，列表来自 `REGISTRY`，所以新指令自动出现在帮助里，不用维护第二份清单。

反过来，如果这些逻辑写在 `main.py`，那 `pip install` 出来的 `w2l` 命令（入口是 `w2l.cli:main`）就拿不到编码处理，Windows 上照样乱码。`w2l/cli.py` 是「程序逻辑」和「进程入口」之间唯一被两边共享的位置。

另外 `parser_factory` 存的是**工厂**而不是现成的 `ArgumentParser` 实例。因为 `-c`、`-l`、`-n`、`-o` 这些短选项在不同指令里含义不同（`grep -c` 是计数，`wc -c` 可能是字节数），必须每个指令各建各的解析器。

## 这个文件是做什么

对外只暴露一个函数：`main(argv: list[str] | None = None) -> int`。

它依次做五件事：

1. `_configure_streams()`：Windows 控制台代码页 + 三个标准流编码。
2. `load_commands()`：触发指令注册（见 `w2l/registry.py`）。
3. 判断无参数 / `--help` / 未知指令名。
4. `entry.parser_factory()` 建解析器 → `parse_args` → 建 `RunContext` → 调 `entry.handler(namespace, ctx)`。
5. 把 `UsageError` / `CommandError` / `BrokenPipeError` / `KeyboardInterrupt` 转成退出码。

内部辅助函数：

| 函数 | 作用 |
|---|---|
| `_print_help()` | 打印用法 + 从 `REGISTRY` 生成指令列表 |
| `_configure_streams()` | UTF-8 编码统一处理 |
| `_set_console_utf8()` | 用 `ctypes.windll.kernel32` 调 `SetConsoleOutputCP(65001)` / `SetConsoleCP(65001)` |
| `_silence_broken_pipe()` | 管道被下游关闭时把 stdout 指向 `os.devnull`，避免解释器退出时刷 `BrokenPipeError` |

不负责：具体指令的业务逻辑、指令注册表本身、正则与编码判定。

## 有什么用

- 让「敲命令」这件事有统一的失败语义：`0` 成功、`1` 无结果、`2` 出错，可以直接写进 PowerShell 脚本或 CI 判断。
- 让中文输出在 Windows 上不乱码，包括管道重定向时。
- 让 `python main.py` 变成一个有用的命令（列出可用指令），而不是一个报错。
- 让 `pip install` 出来的 `w2l` 命令和 `python main.py` 行为完全一致。

## 怎么用（过程教程）

### 第 1 步：按这个顺序读 `main()`

`w2l/cli.py:61` 起：

```python
def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    _configure_streams()
    load_commands()
    ...
```

`argv` 为 `None` 时取 `sys.argv[1:]`；传了列表就用它——后者正是单元测试能直接构造参数的原因。

### 第 2 步：对照四种退出码跑一遍

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py; echo "退出码=$?"          # 无参数 → 1
python main.py --help; echo "退出码=$?"    # 帮助 → 0
python main.py ls; echo "退出码=$?"        # 未知指令 → 2
python main.py grep "def" w2l/cli.py; echo "退出码=$?"  # 命中 → 0
python main.py grep "zzz" w2l/cli.py; echo "退出码=$?"  # 未命中 → 1
```

未知指令的 stderr 长这样：

```
未知指令: ls
可用指令: grep
```

### 第 3 步：验证 Windows 编码处理真的生效

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep "错误" w2l/errors.py
```

预期输出（正常 UTF-8 终端）：

```
8:    """用法错误，退出码 2。"""
```

如果这里出现 `UnicodeEncodeError` 或者问号方块，说明 `_configure_streams()` 里的 `reconfigure` 没生效——检查 `sys.stdout` 是否被换成了不支持 `reconfigure` 的对象（代码里用 `getattr(stream, "reconfigure", None)` 做了兼容，找不到就跳过）。

### 第 4 步：验证断管道不会喷异常

`grep` 输出很多行时管道给下游（`head`）只取前几行，下游退出后写 stdout 会抛 `BrokenPipeError`。`_silence_broken_pipe()` 专门处理这个：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -r "def " . | head -3; echo "退出码=${PIPESTATUS[0]}"
```

预期输出（只有三行，无 traceback）：

```
README.md:def build_parser() -> argparse.ArgumentParser:
README.md:def ls(args: argparse.Namespace, ctx: RunContext) -> int:
git\hooks\pre-rebase.sample:					undef $msg;
退出码=0
```

`${PIPESTATUS[0]}` 是 `python` 这一环的退出码，`0` 来自 `except BrokenPipeError: _silence_broken_pipe(); return 0`。

### 第 5 步：写一个新指令时，分发层要不要动

不用动。只要新指令模块在 `w2l/commands/` 下并用 `@command` 装饰，`load_commands()` 会把它导进 `REGISTRY`，`python main.py` 的可用指令列表会自动多出一行：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py
```

改动分发层的唯一理由是「要加一个全局开关」这类需求，而不是「要多一个指令」。

### 第 6 步：注意 argparse 的错误不走 `main()` 的返回值

`parser.parse_args(argv[1:])` 在参数缺失时会 `print` 用法并 `sys.exit(2)`，直接结束进程，不经过 `main()` 的 `return`：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep; echo "退出码=$?"
```

预期输出：

```
usage: python main.py grep [-h] [-i] [-v] [-n] [-r] [-E] [-w] [-c] [-l] [-o]
                           pattern [paths ...]
python main.py grep: error: the following arguments are required: pattern
退出码=2
```

退出码同样是 2，和 `UsageError` 的语义一致，但产生位置不同。这一点在写测试时有实际影响：不要用 `main()` 去测参数缺失的路径，会让 pytest 进程直接退出；这种用例应该直接测 `build_parser()` 抛 `SystemExit`，或者绕开 argparse 直接构造 `Namespace`（`tests/test_grep.py` 里 `test_invalid_regex_is_usage_error` 就是后者）。
