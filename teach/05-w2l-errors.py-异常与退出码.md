# w2l/errors.py — 异常与退出码

`w2l/errors.py` 定义两个异常类：`UsageError`（用法错误，退出码 2）和 `CommandError`（执行失败，退出码 1）。它们是指令层唯一的两种失败信号。

## 为什么这么创建

失败有两种，语义完全不同：

- **用法错误**：命令本身没写对——正则非法、目录忘了加 `-r`、没给文件也没给管道。这类错误用户改一下命令就能解决，退出码给 2，和 GNU 工具的习惯一致（参数错 = 2）。
- **执行失败**：命令写法没错，但事情没做成——文件被占用、权限不足。这类错误退出码给 1。

如果让指令自己 `sys.exit(2)`，会有两个问题：一是指令层开始关心进程状态，测试时无法安全调用；二是退出码知识散落在每个指令里，`grep` 写 2、`ls` 写 1、`wc` 写 3，谁也说不清全局约定。

所以设计成：指令层只抛异常，分发层 `w2l/cli.py` 统一映射：

```python
    except UsageError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    except CommandError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
```

指令作者只需要判断「这是用法错还是执行错」，具体数字由分发层决定。这是把「约定」集中化的常规做法，代价是多写一层异常类型。

注意：**「没找到结果」不是错误**。`grep` 搜不到东西返回的是退出码 1，但不是通过抛 `CommandError` 实现的，而是直接 `return 1`。理由是「无命中」是正常结果，`CommandError` 是异常路径，两者混用会让调用方难以区分「失败了」和「没结果」。

## 这个文件是做什么

两个空的异常子类：

```python
class UsageError(Exception):
    """用法错误，退出码 2。"""


class CommandError(Exception):
    """指令执行失败，退出码 1。"""
```

没有任何逻辑、没有任何基类定制。继承 `Exception` 而不是 `BaseException`，这样 `except Exception` 之类的兜底不会误捕获 `KeyboardInterrupt`（`w2l/cli.py` 单独捕获它并返回 130）。

不负责：异常到退出码的映射（在 `w2l/cli.py`）、错误信息文案格式（在 `w2l/cli.py` 统一加 `错误: ` 前缀）。

## 有什么用

- 指令实现只表达语义，不表达数字。新指令不用再查「用法错误该返回几」。
- 错误信息统一走 stderr，统一带 `错误: ` 前缀，脚本里可以稳定地匹配。
- 退出码 0/1/2 的约定在整个项目里只有一处定义，可以直接写进 PowerShell 脚本和 CI 判断。

## 怎么用（过程教程）

### 第 1 步：看清当前 `grep` 在哪里抛 `UsageError`

`w2l/commands/grep.py` 里有四处：

| 位置 | 触发条件 | 消息 |
|---|---|---|
| `grep.py:70` | 没给文件，且 stdin 是终端 | `没有指定文件，且标准输入不是终端，无法确定搜索目标` |
| `grep.py:82` | 给了目录但没加 `-r` | `{path}: 是一个目录，请加 -r 递归搜索` |
| `grep.py:105` | 正则编译失败 | `无效的正则表达式 '{pattern}': {exc}` |
| `_translate_bre` 内 | 模式以孤立反斜杠结尾 | 经 `re.error` 转换后同样走 `grep.py:105` |

跑一遍看效果：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep "TODO" w2l; echo "退出码=$?"
```

预期（stderr）：

```
错误: w2l: 是一个目录，请加 -r 递归搜索
退出码=2
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep "[unclosed" README.md; echo "退出码=$?"
```

预期（stderr）：

```
错误: 无效的正则表达式 '[unclosed': unterminated character set at position 0
退出码=2
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep; echo "退出码=$?"
```

预期：这条走的是 argparse 自己的错误路径（参数缺失），不是 `UsageError`，但退出码同样是 2。

### 第 2 步：文件不存在走的是另一条路

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep "x" 不存在的文件.txt; echo "退出码=$?"
```

预期（stderr，退出码 2）：

```
不存在的文件.txt: No such file or directory
```

这条不是 `UsageError`，而是 `grep` 内部捕获 `OSError` 后自己写 stderr 并置 `had_error = True`，最后 `return 2`。也就是说「文件读不了」这种运行期失败，指令层是**自己处理**的，没走异常机制。

注意这条消息**没有** `错误: ` 前缀——那个前缀是分发层 `w2l/cli.py` 统一加的，指令自己写 stderr 就没有前缀。两种写法目前并存，属于已知的不一致。

### 第 3 步：在新指令里抛异常

```python
from ..errors import UsageError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python main.py head")
    parser.add_argument("path")
    parser.add_argument("-n", type=int, default=10)
    return parser


@command("head", "取文件开头若干行", build_parser)
def head(args: argparse.Namespace, ctx: RunContext) -> int:
    if args.n <= 0:
        raise UsageError(f"-n 必须为正整数，收到 {args.n}")
    ...
```

抛出去之后，分发层负责打印 `错误: ...` 并返回 2。

### 第 4 步：什么时候该用 `CommandError`

`CommandError` 对应「命令写法没错，但执行失败」。判断标准是：**同样的命令换个环境能不能成功**。

- 不能（参数本身有问题）→ `UsageError`
- 能（参数没问题，是环境/资源的问题）→ `CommandError`

比如 `head` 读一个被别的进程独占锁住的文件：参数没错，换台机器能成功 → `CommandError`。

目前 `w2l/commands/` 下只有 `grep.py` 一个指令，它只用了 `UsageError`；`CommandError` 目前还没有任何指令在用，是留给后续指令的接口（`w2l/cli.py` 已经接好了）。

### 第 5 步：在测试里断言异常

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q tests/test_grep.py::test_invalid_regex_is_usage_error tests/test_grep.py::test_trailing_backslash_is_usage_error tests/test_grep.py::test_directory_without_recursive_is_usage_error
```

预期：3 passed。这三条用例的写法是：

```python
namespace = build_parser().parse_args(["[unclosed", str(sample_tree / "app.log")])
ctx = RunContext(cwd=sample_tree, stdout=io.StringIO(), stderr=io.StringIO(), stdin=_Tty())
with pytest.raises(UsageError):
    grep(namespace, ctx)
```

注意这里**不经过 `main()`**：直接构造 `Namespace` 再调处理函数，异常原样抛出，不会被分发层翻译成退出码。要测退出码映射，才需要走 `main()`。

### 第 6 步：退出码对照表

| 场景 | 谁产生 | 退出码 |
|---|---|---|
| 有命中 / 正常完成 | 指令 `return 0` | 0 |
| 无命中 | 指令 `return 1` | 1 |
| 未知指令名 | `w2l/cli.py` | 2 |
| 用法错误 | `UsageError` | 2 |
| 参数缺失 / 非法参数 | argparse | 2 |
| 文件读不了 | 指令捕获 `OSError` | 2 |
| 执行失败 | `CommandError` | 1 |
| 用户按 Ctrl+C | `KeyboardInterrupt` | 130 |
| 管道被关闭 | `BrokenPipeError` | 0 |
| 不带参数运行 `python main.py` | `w2l/cli.py` | 1 |
