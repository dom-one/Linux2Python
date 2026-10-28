# .gitignore — 版本控制边界

`.gitignore` 决定哪些文件不进 Git 仓库。当前 12 条规则，作用是让 `git status` 只显示真正需要评审的改动。

## 为什么这么创建

这个项目要同时做三件事：跑测试、打包、给两个 cron 任务提交改动。三件事都会在仓库里产生**本地垃圾**：

- 跑测试 → `__pycache__/`、`.pytest_cache/`
- 打包 → `*.egg-info/`、`build/`、`dist/`
- 建虚拟环境 → `.venv/`、`venv/`

这些文件的特点是：**每次都重新生成、内容随机器变化、不含任何人工劳动**。提交它们只会让每次 diff 多出几十行二进制噪音，还会在不同机器上产生无意义的冲突。

`.gitignore` 是按「目录」和「通配符」组织的，不是按「谁来生成」组织的。这条规则决定了它同时承担了两个职责：

1. **挡住生成物**：`__pycache__/`、`*.py[cod]`、`.pytest_cache/`、`*.egg-info/`、`build/`、`dist/`。
2. **挡住本机私有物**：`.venv/`、`venv/`、`.env`、`.idea/`、`.vscode/`。

第 2 类里 `.env` 最要紧——它是本地密钥文件，一旦提交进 Git 历史，后果是永久的，因为 Git 历史不能靠「再提交一次」抹掉。

**为什么用 `*.py[cod]` 而不是 `*.pyc`。** `[cod]` 是字符集写法，一个规则覆盖 `.pyc`、`.pyo`、`.pyd` 三种后缀。写全三种要多两行，且以后 Python 加新后缀又要补。

**为什么 `__pycache__/` 写目录而不是 `*.pyc`。** Python 3.2 以后缓存是按目录组织的，一个 `__pycache__` 目录里可能有几十个 `.pyc`。只忽略文件的话，`git status --ignored` 里会刷出一长串；忽略目录更干净。

**为什么 `.pytest_cache/` 也要写。** pytest 自己会在 `.pytest_cache/` 里放一个 `.gitignore`（内容是 `*`），理论上光靠它就够。但显式写一行更保险：pytest 版本升级或缓存目录结构变化时不至于突然冒出几百个未跟踪文件。

## 这个文件是做什么

完整内容：

```
__pycache__/
*.py[cod]
*.egg-info/
build/
dist/
.pytest_cache/
.venv/
venv/
.env
.idea/
.vscode/
AI/锁/
```

12 条规则，全部是「忽略」语义，没有例外项（没有 `!` 开头的反选规则）。

注意它**没有**忽略这些：`.git/`（Git 自己就不跟踪）、`teach/`（教程要提交）、`AI/` 里除 `AI/锁/` 之外的内容（脚本、进度、任务 prompt 都要提交）、`AGENTS.md`、`cron.md`。

不负责：决定哪些文件**应该**被跟踪。`.gitignore` 只管「不要」，不管「要」。要提交什么由 `AGENTS.md` 第 2 节的目录分工表和第 6 节的提交纪律决定。

## 有什么用

- `git status` 干净，diff 里只有真正的代码改动。
- 换一台机器 clone 之后，`git status` 不会因为「多了几个 `.pyc`」而显示一堆待处理项。
- 避免把 `.env`、虚拟环境、缓存误提交。
- 让 `AGENTS.md` 第 6 节「提交前 `git status` 里只应有本次改动」这条纪律可以真正执行——如果缓存没被忽略，这条纪律根本没法遵守。

## 怎么用（过程教程）

### 第 1 步：看当前哪些被忽略了

```bash
cd E:\1\NULL\Windows-to-Linux
git status --ignored --short
```

预期输出：

```
?? teach/
!! .pytest_cache/
!! tests/__pycache__/
!! w2l/__pycache__/
!! w2l/commands/__pycache__/
```

- `??` = 未跟踪且没被忽略（`teach/` 是还没提交的教程目录）。
- `!!` = 被忽略，不会出现在提交里。

### 第 2 步：查某个文件为什么被忽略

```bash
cd E:\1\NULL\Windows-to-Linux
git check-ignore -v .pytest_cache/v/cache/nodeids w2l/__pycache__/cli.cpython-314.pyc
```

预期输出：

```
.gitignore:6:.pytest_cache/	.pytest_cache/v/cache/nodeids
.gitignore:1:__pycache__/	w2l/__pycache__/cli.cpython-314.pyc
```

格式是「命中的规则:行号 → 目标路径」，能直接定位是哪一行规则生效的。

### 第 3 步：验证缓存确实不会进提交

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q
git status --short
```

跑完测试会新生成 `.pytest_cache/` 和 `__pycache__/`，但 `git status --short` 里不会出现它们。

### 第 4 步：加一条新规则

比如以后要加 `*.log`（日志不进仓库），在 `.gitignore` 末尾追加：

```
*.log
```

然后验证：

```bash
cd E:\1\NULL\Windows-to-Linux
git check-ignore -v some.log
```

预期：`.gitignore:13:*.log	some.log`（行号随文件长度变化）。

### 第 5 步：知道 `.gitignore` 管不了已跟踪的文件

这是最容易踩的坑：`.gitignore` **只对未被跟踪的文件生效**。一旦某个文件被 `git add` 过，之后再往 `.gitignore` 里加规则，它依然会继续被跟踪。

典型场景：先提交了 `.pytest_cache/`，后来才加忽略规则。这时 `git status` 还是显示它要改。

处理办法是把它从索引里移除但保留工作区文件：

```bash
cd E:\1\NULL\Windows-to-Linux
git rm --cached .pytest_cache/v/cache/nodeids
git commit -m "chore: 停止跟踪 pytest 缓存"
```

`--cached` 只动索引，不删工作区文件。当前仓库没有这个问题（`git ls-files` 里没有缓存文件），列在这里是为了以后遇到时知道怎么办。

### 第 6 步：判断一个文件该不该被忽略

按 `AGENTS.md` 第 2 节的分工表：

| 路径 | 该不该进 Git |
|---|---|
| `w2l/`、`tests/`、`teach/`、`README.md`、`AGENTS.md` | 该进 |
| `AI/`（脚本、进度、任务 prompt） | 该进——它们是任务状态，不是本机垃圾 |
| `cron.md` | 该进 |
| `AI/锁/` | 不该进——锁文件是运行时状态。`.gitignore` 第 12 行已经把它挡住了 |
| `__pycache__/`、`.pytest_cache/`、`dist/` 等 | 不该进 |
| `.env` | 绝对不该进 |

`AI/锁/` 这条值得留意：锁文件是 `AI/脚本/_t10_lock.py` 在 `acquire` 时写的 `AI/锁/git.lock`，内容是 `owner` / `acquired_ts` / `released_ts`。它是运行时状态，提交进去会让每个 tick 都产生一次无意义 diff。当前 `.gitignore` 最后一行 `AI/锁/` 就是为此加的。

确认哪些文件已经在版本控制里：

```bash
cd E:\1\NULL\Windows-to-Linux
git ls-files
```

预期列出现在仓库里的全部文件：`.github/workflows/ci.yml`、`.gitignore`、`AGENTS.md`、`AI/` 下的四个文件和两个脚本、`README.md`、`cron.md`、`main.py`、`pyproject.toml`、`tests/` 两个文件、`w2l/` 下的 7 个文件。缓存、虚拟环境和 `AI/锁/` 一个都不在里面——这正是 `.gitignore` 在起作用。
