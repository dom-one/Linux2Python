# w2l/context.py — 运行上下文

`w2l/context.py` 定义了 `RunContext` 这个数据类，把「当前目录」和「三个标准流」打包传给指令实现。

## 为什么这么创建

如果指令直接用 `sys.stdout` 写输出，会带来三个具体麻烦：

1. **没法测**。测试要断言输出内容，就得往 `sys.stdout` 上挂 `capsys` 或 `monkeypatch`，而且指令一旦用了 `print` 而不是 `sys.stdout.write`，测试和实现的耦合点就散开了。
2. **没法扩展输出通道**。以后想加 `--json` 输出，输出就不该只有 stdout 一个去处。
3. **没法换工作目录**。有的指令需要以某个目录为基准解析相对路径，得有个明确的地方放这个基准。

`RunContext` 就是把这些「环境」变成显式参数。指令处理函数的签名固定成 `(args: argparse.Namespace, ctx: RunContext) -> int`，所有环境相关的东西从 `ctx` 拿，不从全局拿。

代价是多写一个参数、多一层间接。收益是每条指令都能被完整地塞进内存里跑——`tests/conftest.py` 的 `run_grep()` 就是把 `stdout` / `stderr` 换成 `io.StringIO()`、`stdin` 换成 `io.StringIO(stdin_text)`，然后直接调处理函数，完全不碰进程环境。

为什么不用 `contextvars` 或线程局部变量：那些方案在多线程下会给出「隐式全局」的错觉，读代码的人看不出数据从哪来；而且这个项目是单进程单线程的命令行工具，显式传参的成本可以忽略。

## 这个文件是做什么

只有一个类：

```python
@dataclass
class RunContext:
    cwd: Path
    stdout: TextIO
    stderr: TextIO
    stdin: TextIO
```

`@dataclass` 自动生成 `__init__` 和 `__repr__`，所以测试里可以直接 `RunContext(cwd=..., stdout=out, stderr=err, stdin=...)`，四个字段全用关键字传。

这个类**没有任何方法**，纯粹是数据搬运。行为全在指令里。

构造点在 `w2l/cli.py:82`：

```python
ctx = RunContext(cwd=Path.cwd(), stdout=sys.stdout, stderr=sys.stderr, stdin=sys.stdin)
```

不负责：输出缓冲、编码设置（那是 `w2l/cli.py` 的 `_configure_streams`）、异常与退出码（那是 `w2l/errors.py`）。

## 有什么用

- 指令实现不再直接依赖 `sys` 模块，函数签名本身就是一份依赖清单。
- 测试可以把输入输出换成内存对象，跑得又快又不污染终端。
- `ctx.cwd` 给「相对路径以哪为基准」这个问题一个明确答案：`python main.py` 启动时的 `Path.cwd()`。
- 将来加 `--json`、`--output FILE` 之类选项时，多一个去处不用改指令签名。

## 怎么用（过程教程）

### 第 1 步：看它是怎么被造出来的

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep --help
```

帮助里看不到 `ctx`，因为它是内部参数。真正要看的是 `w2l/cli.py:82` 那一行。

### 第 2 步：在测试里造一个 ctx

打开 `tests/conftest.py`，核心辅助函数是这样：

```python
def run_grep(argv, cwd=None, stdin_text=""):
    namespace = build_parser().parse_args(list(argv))
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(
        cwd=Path(cwd or ROOT),
        stdout=out,
        stderr=err,
        stdin=io.StringIO(stdin_text),
    )
    code = grep(namespace, ctx)
    return code, out.getvalue(), err.getvalue()
```

三个流全是内存对象，所以断言输出就是断言字符串：

```python
code, out, err = run_grep(["ERROR", str(sample_tree / "app.log")])
assert out == "ERROR failed\nERROR again\n"
```

### 第 3 步：自己写一条最简测试

新建一个临时文件 `tests/test_ctx_demo.py`：

```python
import io
from pathlib import Path

from w2l.context import RunContext
from w2l.commands.grep import build_parser, grep


def test_ctx_demo(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("hello\nworld\n", encoding="utf-8")
    out = io.StringIO()
    ctx = RunContext(cwd=tmp_path, stdout=out, stderr=io.StringIO(), stdin=io.StringIO())
    namespace = build_parser().parse_args(["world", str(target)])
    code = grep(namespace, ctx)
    assert code == 0
    assert out.getvalue() == "world\n"
```

跑：

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q tests/test_ctx_demo.py
```

预期：`1 passed`。验完删掉这个临时文件：

```bash
rm -- tests/test_ctx_demo.py
```

### 第 4 步：注意 `ctx.cwd` 不会自动影响相对路径

`ctx.cwd` 只是**一个记录**，不是「切换了工作目录」。`grep` 的 `ctx.cwd` 字段在整个实现里没有被使用——它把 `args.paths` 里的路径直接 `Path(raw)` 解析，相对路径按进程当前目录解析，与 `ctx.cwd` 无关。

所以想测「相对路径」行为时，要靠进程的工作目录（`monkeypatch.chdir`），不能指望 `ctx.cwd`：

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q
```

预期：36 passed（现有用例都用 `tmp_path` 的绝对路径）。

### 第 5 步：`ctx.stdin` 的一个特殊约定

`grep` 判断「标准输入是不是管道」用的不是 `sys.stdin` 而是 `ctx.stdin`：

```python
paths = list(args.paths)
recursive = args.recursive
stdin_mode = not paths

if stdin_mode:
    if ctx.stdin is None:
        raise UsageError("没有指定文件，也没有可读取的标准输入")
    if ctx.stdin.isatty():
        paths = ["."]
        recursive = True
        stdin_mode = False
        ctx.stderr.write("未指定路径：递归搜索当前目录（.）。要读标准输入请用管道。\n")
```

真实终端的 `sys.stdin.isatty()` 返回 `True`（交互式终端），管道重定向时返回 `False`。终端分支把搜索目标换成当前目录并打开递归，管道分支保持读 stdin。

测试里因为用了 `io.StringIO`（`isatty()` 默认返回 `False`），`run_grep(["warn"], stdin_text="ok\nwarn here\n")` 会走管道分支；要测终端分支需要 `tests/conftest.py` 里那个 `_Tty` 类：

```python
class _Tty(io.StringIO):
    def isatty(self) -> bool:
        return True
```

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q tests/test_grep.py::test_no_path_in_terminal_searches_current_directory
```

预期：通过。用例用 `monkeypatch.chdir(tmp_path)` 把工作目录换到临时目录，断言搜到了临时目录里的文件、没输出不含匹配的文件。

### 第 6 步：真实管道也能搜

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'ok\nwarn here\n' | python main.py grep warn
```

预期输出：

```
warn here
```

注意 `printf` 在 Git Bash 里可用；PowerShell 里换成 `"ok`nwarn here" | python main.py grep warn`。
