# pyproject.toml — 打包与入口点

`pyproject.toml` 是项目的打包描述，同时兼任 pytest 的配置文件。21 行，定义了包名、版本、Python 版本要求、控制台入口和要打包的子包。

## 为什么这么创建

**为什么用 `pyproject.toml` 而不是 `setup.py`。** `setup.py` 是要执行的 Python 代码，构建时会被执行，存在任意代码执行的风险；`pyproject.toml` 是声明式的，构建工具读它而不执行它。这是现在打包的标准做法。

**为什么显式列出 `packages`。**

```toml
[tool.setuptools]
packages = ["w2l", "w2l.commands"]
```

如果删掉这两行，setuptools 会做「扁平布局自动发现」，扫到项目根目录下的多个顶层目录（`w2l`、`tests`、`AI`、`teach`）就会直接报错——它无法判断哪个才是要发布的包。显式列出两个包，既避免了报错，也顺带保证了 `tests/` 和 `AI/` 不会被装进发行包。

注意 `w2l.commands` 单独列出来：它是 `w2l` 的子包，setuptools 不会自动把子包带上。

**为什么 `requires-python = ">=3.10"`。** 这个下限和 CI 的测试矩阵（3.10 / 3.11 / 3.12 / 3.13 / 3.14）对齐。源码里用到的 `list[str] | None` 这种联合类型标注，靠的是 `from __future__ import annotations`，在 3.10 上是安全的。

**为什么 `dependencies = []`。** 硬约束是零第三方依赖（`AGENTS.md` 第 3 节）。依赖列表为空，意味着一条 `pip install` 都不用跑，`git clone` 之后直接 `python main.py` 就能用。

**为什么 `[project.scripts]` 里写的是 `w2l.cli:main` 而不是 `main:main`。** 控制台脚本安装后是一个 `w2l` 可执行命令，它生成的包装代码是 `sys.exit(main())`。`w2l.cli:main` 返回的是 int，正好交给 `sys.exit` 当退出码，和 `python main.py` 的行为一致。如果指向 `main:main`，装出来的命令会走不到 `main.py` 里的 `sys.exit`。

**为什么 pytest 配置也放这里。** `pyproject.toml` 是目前唯一被普遍支持的集中配置位置（`pytest.ini` / `setup.cfg` 都在被淡化）。既然已经有这个文件，pytest 的配置就没必要再开一个。

## 这个文件是做什么

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "windows-to-linux"
version = "0.1.0"
description = "在 Windows 上提供类 Linux 命令行工具，统一入口 python main.py <指令> <参数>"
readme = "README.md"
requires-python = ">=3.10"
dependencies = []

[project.scripts]
w2l = "w2l.cli:main"

[tool.setuptools]
packages = ["w2l", "w2l.commands"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

两个块的分工：

| 块 | 谁在读 | 作用 |
|---|---|---|
| `[build-system]` / `[project]` / `[project.scripts]` / `[tool.setuptools]` | setuptools / pip | 打包与安装 |
| `[tool.pytest.ini_options]` | pytest | 测试发现范围与默认参数 |

`[tool.pytest.ini_options]` 的两项：

- `testpaths = ["tests"]`：不指定路径时，pytest 只收 `tests/` 下的用例。所以裸跑 `pytest` 不会去收集项目里别的 Python 文件。
- `addopts = "-q"`：默认安静模式。所以 `python -m pytest` 和 `python -m pytest -q` 输出一样。

不负责：依赖管理（没有依赖）、CI 触发（那在 `.github/workflows/ci.yml`）、代码风格检查（没有配 ruff / flake8）。

## 有什么用

- `pip install -e .` 之后可以用 `w2l` 命令，免去每次写 `python main.py`。
- `requires-python` 让 pip 在 Python 版本不够时直接拒绝安装，而不是装完运行时报语法错误。
- `packages` 显式声明，保证发行包里只有 `w2l/`，不会把 `tests/`、`AI/`、`teach/` 一起打包。
- `testpaths` 让「跑测试」永远是一条不带路径的命令，减少「漏跑某个目录」这类问题。

## 怎么用（过程教程）

### 第 1 步：看当前打包配置

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest
```

`addopts = "-q"` 生效，输出是安静模式。这一步同时证明 pytest 读到了 `pyproject.toml`（`testpaths` 让它只收 `tests/`）。

### 第 2 步：本地安装成 `w2l` 命令

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pip install -e .
```

这一步会创建 `build` / `*.egg-info` 之类的中间产物——都在 `.gitignore` 里，不会污染提交。

预期结尾类似：

```
Successfully installed windows-to-linux-0.1.0
```

然后：

```bash
cd E:\1\NULL\Windows-to-Linux
w2l --help
```

预期输出与 `python main.py --help` 一致：

```
用法: python main.py <指令> [参数]

可用指令:
  grep  搜索包含 PATTERN 的行（GNU grep 风格子集）

查看具体用法: python main.py <指令> --help
```

（提示文本是 `w2l/cli.py` 里写死的 `python main.py`，所以装成 `w2l` 之后提示里仍然写 `python main.py`。这是已知的不一致，要改的话改 `w2l/cli.py:_print_help` 里的字符串。）

### 第 3 步：卸载

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pip uninstall -y windows-to-linux
```

### 第 4 步：确认打包内容只有 w2l

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pip wheel . --no-deps -w dist
```

预期在 `dist/` 下生成一个 wheel（本机 setuptools 是 82.0.1，满足 `requires = ["setuptools>=68"]`）。用归档工具打开它，里面应该只有 `w2l/`（含 `w2l/commands/`）加上元数据，不应该有 `tests/`、`AI/`、`teach/`。`[tool.setuptools] packages` 的显式列表就是为了这个结果。

生成物在 `dist/`，已在 `.gitignore` 里，不会污染提交。

### 第 5 步：改版本号

版本号在这里改，不在别处：

```toml
[project]
version = "0.1.0"
```

`w2l/__init__.py` 里另有一份 `__version__ = "0.1.0"`，目前两处是手工同步的，没有自动关联。改的时候两处一起改，或者干脆只认 `pyproject.toml` 这一处。

### 第 6 步：给 pytest 单独加参数而不改配置文件

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -v
```

预期：详细模式，每个用例一行。命令行参数会覆盖 `addopts`，不影响配置文件本身。

### 第 7 步：如果以后要加开发依赖

现在没有 dev 依赖组。加的话建议用可选依赖，而不是塞进 `dependencies`：

```toml
[project.optional-dependencies]
dev = ["pytest>=8"]
```

装的时候：

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pip install -e ".[dev]"
```

这样 `dependencies = []` 的「零第三方运行时依赖」这个承诺还成立。目前 CI 的 `Install` 步骤没有做这件事，见 `11-github-actions-ci.yml-持续集成.md`。
