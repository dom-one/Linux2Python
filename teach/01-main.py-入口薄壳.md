# main.py — 入口薄壳

`main.py` 是整个项目的命令行入口，文件里只有一句实质代码：把 `w2l.cli.main()` 的返回值交给 `sys.exit`。

## 为什么这么创建

项目要同时满足两个入口形态：

- 用户手敲：`python main.py grep -n TODO .`
- 安装成命令：`pip install -e .` 之后直接敲 `w2l grep -n TODO .`

`pyproject.toml` 里的 `[project.scripts]` 写的是 `w2l = "w2l.cli:main"`，也就是说安装后的命令直接调 `w2l.cli:main`，**不经过 `main.py`**。如果把逻辑写进 `main.py`，装出来的 `w2l` 命令就找不到入口；所以 `main.py` 只能是薄壳，真实逻辑必须放在可被 `w2l.cli:main` 引用的地方。

另一层考虑是退出码。指令层与分发层统一用 `return int` 表达结果，而不是直接调 `sys.exit()`。只有进程入口才有权决定进程退出码，把 `sys.exit` 收到 `main.py` 这一个位置，单元测试里就能直接 `code = main(["grep", ...])` 拿到退出码而不结束测试进程——`tests/test_grep.py` 的 `test_cli_dispatch_returns_match_code` 正是这么做的。

反过来，如果 `main.py` 里塞了 argparse 定义、帮助文本、错误处理，改一个选项就要动入口文件，且 `w2l` 控制台脚本和 `main.py` 会走两套逻辑。

## 这个文件是做什么

职责只有一条：把命令行进程启动起来，并把 `w2l.cli:main` 的返回值变成进程退出码。

完整内容（13 行，含 docstring）：

```python
#!/usr/bin/env python
"""Windows-to-Linux 统一入口。

用法:
    python main.py <指令> [参数]
"""

import sys

from w2l.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

不负责：解析参数（`w2l/cli.py`）、查找指令（`w2l/registry.py`）、任何具体业务（`w2l/commands/*.py`）、错误提示（`w2l/errors.py` + `w2l/cli.py`）。

依赖谁：只依赖 `w2l.cli`。反过来 `w2l` 包内部没有任何模块 import `main.py`，所以包可以被独立安装使用。

## 有什么用

- 把「用户怎么敲命令」固定成一种形式：`python main.py <指令> [参数]`，所有指令共用一条心智模型。
- 统一退出码来源：所有退出码都由 `w2l/cli.py` 的 `main()` 决定，`main.py` 只负责把它交给操作系统。
- 让 `python main.py` 和安装后的 `w2l` 命令行为完全一致，因为两者最终调的是同一个 `main()`。

## 怎么用（过程教程）

### 第 1 步：跑起来看看

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py
```

预期输出：

```
用法: python main.py <指令> [参数]

可用指令:
  grep  搜索包含 PATTERN 的行（GNU grep 风格子集）

查看具体用法: python main.py <指令> --help
```

退出码是 1（`w2l/cli.py` 里 `if not argv:` 分支 `return 1`）。在 PowerShell 里可以这样看：

```powershell
cd E:\1\NULL\Windows-to-Linux
python main.py
$LASTEXITCODE
```

### 第 2 步：看退出码怎么传出来

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep "不存在的字符串" README.md; echo "退出码=$?"
```

预期输出：无内容，`退出码=1`（有搜索目标但没命中）。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep "TODO" README.md; echo "退出码=$?"
```

预期输出：`退出码=0`（有命中）。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep "x" 不存在的文件.txt; echo "退出码=$?"
```

预期输出：stderr 上 `错误: 不存在的文件.txt: ...`，`退出码=2`（运行错误）。

### 第 3 步：在 Python 里直接调，不用起进程

因为 `main()` 返回 int 而不自己退出，测试和脚本都能直接调：

```python
from w2l.cli import main

code = main(["grep", "-n", "def", "w2l/cli.py"])
print("退出码:", code)
```

在项目根目录执行：

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q tests/test_grep.py::test_cli_dispatch_returns_match_code
```

预期：测试通过。这条用例内部就是 `code = main(["grep", "ERROR", str(sample_tree / "app.log")])`，并断言 `code == 0`。

### 第 4 步：确认 `if __name__ == "__main__"` 的作用

这一行让 `main.py` 被 `import` 时不自动执行退出逻辑。所以下面这样 import 是安全的：

```python
import main  # 不会跑命令，也不会结束进程
print(main.main(["--help"]))
```

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q
```

预期：31 个用例全部通过。如果去掉 `if __name__ == "__main__":` 这层保护，任何 import 这个文件的代码都会在导入瞬间执行命令并 `sys.exit`，把导入方的进程直接结束掉。

### 第 5 步：装成命令行命令（可选）

`pyproject.toml` 声明了控制台入口：

```toml
[project.scripts]
w2l = "w2l.cli:main"
```

在项目根目录执行：

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pip install -e .
w2l --help
```

预期：输出与 `python main.py --help` 相同（`w2l --help` 走的是 `w2l/cli.py` 的 `argv[0] in ("-h", "--help", "help")` 分支）。

若不想污染环境，用 `pipx install .` 装到独立目录，或者跳过这一步——项目本身零依赖，不装也能用。
