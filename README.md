# Windows-to-Linux

在 Windows 上用 Python 复刻常用 Linux 命令行能力，统一入口：

```
python main.py <指令> [参数]
```

当前实现：`grep`（GNU grep 风格子集）。后续指令按同一模式接入，主干代码不需要改动。

纯标准库实现，零第三方依赖，`git clone` 后直接可跑。

## 快速开始

```bash
python main.py                          # 列出可用指令
python main.py grep --help              # 查看 grep 用法
python main.py grep -rn "TODO" src      # 递归搜索并显示行号
python main.py grep -ril "error" .      # 递归列出含匹配的文件名
python main.py grep -cE "ERROR|FATAL" app.log
python main.py grep -oE "https?://\S+" notes.txt
```

## grep 能力清单

| 选项 | 含义 |
| --- | --- |
| `-i` | 忽略大小写 |
| `-v` | 反向匹配，输出不匹配的行 |
| `-n` | 显示行号 |
| `-r` | 递归搜索目录 |
| `-E` | 使用扩展正则 ERE（默认基本正则 BRE） |
| `-w` | 只匹配构成完整单词的片段 |
| `-c` | 只输出每个文件的匹配行数 |
| `-l` | 只输出含有匹配的文件名 |
| `-o` | 只输出匹配到的部分 |

行为细节对齐 GNU grep：

- **正则默认 BRE**：默认模式下 `+ ? | ( ) { }` 是字面量，`\+ \| \( \)` 才是元字符；加 `-E` 切换为扩展正则。
- **退出码**：`0` 有命中，`1` 无命中，`2` 出错（文件不存在等）。可直接用于 PowerShell/CI 判断。
- **文件编码自动判定**：UTF-8 → 系统编码 → GB18030 → Latin-1，GBK 源码文件也能正确搜出中文。
- **二进制文件**：不输出乱码内容，改为提示 `Binary file xxx matches`。
- **多文件前缀**：搜索多个文件或递归搜索时输出 `文件:行号:内容`。
- **标准输入**：不给文件路径时从管道读取。

## 目录结构

```
Windows-to-Linux/
├── main.py                  # 薄入口，转调 w2l.cli:main
├── w2l/
│   ├── cli.py               # 指令分发、帮助输出、异常与退出码处理
│   ├── registry.py          # 指令注册表 + @command 装饰器
│   ├── context.py           # 运行上下文（cwd / stdout / stderr / stdin）
│   ├── errors.py            # UsageError / CommandError
│   └── commands/
│       ├── __init__.py      # 自动导入子模块完成注册
│       └── grep.py          # grep 实现
├── tests/
│   ├── conftest.py
│   └── test_grep.py
├── pyproject.toml
└── .github/workflows/ci.yml
```

## 架构设计

四层，每层职责单一：

1. **入口层** `main.py`：只做 `sys.exit(main())`，不写任何逻辑。
2. **分发层** `w2l/cli.py`：查注册表 → 建解析器 → 建上下文 → 调处理器 → 把异常翻译成退出码。
3. **注册层** `w2l/registry.py`：`@command(name, summary, parser_factory)` 把处理函数登记进 `REGISTRY`。
4. **指令层** `w2l/commands/*.py`：每个指令一个模块，自带参数解析与业务逻辑，互不依赖。

关键设计点：

- **指令自动发现**：`commands/__init__.py` 用 `pkgutil.iter_modules` 导入全部子模块，新增指令文件即被注册，无需改分发层。
- **解析器工厂**：`parser_factory` 而不是共享解析器，保证每个指令的 `-h` 只显示自己的参数，不会互相污染短选项。
- **异常到退出码的映射集中在一处**：指令层只抛 `UsageError` / `CommandError`，退出码由 `cli.py` 统一决定。
- **上下文注入**：指令通过 `RunContext` 拿 cwd 与三个标准流，便于测试注入内存流，也方便以后加 `--json` 之类的输出通道。

## 如何新增一个指令

1. 新建 `w2l/commands/<名字>.py`。
2. 写 `build_parser()` 返回 `argparse.ArgumentParser`。
3. 写处理函数并用 `@command` 装饰：

```python
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

4. 文件放进 `w2l/commands/` 即自动生效，`python main.py ls` 可直接调用。
5. 在 `tests/test_<名字>.py` 补测试。

约定：处理函数返回 `0` 表示成功；命中类指令用 `1` 表示「无结果」；用法错误抛 `UsageError`（退出码 2）。

## 后续演进路线

**阶段一：补齐 grep**

- `--include` / `--exclude` 文件过滤规则
- `-A` / `-B` / `-C` 上下文行
- `-h` / `-H` 显式控制文件名前缀
- `--color=auto|always|never` 彩色高亮
- `--binary-files=without|with` 二进制策略

**阶段二：常用命令族**

`ls`、`cat`、`head`、`tail`、`wc`、`find`、`tree`、`du`、`cp`、`mv`、`rm`、`chmod`、`sed`（行内替换）、`awk-lite`（字段投影）。先做「Windows 用户最常抱怨缺失」的那一批。

**阶段三：工程化**

- **并行搜索**：大目录树用 `multiprocessing` 分片并行，串行版本在大仓上是明显瓶颈，这是性能优化的第一优先级。
- **配置化**：`.w2lrc` 放默认选项（如默认递归、默认忽略目录、默认编码）。
- **结构化输出**：`--json` 输出机器可读结果，便于和其他工具串联。
- **Windows 特性适配**：长路径（>260 字符）、UNC 路径、符号链接（`mklink`）、权限位语义。

**阶段四：分发**

- `pipx install` / `pip install -e .` 安装为 `w2l` 命令
- PyInstaller 打包成单文件 exe，免 Python 环境
- GitHub Releases 自动附带各平台构建产物

## 性能优化要点（按收益排序）

1. **并行遍历**：目录越大收益越明显，进程池按顶层子目录分片。
2. **二进制快速跳过**：已经做了头部 NUL 探测，避免全文解码。
3. **编码一次判定**：每个文件只探测一次，避免逐行重复判断。
4. **`mmap` + 正则扫描**：超大单文件时避免逐行 Python 循环开销。
5. **结果流式输出**：当前实现是流式的，不在内存里攒全部结果，大结果集不会撑爆内存。

## Git / GitHub 协作约定

- **分支模型**：`main` 保持可用，功能分支 `feat/<名字>`，修复分支 `fix/<名字>`，实验性 `spike/<名字>`。
- **提交信息**：Conventional Commits，例如 `feat(grep): 支持 -A/-B/-C 上下文行`、`fix(grep): 修正 GBK 文件编码判定`。
- **PR 要求**：一个 PR 只做一件事；描述里写清「改了什么 / 为什么 / 怎么验证」；CI 必须绿。
- **CI**（`.github/workflows/ci.yml`）：push 与 PR 触发，Python 3.10–3.14 矩阵跑 `pytest`。
- **版本与发布**：语义化版本，tag `v0.1.0` 对应一次可用的能力集，GitHub Release 附变更说明。

### 本地首次使用

```bash
cd Windows-to-Linux
git init -b main
git add .
git commit -m "feat(grep): 首个可用的 grep 实现，含分发骨架与测试"
git remote add origin <你的仓库地址>
git push -u origin main
```
