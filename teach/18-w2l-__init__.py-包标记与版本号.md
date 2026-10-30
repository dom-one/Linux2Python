# w2l/__init__.py — 包标记与版本号

`w2l/__init__.py` 只有 3 行，是整个项目里最短的一个文件。它做两件事：把 `w2l/` 声明成一个正经的 Python 包，以及放一个 `__version__` 常量。

## 为什么这么创建

这个文件里没有任何业务逻辑，所以创建它的理由只有「结构性的」和「元数据的」两类。

**第一类理由：让 `w2l` 成为一个常规包，而不是命名空间包。**

Python 3.3 之后，目录里不放 `__init__.py` 也能 import，这种目录叫命名空间包（PEP 420）。两种写法在 `import w2l` 时都不报错，但行为差别很大。实测两种结构的差别：

```
# 有 __init__.py
file= '...\w2l\__init__.py'
path_type= list
version= 0.1.0

# 没有 __init__.py
file= None
path_type= _NamespacePath
version= NO_ATTR
```

命名空间包没有 `__file__`，`__path__` 是 `_NamespacePath` 这种特殊类型，而且**没有 `__version__`**——因为根本没有 `__init__.py` 那个文件来承载它。项目要对外暴露版本号、要让 `w2l.__file__` 指向真实文件，就需要一个常规包。

命名空间包还有个更隐蔽的坑：它会把**路径上所有**叫 `w2l` 的目录合并成一个包。如果用户机器上碰巧有另一个 `w2l` 目录在 `sys.path` 上，两边的文件会混在一起。常规包不会——它只认一个目录。

**第二类理由：版本号要有一个对外的落点。**

`pyproject.toml` 里的 `version = "0.1.0"` 是给打包工具（setuptools / pip）看的，`w2l/__init__.py` 里的 `__version__` 是给运行时的 Python 代码看的。两者用途不同，所以需要分开存在。

代价是**同一个版本号写了两遍**，而且没有任何自动关联。`teach/09-pyproject.toml-打包与入口点.md` 里也记了这一点：改的时候两处一起改。

## 这个文件是做什么

完整实现：

```python
"""Windows-to-Linux：在 Windows 上提供类 Linux 命令行工具。"""

__version__ = "0.1.0"
```

- 第一行是模块文档字符串，会成为 `w2l.__doc__`。
- 第二行定义 `__version__`，`w2l.__version__` 取到的就是 `"0.1.0"`。
- 没有 `__all__`，也没有任何 `import`。

不负责：指令注册（在 `w2l/registry.py`）、指令自动发现（在 `w2l/commands/__init__.py`）、命令行分发（在 `w2l/cli.py`）。

**这个文件和 `w2l/commands/__init__.py` 完全不是一回事**，尽管文件名一样：

| | `w2l/__init__.py` | `w2l/commands/__init__.py` |
|---|---|---|
| 行数 | 3 | 12 |
| 有逻辑吗 | 没有 | 有 `load_all()` |
| 谁调用它 | Python 导入机制自动执行 | `w2l/registry.py` 的 `load_commands()` 显式调用 |
| 删了会怎样 | `w2l` 退化成命名空间包，`__version__` 消失 | 所有指令都不再自动注册，CLI 找不到任何指令 |

## 有什么用

**1. 提供 `w2l.__version__`。**

这是它对外唯一的实际用途。目前项目代码里**没有任何地方读取** `__version__`（全仓库只有定义那一行）——CLI 也没有 `--version` 选项：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py --version
```

预期输出（退出码 2）：

```
未知指令: --version
可用指令: grep
```

所以 `__version__` 现在是「备着但还没接上」的状态。想加 `--version` 支持，`w2l/cli.py` 的 `main()` 里加一个判断，读 `w2l.__version__` 就行。

**2. 锁定包结构，防止退化成命名空间包。**

有了这个文件，`w2l.__path__` 是一个普通的 `list`，`w2l.__file__` 指向真实路径，打包时 `w2l/__init__.py` 也会被装进 wheel。实测打包产物：

```
w2l/__init__.py
w2l/cli.py
w2l/commands/__init__.py
w2l/commands/grep.py
w2l/context.py
w2l/errors.py
w2l/registry.py
```

**3. 顺带提供包的文档字符串。**

`w2l.__doc__` 读出来是「Windows-to-Linux：在 Windows 上提供类 Linux 命令行工具。」，是 `help(w2l)` 显示的第一段说明。

## 怎么用（过程教程）

下面所有命令都实测过，输出与文档一致。用 `AI/脚本/_t12_verify_teach.py` 可以自动核对本篇的命令。

### 第 1 步：确认它确实是个常规包

```bash
cd E:\1\NULL\Windows-to-Linux
python -c "import w2l;print(w2l.__file__);print(type(w2l.__path__).__name__);print(w2l.__version__)"
```

预期输出：

```
E:\1\NULL\Windows-to-Linux\w2l\__init__.py
list
0.1.0
```

三行分别对应「有真实文件」「`__path__` 是普通 list（不是 `_NamespacePath`）」「版本号在」。

### 第 2 步：确认导入 `w2l` 没有任何副作用

```bash
cd E:\1\NULL\Windows-to-Linux
python -c "import w2l;from w2l.registry import REGISTRY;print(dict(REGISTRY))"
```

预期输出：

```
{}
```

注册表是空的。说明 `import w2l` 只执行了那 3 行，不会顺带把指令都加载进来——指令注册必须靠 `w2l/registry.py` 的 `load_commands()` 显式触发（见 `teach/03-w2l-registry.py-指令注册表.md`）。

再进一步，导入 `w2l.cli` 也不会注册任何指令：

```bash
cd E:\1\NULL\Windows-to-Linux
python -c "import w2l.cli;from w2l.registry import REGISTRY;print(len(REGISTRY))"
```

预期输出：

```
0
```

### 第 3 步：看这个包对外暴露了什么

```bash
cd E:\1\NULL\Windows-to-Linux
python -c "import w2l;print([n for n in dir(w2l) if not n.startswith('_')])"
```

预期输出：

```
[]
```

空列表。`w2l` 顶层没有任何公开名字——`__version__` 带下划线，被这个过滤条件排掉了。这正是「3 行文件不做事」的直接体现。

### 第 4 步：看包的文档字符串

```bash
cd E:\1\NULL\Windows-to-Linux
python -c "import w2l;print(w2l.__doc__)"
```

预期输出：

```
Windows-to-Linux：在 Windows 上提供类 Linux 命令行工具。
```

### 第 5 步：确认子模块是导入后才挂上去的

```bash
cd E:\1\NULL\Windows-to-Linux
python -c "import w2l,w2l.commands;print(w2l.commands.__name__)"
```

预期输出：

```
w2l.commands
```

`w2l.commands` 是一个子包，`import w2l.commands` 之后它成为 `w2l` 的属性。单独 `import w2l` 时 `dir(w2l)` 里没有 `commands`——Python 不会自动递归导入子包，需要谁用谁显式导入。

### 第 6 步：搞清「删掉它会怎样」

这是最容易想当然的地方。做个对照实验：造一个没有 `__init__.py` 的包，再造一个有的，对比行为。

```bash
cd E:\1\NULL\Windows-to-Linux
python -c "import os,shutil,sys,tempfile;t=tempfile.mkdtemp();os.makedirs(os.path.join(t,'nspkg'));open(os.path.join(t,'nspkg','m.py'),'w').write('V=1');sys.path.insert(0,t);import nspkg;print(nspkg.__file__);print(type(nspkg.__path__).__name__);print(getattr(nspkg,'__version__','NO_ATTR'));shutil.rmtree(t,ignore_errors=True)"
```

预期输出：

```
None
_NamespacePath
NO_ATTR
```

没有 `__init__.py` 就没有 `__file__`，`__path__` 变成 `_NamespacePath`，连 `__version__` 都不存在。

再看有 `__init__.py` 的对照组：

```bash
cd E:\1\NULL\Windows-to-Linux
python -c "import os,shutil,sys,tempfile;t=tempfile.mkdtemp();os.makedirs(os.path.join(t,'regpkg'));open(os.path.join(t,'regpkg','__init__.py'),'w').write('__version__=\"0.1.0\"');sys.path.insert(0,t);import regpkg;print(os.path.basename(regpkg.__file__));print(type(regpkg.__path__).__name__);print(regpkg.__version__);shutil.rmtree(t,ignore_errors=True)"
```

预期输出：

```
__init__.py
list
0.1.0
```

对照着看，本项目这个文件存在的价值就清楚了。

### 第 7 步：用项目自带的 grep 找版本号的两处位置

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -n "version = " pyproject.toml
```

预期输出：

```
7:version = "0.1.0"
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -n "__version__" w2l/__init__.py
```

预期输出：

```
3:__version__ = "0.1.0"
```

一处 `7:`，一处 `3:`。改版本号时这两行都要动。

### 第 8 步：核对两处是否一致

```bash
cd E:\1\NULL\Windows-to-Linux
python -c "import pathlib;repl=pathlib.Path('w2l/__init__.py').read_text(encoding='utf-8');pj=pathlib.Path('pyproject.toml').read_text(encoding='utf-8');a=[l for l in pj.splitlines() if l.startswith('version')][0];b=[l for l in repl.splitlines() if l.startswith('__version__')][0];print(a);print(b);print('一致' if '0.1.0' in a and '0.1.0' in b else '不一致')"
```

预期输出：

```
version = "0.1.0"
__version__ = "0.1.0"
一致
```

这段只做读取、不改文件，可以放心跑。

### 第 9 步：知道三个容易踩的点

**坑一：以为 `import w2l` 会把指令都加载好。**

不会。`import w2l` 后 `REGISTRY` 是空的，`python main.py` 能用是因为 `w2l/cli.py` 的 `main()` 调了 `load_commands()`。

**坑二：以为 `__version__` 能通过命令行看到。**

目前不能，`python main.py --version` 报「未知指令」并返回退出码 2。`__version__` 只能通过 Python 代码读到。

**坑三：以为版本号只有一处。**

有两处，`pyproject.toml` 和 `w2l/__init__.py`，手工同步。现在项目里没有任何代码读 `__version__`，所以改错也不会立刻报错——这正是它容易漏改的原因。

### 第 10 步：确认整体没坏

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q
```

预期：`36 passed`。
