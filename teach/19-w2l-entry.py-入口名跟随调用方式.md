# w2l/entry.py — 入口名跟随调用方式

`w2l/entry.py` 只有 26 行，两个函数。它回答一个很小的问题：**这个程序现在应该管自己叫什么？**

答案是「看你怎么调用它的」——直接跑项目叫 `python main.py`，通过全局启动器跑叫 `dmlinux`。这个模块负责在两种叫法之间切换，让帮助文案和报错信息永远显示你实际敲的那条命令。

## 为什么这么创建

项目有两种入口写法：

- 直接跑项目：`python main.py grep -n TODO src`
- 通过全局启动器：`dmlinux grep -n TODO src`

第二种的实现是 `bin/` 下的两份启动器（`dmlinux.cmd` 给 cmd/PowerShell，`dmlinux` 给 git-bash/WSL）。它们把 `bin/` 加进 PATH 之后，你就能在任意目录直接敲 `dmlinux`，不用先 `cd` 回项目根。

问题出在**帮助文案**上。argparse 生成用法行时会用一个 `prog` 字符串，默认取 `sys.argv[0]` 的 basename，也就是 `main.py`。命令行报错时，argparse 也会在错误信息前面加上这个 `prog`：

```
usage: main.py grep [-h] [-i] ...
main.py grep: error: the following arguments are required: pattern
```

一个用 `dmlinux` 的人看到 `main.py grep: error: ...`，会以为程序坏了一直让他跑 `main.py`。这跟 GNU 工具的做法相反——`grep` 报错时说的是 `grep`，不是 `/usr/bin/grep`；用户复制报错信息里的命令就能直接粘贴执行。

所以这里需要一件事：**程序知道自己被怎么调用，就显示对应的名字**。

### 为什么用环境变量，而不是别的办法

有几种 conceivable 的做法，都不合适：

| 方案 | 为什么不选 |
|---|---|
| 硬编码成 `python main.py` | 用启动器的人看到的还是错的 |
| 从 `sys.argv[0]` 推 | 启动器最终也是执行 `python main.py`，`argv[0]` 里看不出区别 |
| 加命令行选项 `--as=dmlinux` | 要用户每次都敲，违背了「加进 PATH 直接用」的初衷 |
| 读环境变量 | 启动器设一个变量，程序读它，双方都不用改命令行 |

环境变量这条路的实现成本极低：`bin/dmlinux.cmd` 里一行 `set "DMLINUX=1"`，`bin/dmlinux` 里一行 `export DMLINUX=1`。启动器在拉起 Python 进程前设好，Python 进程继承这个环境，读到就切换名字。

### 为什么单独一个文件，而不是塞进 `cli.py`

因为**要用它的不止 `cli.py` 一个地方**。

顶层帮助（`w2l/cli.py:16`）和五个指令自己的用法行（`w2l/commands/grep.py:41`、`ls.py:47`、`cat.py:67`、`head.py:196`、`tail.py:201`）都要这个前缀。如果逻辑写在 `cli.py` 里，五个指令模块就得反向 import `cli`，而 `cli` 又要 import `registry`，`registry` 又会加载指令模块——形成循环依赖。

把它抽成一个只依赖 `os` 的叶子模块，任何人都能 import 它，没有环。

### 为什么不用「更聪明」的判断

有人会想：能不能判断当前是不是从终端直接敲的？比如检查 `sys.stdout.isatty()`。不能——用启动器跑也是终端，用 `python main.py` 跑也可能重定向到管道。环境变量是启动器**主动声明**的意图，比任何间接推断都可靠。

## 这个文件是做什么

完整实现（26 行，792 字节）：

```python
"""入口名称：让帮助文案跟着实际调用方式走。

同一个入口有两种走法：

- 直接跑项目：``python main.py grep ...``
- 通过全局启动器：``dmlinux grep ...``（bin/dmlinux.cmd 或 bin/dmlinux）

启动器会设置环境变量 ``DMLINUX=1``，据此决定帮助里显示哪个命令名，
这样 ``dmlinux grep --help`` 不会还打印 ``python main.py grep``。
"""

from __future__ import annotations

import os

ENV_FLAG = "DMLINUX"


def entry_name() -> str:
    """返回当前调用方式对应的入口名。"""
    return "dmlinux" if os.environ.get(ENV_FLAG) else "python main.py"


def command_prog(name: str) -> str:
    """返回某个指令在用法文案里的完整前缀，例如 ``dmlinux grep``。"""
    return f"{entry_name()} {name}"
```

三个对外名字：

| 名字 | 类型 | 作用 |
|---|---|---|
| `ENV_FLAG` | 常量 | 环境变量名 `"DMLINUX"`，抽成常量是为了避免在代码里散落魔法字符串 |
| `entry_name()` | 函数 | 返回 `"dmlinux"` 或 `"python main.py"` |
| `command_prog(name)` | 函数 | 返回 `"<入口名> <指令名>"`，例如 `"dmlinux grep"` |

### 判断条件为什么是「有值」而不是「等于 1」

`os.environ.get(ENV_FLAG)` 返回的是字符串。判定走的是 Python 的**真值**规则：

- 环境变量**没设** → `get` 返回 `None` → 假值 → `"python main.py"`
- 环境变量**设为空串** → `get` 返回 `""` → 假值 → `"python main.py"`
- 环境变量**设成任何非空字符串**（包括 `"0"`、`"yes"`、一个空格）→ 真值 → `"dmlinux"`

这个细节有实际后果，见下面第 5 步。

### 谁在用它

```
$ python main.py grep -n "command_prog" w2l/commands/grep.py
19:from ..entry import command_prog
41:    prog = command_prog("grep")
```

全仓库的调用点一共 6 处：

| 调用点 | 用哪个函数 | 影响的输出 |
|---|---|---|
| `w2l/cli.py:16` | `entry_name()` | 顶层 `用法:` 行和 `查看具体用法:` 行 |
| `w2l/commands/grep.py:41` | `command_prog("grep")` | grep 的用法行、报错前缀、示例块 |
| `w2l/commands/ls.py:47` | `command_prog("ls")` | ls 的用法行、报错前缀、示例块 |
| `w2l/commands/cat.py:67` | `command_prog("cat")` | cat 的用法行、报错前缀、示例块 |
| `w2l/commands/head.py:196` | `command_prog("head")` | head 的用法行、报错前缀、示例块 |
| `w2l/commands/tail.py:201` | `command_prog("tail")` | tail 的用法行、报错前缀、示例块 |

每个指令的 `build_parser()` 里都有一行 `prog = command_prog("xxx")`，这个 `prog` 同时决定了三样东西：**用法行**、**报错信息前缀**、**示例块里的命令**。

不负责：判断当前是不是启动器（它只读环境变量）、写帮助文案（那是 `cli.py` 和各指令的事）、改 `sys.argv[0]`。

## 有什么用

**1. 报错信息里的话能直接复制执行。**

这是最实用的一条。argparse 报错时会把 `prog` 放在错误前面：

```
python main.py grep: error: the following arguments are required: pattern
```

用户复制这一行就能原样再跑一遍。走启动器时则是：

```
dmlinux grep: error: the following arguments are required: pattern
```

两种写法都对得上用户自己敲的命令。

**2. 用法行跟着入口走。**

`dmlinux grep --help` 显示 `usage: dmlinux grep ...`，不是 `usage: main.py grep ...`。

**3. 顶层帮助的调用提示跟着走。**

`dmlinux --help` 最后一行是「查看具体用法: dmlinux <指令> --help」，提示的也是启动器写法。

**4. 指令的示例块跟着走。**

`grep` 的示例块是用 `prog` 拼的：

```
示例:
  dmlinux grep -n TODO src
  dmlinux grep -ril error .
```

从 `python main.py` 进来时，这四行自动变成 `python main.py grep -n TODO src` 这样。

**5. 副作用为零。**

`entry.py` 只 import `os`，不读文件、不碰 `sys.argv`、不改全局状态。删掉它整个项目立刻报错（`cli.py` 和五个指令模块都 import 它），但只要保留，任何一个函数单独调用都没有副作用。

## 怎么用（过程教程）

下面所有命令都实测过，输出与文档一致。用 `AI/脚本/_t12_verify_teach.py` 可以自动核对本篇的命令。

### 第 1 步：先看清这个文件有多小

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -n "def " w2l/entry.py
```

预期输出：

```
19:def entry_name() -> str:
24:def command_prog(name: str) -> str:
```

两个函数，加一个常量 `ENV_FLAG`，没有别的了。

### 第 2 步：看两个函数分别返回什么

```bash
cd E:\1\NULL\Windows-to-Linux
python -c "from w2l.entry import entry_name, command_prog;print(entry_name());print(command_prog('grep'))"
```

预期输出：

```
python main.py
python main.py grep
```

没设 `DMLINUX` 时，`entry_name()` 返回 `python main.py`，`command_prog()` 在它后面接一个空格和指令名。

### 第 3 步：设上环境变量，看它变过来

```bash
cd E:\1\NULL\Windows-to-Linux
DMLINUX=1 python -c "from w2l.entry import entry_name, command_prog;print(entry_name());print(command_prog('grep'))"
```

预期输出：

```
dmlinux
dmlinux grep
```

`DMLINUX=1` 是 bash 的「临时设一个环境变量给这一条命令」写法，不影响当前 shell。Windows 的 cmd 里对应 `set DMLINUX=1`。

### 第 4 步：看顶层帮助的差别

不设环境变量：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py --help | head -1
```

预期输出：

```
用法: python main.py <指令> [参数]
```

设上环境变量：

```bash
cd E:\1\NULL\Windows-to-Linux
DMLINUX=1 python main.py --help | head -1
```

预期输出：

```
用法: dmlinux <指令> [参数]
```

同一段代码，输出的名字跟着环境变量走。

### 第 5 步：搞清「设了变量就生效」的真实判定规则

这一步是最容易想当然的地方。判定用的是真值，不是「等于 1」：

```bash
cd E:\1\NULL\Windows-to-Linux
DMLINUX=0 python main.py --help | head -1
```

预期输出：

```
用法: dmlinux <指令> [参数]
```

`"0"` 是一个**非空字符串**，在 Python 里是真值。所以 `DMLINUX=0` 反而会切换成 `dmlinux`——想关掉它，得把变量**设成空串**：

```bash
cd E:\1\NULL\Windows-to-Linux
DMLINUX= python main.py --help | head -1
```

预期输出：

```
用法: python main.py <指令> [参数]
```

或者干脆 `unset DMLINUX`。

这条规则的另一面：**只要环境里有这个变量（不管值是什么），就一律当成启动器调用**。启动器自己设的是 `DMLINUX=1`，所以走启动器时不受父环境里 `DMLINUX` 是什么值的影响：

```bash
cd E:\1\NULL\Windows-to-Linux
PATH="$PATH:$PWD/bin" DMLINUX=0 dmlinux --help | head -1
```

预期输出：

```
用法: dmlinux <指令> [参数]
```

### 第 6 步：看指令级的用法行怎么变

`prog` 会同时影响用法行和后面的参数列表缩进：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep --help | head -2
```

预期输出：

```
usage: python main.py grep [-h] [-i] [-v] [-n] [-r] [-E] [-w] [-c] [-l] [-o]
                           pattern [paths ...]
```

设上环境变量：

```bash
cd E:\1\NULL\Windows-to-Linux
DMLINUX=1 python main.py grep --help | head -2
```

预期输出：

```
usage: dmlinux grep [-h] [-i] [-v] [-n] [-r] [-E] [-w] [-c] [-l] [-o]
                    pattern [paths ...]
```

第二行的缩进也跟着 `prog` 变短了——argparse 是按 `prog` 的长度对齐参数列表的。

### 第 7 步：看报错信息里的前缀

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -Z 2>&1 | tail -1
```

预期输出：

```
python main.py grep: error: the following arguments are required: pattern
```

设上环境变量：

```bash
cd E:\1\NULL\Windows-to-Linux
DMLINUX=1 python main.py grep -Z 2>&1 | tail -1
```

预期输出：

```
dmlinux grep: error: the following arguments are required: pattern
```

注意 `-Z` 不是 grep 的合法选项，但报错说的是「缺 pattern」——因为 argparse 先检查位置参数，用户没给 pattern。这跟 GNU grep 的行为一致，不是本项目的 bug。

### 第 8 步：走一遍真正的启动器

`bin/` 加进 PATH 之后（`PATH="$PATH:$PWD/bin"` 就是临时加一下）：

```bash
cd E:\1\NULL\Windows-to-Linux
PATH="$PATH:$PWD/bin" dmlinux --help | head -1
```

预期输出：

```
用法: dmlinux <指令> [参数]
```

指令级的也一样：

```bash
cd E:\1\NULL\Windows-to-Linux
PATH="$PATH:$PWD/bin" dmlinux grep --help | head -1
```

预期输出：

```
usage: dmlinux grep [-h] [-i] [-v] [-n] [-r] [-E] [-w] [-c] [-l] [-o]
```

启动器里设置环境变量的地方：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -n "DMLINUX" bin/dmlinux
```

预期输出：

```
26:export DMLINUX=1
```

Windows 那份：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -n "DMLINUX" bin/dmlinux.cmd
```

预期输出：

```
13:set "DMLINUX_HOME=%~dp0.."
14:set "DMLINUX=1"
26:python "%DMLINUX_HOME%\main.py" %*
30:py -3 "%DMLINUX_HOME%\main.py" %*
```

第 13 行是项目根目录（`bin/` 的上一级），第 14 行才是给 `w2l/entry.py` 看的那个开关。

### 第 9 步：确认启动器不会污染你的 shell

启动器设了 `DMLINUX`，但跑完一次之后你的 shell 里不该多出这个变量。cmd 版用 `setlocal` 隔离，sh 版靠 `exec` 直接替换进程：

```bash
cd E:\1\NULL\Windows-to-Linux
PATH="$PATH:$PWD/bin" dmlinux --help > /dev/null && if [ -z "${DMLINUX:-}" ]; then echo "父 shell: DMLINUX 未设置（没漏回）"; else echo "父 shell: DMLINUX=[$DMLINUX]"; fi
```

预期输出：

```
父 shell: DMLINUX 未设置（没漏回）
```

### 第 10 步：知道这个模块什么时候求值

`entry_name()` 每次调用都重新读 `os.environ`，不是在导入时算一次存起来：

```bash
cd E:\1\NULL\Windows-to-Linux
python -c "import os;from w2l.entry import entry_name;print('导入后:',entry_name());os.environ['DMLINUX']='1';print('改环境后:',entry_name())"
```

预期输出：

```
导入后: python main.py
改环境后: dmlinux
```

这个设计让 `tests/test_launcher.py:134` 的 `test_entry_name_follows_env_flag` 可以用 `monkeypatch.setenv` / `monkeypatch.delenv` 直接测——不需要起子进程。

### 第 11 步：跑相关测试

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest tests/test_launcher.py 2>&1 | tail -1
```

预期输出：

```
10 passed in 4.00s
```

（耗时每次不同，核对器会把 `in 4.00s` 这类归一化后再比对。）

### 第 12 步：知道三个容易踩的点

**坑一：以为 `DMLINUX=0` 能关掉它。**

不能。`"0"` 是非空字符串，真值为真，`DMLINUX=0` 会**打开** `dmlinux` 模式。要关掉得设成空串或 unset 掉。

**坑二：以为它读的是命令行参数。**

它读环境变量。项目里没有 `--as=dmlinux` 这种选项，命令行参数的位置全留给指令自己用（`python main.py grep -n TODO src` 里的 `grep`、`-n`、`TODO`、`src` 都是 grep 的参数）。

**坑三：以为改了 `sys.argv[0]` 就能改名字。**

改不了。`entry_name()` 不看 `sys.argv[0]`，只读 `os.environ`。改 `argv[0]` 对这个模块没有任何影响。

### 第 13 步：确认整体没坏

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest 2>&1 | tail -1
```

预期输出：

```
180 passed in 5.00s
```

（耗时每次不同。）
