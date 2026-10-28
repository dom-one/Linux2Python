# .github/workflows/ci.yml — 持续集成

`.github/workflows/ci.yml` 是 GitHub Actions 的工作流定义：在 Windows 上跑 5 个 Python 版本的测试。28 行，一个 job。

## 为什么这么创建

**为什么 `runs-on: windows-latest` 而不是 `ubuntu-latest`。** 这个项目存在的理由就是「在 Windows 上提供类 Linux 命令」。它要解决的很多问题——控制台代码页是 GBK、路径分隔符是 `\`、`SetConsoleOutputCP(65001)` 的行为——在 Linux 上根本不会发生。在 Linux 上跑测试等于测了一个不存在的环境。

**为什么用矩阵跑 5 个 Python 版本。** `pyproject.toml` 里写的是 `requires-python = ">=3.10"`，矩阵覆盖 3.10 / 3.11 / 3.12 / 3.13 / 3.14，正好对应声明的支持范围。理由不是「版本多显得严谨」，而是这个项目里有几处行为确实跟版本相关：

- `re` 模块的正则方言在版本间有过调整，`_translate_bre` 生成的模式在不同版本上的解析结果可能不同。
- `argparse` 的错误消息格式、帮助文本换行方式在版本间会变，而这些输出正是测试断言的对象。
- `pathlib` 的行为在新版本里有细节调整。

跑矩阵的成本很低（GitHub 托管 runner 免费），但能挡住一类「本地 3.14 能跑、用户 3.10 跑不了」的问题。

**为什么 `fail-fast: false`。** 默认是 `fail-fast: true`，某个版本失败就取消其余还在跑的 job。设成 `false` 是为了让一次 push 能看到**全部**版本的结果——如果 3.10 挂了，你同时想知道 3.14 是不是也挂了。对一个支持 5 个版本的项目，这个信息是有用的。

**为什么 CI 不安装项目。** 步骤里没有 `pip install -e .`。因为 `tests/conftest.py` 在导入前把项目根目录塞进了 `sys.path`：

```python
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

所以 CI 里不需要安装包就能 `import w2l`。这让 CI 的安装步骤极短，也避免了「装了 editable 包但装坏」的失败模式。

**为什么只有 push / PR 到 main 才触发。** 其它分支的 push 不跑 CI，避免每个小提交都烧一遍矩阵。要在 PR 上跑，靠的是 `pull_request` 触发条件——PR 指向 main 就会触发。

## 这个文件是做什么

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: windows-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13", "3.14"]

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install
        run: python -m pip install --upgrade pip

      - name: Test
        run: python -m pytest -q
```

四个步骤：检出代码 → 装指定版本的 Python → 升级 pip → 跑测试。

`python -m pytest -q` 而不是 `pytest -q`：前者保证用的是「当前这个 Python」的解释器去跑 pytest，不会因为 PATH 上有另一个 Python 的 pytest 而串版本。

不负责：代码风格检查（没有 lint 步骤）、打包验证（没有 build 步骤）、发布（没有 release 流程）。

## 有什么用

- push 到 main 或开 PR 时自动验证：31 个测试 × 5 个 Python 版本。
- 挡住「本机环境能跑、别人环境跑不了」这类问题。
- 给 PR 一个客观的通过/不通过信号，不用靠人肉点按钮。
- 版本支持范围写在配置里，和 `pyproject.toml` 的 `requires-python` 对照着看就知道覆盖全没。

## 怎么用（过程教程）

### 第 1 步：本地复现 CI 做的事

CI 的 Test 步骤就是一条命令：

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q
```

预期：

```
...............................                                          [100%]
36 passed in 0.15s
```

本机是 Python 3.14.0 / pytest 9.0.2，对应矩阵里的 3.14。其他版本在本地复现的办法是分别装 3.10～3.13 后各跑一次。

### 第 2 步：确认 workflow 文件被 GitHub 识别

```bash
cd E:\1\NULL\Windows-to-Linux
git ls-files .github
```

预期输出：

```
.github/workflows/ci.yml
```

文件必须被 Git 跟踪，GitHub 才会在 `.github/workflows/` 下发现它。目录名是 `.github`（不是 `github`），`workflows` 也是复数。

### 第 3 步：在 GitHub 上看结果

推上去之后，在仓库页面点 **Actions** 标签，左侧选 **CI**，能看到 5 个 job（每个 Python 版本一个）。任何一个红了，PR 页面也会显示红色状态。

### 第 4 步：加一个新 Python 版本

改矩阵那一行：

```yaml
        python-version: ["3.10", "3.11", "3.12", "3.13", "3.14", "3.15"]
```

同时把 `pyproject.toml` 的 `requires-python` 一起改，否则声明的支持范围和实际测出来的会不一致。

### 第 5 步：注意当前 workflow 的两个薄弱点

**一、`Install` 步骤没有装 pytest。**

```yaml
      - name: Install
        run: python -m pip install --upgrade pip
```

这一步只升级了 pip，没有 `pip install pytest`。`python -m pytest` 能不能跑，取决于 runner 镜像里有没有预装 pytest。如果 runner 镜像不带 pytest，这个步骤会以 `No module named pytest` 失败。

修法（两种选一）：

```yaml
      - name: Install
        run: |
          python -m pip install --upgrade pip
          python -m pip install pytest
```

或者在 `pyproject.toml` 里加可选依赖组，然后 `python -m pip install -e ".[dev]"`。

**二、没有 lint / 格式检查步骤。**

`pyproject.toml` 里也没有 ruff / flake8 的配置，所以风格问题目前全靠人工。

### 第 6 步：CI 失败时先看什么

1. 看是哪个 Python 版本挂的——如果只有一个版本挂，多半是版本兼容问题；如果全挂，多半是代码本身坏了。
2. 点进失败 job 看 Test 步骤的完整输出，pytest 会打印失败用例的断言差异。
3. 本地按同样的 Python 版本复现：装对应版本后 `python -m pytest -q`。
4. 本地跑不出来不要写「已验证」——`AGENTS.md` 第 5 节的原话是「测试跑不起来就是没验证」。

### 第 7 步：PR 的要求

`README.md` 的「Git / GitHub 协作约定」一节写明：PR 只做一件事、描述里写清「改了什么 / 为什么 / 怎么验证」、CI 必须绿。对应到 `AGENTS.md` 第 6 节：一次提交一件事，消息用 Conventional Commits 格式，例如 `feat(ls): 实现 ls 指令`。
