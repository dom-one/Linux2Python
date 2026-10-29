# AGENTS.md · 项目守则

`AGENTS.md` 是仓库根目录的守则文件。69 行，7 个小节，定死「文件放哪、代码怎么写、测试怎么跑、提交怎么发」。`teach/` 目录里有 30 处写着「`AGENTS.md` 第 N 节」，但这份文件本身一直没被单独讲过——本篇补上。

## 为什么这么创建

**为什么需要一份能被机器读的守则。** 这个仓库有三种身份往同一棵 `main` 上提交：人手动改代码、开发任务的 cron tick、教程任务的 cron tick。cron tick 每次触发都是全新会话，没有上一次的记忆，约束只能落在文件里、靠每轮重新读一遍生效。

**为什么守则分三层，不合并成一份。** 同一台机器上实际存在三份 `AGENTS.md`，作用域各不相同：

| 文件 | 行数 | 管什么 |
|---|---|---|
| `E:\1\NULL\AGENTS.md` | 69 | 整个工作区：回复风格、skill 加载、后台命令禁令 |
| `AGENTS.md`（本篇讲的） | 69 | 本项目的工程约定：目录、硬约束、测试、提交 |
| `AI/AGENTS.md` | 87 | 两个 cron tick 的执行细则：取锁、提交纪律、进度格式 |

`AI/AGENTS.md` 第 7 节把「不动 `E:\1\NULL\AGENTS.md`」列为硬红线。三层的分工是：工作区守则管「怎么工作」，项目守则管「这个仓库的代码长什么样」，cron 细则管「自动任务怎么跑」。名字完全一样、层级完全不同，这是这块最容易搞混的地方。

**为什么只写 69 行。** 守则是契约，不是教程。它得能被 AI 每次会话整份读进上下文，也得能在人改代码之前一眼扫完。所以里面只写「必须这样」，不写「为什么这样」——「为什么」的部分在 `teach/` 里。代价很明确：只读守则能知道规矩，但不知道理由；想知道理由就得来读 `teach/`。

**为什么硬约束写成祈使句，不留商量余地。** 硬约束是能被检查的，不是能被权衡的。第 3 节第一条写的是「源码零第三方依赖。要加依赖先问」——「先问」意味着这是一个需要人点头的例外，不是可以自行判断的灰色地带。同理第 5 节的「全绿才允许提交」，它是提交前的判据，不是建议。

**为什么第 7 节只列任务、不写细节。** 两个 cron 任务的时间表和 prompt 真相源列在项目守则里，是为了让任何读这份文件的人都知道「这个仓库有自动任务在跑」。任务怎么取锁、怎么写 tick 日志，属于执行细则，放在 `AI/AGENTS.md`（见 `teach/16-...`）。项目守则只做索引，不抢细则的位置。

## 这个文件是做什么

7 个小节，逐个说清：

| 小节 | 起始行 | 管什么 |
|---|---|---|
| 1. 项目是什么 | 3 | 定位、入口 `python main.py`、纯标准库、Python 3.10+ |
| 2. 目录分工 | 13 | 6 个路径分别放什么、写入方是谁 |
| 3. 硬约束 | 26 | 7 条不可协商项 |
| 4. 加一个指令的步骤 | 36 | 6 步固定流程 |
| 5. 测试 | 45 | 跑什么命令、什么算通过 |
| 6. 提交 | 53 | 4 条提交纪律 |
| 7. 定时任务 | 60 | 两个 cron 任务的时间、职责、prompt 真相源 |

### 守则第 2 节：目录分工

6 行表格，第 3 列「写入方」是这张表的关键——它同时划出了人和自动任务的分界：

| 路径 | 放什么 | 写入方 |
|---|---|---|
| `w2l/` | 源码 | 人和 AI |
| `tests/` | pytest 测试 | 人和 AI |
| `teach/` | 逐文件教程 | 人和 AI |
| `AI/` | 脚本、中间产物、tick 进度、教程任务的 prompt | AI |
| `cron.md` | 开发任务的定时 prompt | AI |
| `README.md` | 项目说明、路线、用法 | 人和 AI |

注意 `AI/` 和 `cron.md` 的写入方只有 AI：这两个目录里装的是自动任务的运行状态和配置，人手工改它们没有意义，改了下个 tick 也会被覆盖。

### 守则第 3 节：硬约束

7 条，每条都能对上源码里的一处事实：

- 源码零第三方依赖。要加依赖先问。
- 一个新指令 = `w2l/commands/<名字>.py` 一个文件 + `tests/test_<名字>.py` 一个文件，主干不动。
- 新指令必须提供 `build_parser()` 和一个用 `@command` 装饰的处理函数。
- 退出码：`0` 成功，`1` 无结果（命中类指令），`2` 用法或运行错误。
- 输出统一 UTF-8。Windows 控制台靠 `SetConsoleOutputCP(65001)` 保证中文不乱码。
- 文件读写走 Python 脚本，不写内联解释器、不写 heredoc、不用 PowerShell 文件操作命令。
- 正则默认 BRE，与 GNU grep 一致；要 ERE 就加 `-E`。

前两条对应 `w2l/commands/__init__.py` 的 `pkgutil.iter_modules` 自动发现机制：新增指令只要放进那个目录就会被注册，`w2l/cli.py`、`w2l/registry.py`、`main.py` 都不用动，所以「主干不动」是能被机制保证的，不是靠自觉。第五条对应 `w2l/cli.py:50` 的 `kernel32.SetConsoleOutputCP(65001)`。

### 守则第 6 节：提交

4 条纪律：

- 消息格式：Conventional Commits，例如 `feat(ls): 实现 ls 指令`、`fix(grep): 修正 GBK 编码判定`。
- 一次提交一件事。
- 提交前 `git status` 里只应有本次改动。
- 提交信息 UTF-8。

### 守则第 7 节：定时任务

2 行表格：

| 任务 | 触发时间 | 干什么 | prompt 真相源 |
|---|---|---|---|
| 开发 | 每天 02:00 | 补 Linux 常用命令 | `cron.md` |
| 教程 | 每天 04:00 | 补 `teach/` 教程 | `AI/cron-教程任务.md` |

两个任务相隔 2 小时，不并发；执行细则（取锁、活动窗口、进度追加格式）在 `AI/AGENTS.md`。

不负责：讲某段代码怎么实现（那是 `teach/` 里 01～16 的职责）、对外说明与路线（`README.md`，见 `teach/12-...`）、自动任务的执行细则（`AI/AGENTS.md`，见 `teach/15-...`、`teach/16-...`）、上级工作区的通用约定（`E:\1\NULL\AGENTS.md`）。

## 有什么用

- **改代码前知道边界。** 该往哪个目录写、退出码怎么给、提交信息什么格式，全在 69 行里，不用问人。
- **给 AI 当上下文契约。** 两个 cron prompt 的第 0 步都是「读 `AGENTS.md`、`AI/AGENTS.md`、进度文件」。这份文件就是每轮自动任务开工前读到的工程约定。
- **给读者当索引。** `teach/` 里 30 处引用按小节分布是：第 2 节 6 处、第 3 节 6 处、第 4 节 1 处、第 5 节 8 处、第 6 节 9 处，第 1 节和第 7 节 0 处。引用最密的是「目录分工」「硬约束」「测试」「提交」——正好是动手改代码时最需要确认的四件事。
- **当判据用，不是当参考用。** 「全绿才允许提交」「一次提交一件事」「`git status` 里只应有本次改动」，都是可以直接对照检查的判据。

## 怎么用（过程教程）

### 第 1 步：先确认你在读哪一层守则

三份同名文件，先按路径分清：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -c "" AGENTS.md
python main.py grep -c "" AI/AGENTS.md
```

预期：

```
69
87
```

再确认上级那份在、且内容不同：

```bash
python main.py grep -n "^# " "E:/1/NULL/AGENTS.md"
```

预期第一行是 `# 本工作区使用约定`。这是工作区层守则，与本项目无关，`AI/AGENTS.md` 第 7 节明令不许改。

### 第 2 步：把 7 条硬约束拉出来逐条读

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -n "^- " AGENTS.md
```

预期输出 11 行——第 3 节的 7 条硬约束，加上第 6 节的 4 条提交纪律：

```
28:- 源码零第三方依赖。要加依赖先问。
29:- 一个新指令 = `w2l/commands/<名字>.py` 一个文件 + `tests/test_<名字>.py` 一个文件，主干不动。
30:- 新指令必须提供 `build_parser()` 和一个用 `@command` 装饰的处理函数。
31:- 退出码：`0` 成功，`1` 无结果（命中类指令），`2` 用法或运行错误。
32:- 输出统一 UTF-8。Windows 控制台靠 `SetConsoleOutputCP(65001)` 保证中文不乱码。
33:- 文件读写走 Python 脚本，不写内联解释器、不写 heredoc、不用 PowerShell 文件操作命令。
34:- 正则默认 BRE，与 GNU grep 一致；要 ERE 就加 `-E`。
55:- 消息格式：Conventional Commits，例如 `feat(ls): 实现 ls 指令`、`fix(grep): 修正 GBK 编码判定`。
56:- 一次提交一件事。
57:- 提交前 `git status` 里只应有本次改动。
58:- 提交信息 UTF-8。
```

要单独看第 3 节那 7 条，用 `python main.py grep -n "^- " AGENTS.md` 的输出取行号 28 到 34 那一段即可。

### 第 3 步：用目录分工表定位改动该放哪

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -n "^| " AGENTS.md
```

预期能看到两张表：第 2 节的目录分工表（6 行数据）和第 7 节的定时任务表（2 行数据）。判断规则很简单——要写的东西属于哪一类，就放进对应的目录；表里「写入方」只有 AI 的，人不要手改。

### 第 4 步：加指令时照第 4 节的 6 步走

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -n "^[0-9]\. " AGENTS.md
```

预期输出 6 行，就是加一个指令的固定流程：

```
38:1. 在 `w2l/commands/` 建 `<名字>.py`，写 `build_parser()` 与处理函数。
39:2. 处理函数用 `@command("<名字>", "一句话说明", build_parser)` 装饰。
40:3. 在 `tests/` 建 `test_<名字>.py`，覆盖正常路径、选项组合、错误路径。
41:4. 在 `README.md` 的指令表补一行。
42:5. 跑 `python -m pytest -q`。
43:6. 提交。
```

每一步都能独立验证。放完文件后确认自动发现生效：

```bash
python main.py
```

预期「可用指令:」下面多出新指令那一行。完整的手把手版本（含可直接粘贴的实现和测试代码）见 `teach/13-新增一个指令的完整过程.md`。

### 第 5 步：按第 5 节跑测试

第 5 节只有一句判据：「`python -m pytest -q`，全绿才允许提交。测试跑不起来就是没验证，不写『已验证』」。

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q
```

预期：

```
....................................                                     [100%]
36 passed in 0.15s
```

36 个点对应 36 条用例，全在 `tests/test_grep.py` 里。

### 第 6 步：按第 6 节提交

```bash
cd E:\1\NULL\Windows-to-Linux
git status --short
```

预期只列出本次改动，没有别的文件混进来。然后：

```bash
git add w2l tests README.md
git commit -m "feat(ls): 实现 ls 指令"
```

一次提交一件事：实现和它的测试可以放同一个提交（是同一件事），文档改动单独一个 `docs` 提交。提交信息 UTF-8。

### 第 7 步：自查退出码

第 3 节的退出码约定是硬约束里最容易被违反的一条，因为「写错了也能跑」。实测对照：

| 场景 | 命令 | 退出码 |
|---|---|---|
| 打印帮助（无参数） | `python main.py` | 1 |
| 显式帮助 | `python main.py --help` | 0 |
| 未知指令 | `python main.py nosuch` | 2 |
| grep 有命中 | `python main.py grep "UsageError" w2l/errors.py` | 0 |
| grep 无命中 | `python main.py grep "ZZZ" w2l/errors.py` | 1 |
| grep 无效正则 | `python main.py grep "[" w2l/errors.py` | 2 |
| grep 目录没加 `-r` | `python main.py grep "x" w2l` | 2 |

两个容易踩的点：

- `python main.py` 不带参数会打印用法，但退出码是 **1** 不是 0（`w2l/cli.py:68`）。在 CI 里判「命令跑成功了」不能只看有没有输出。
- `1` 不只表示「grep 没匹配到」。`w2l/cli.py` 里 `UsageError` → 2、`CommandError` → 1，所以指令层抛 `CommandError` 也是 1。目前 `w2l/` 下没有任何地方抛 `CommandError`（只有 `cli.py` 导入并捕获它），实际用到的只有 `UsageError` → 2。

再核一遍 BRE 默认这条：

```bash
python main.py grep "UsageError|CommandError" w2l/errors.py; echo "退出码=$?"
python main.py grep -E "UsageError|CommandError" w2l/errors.py; echo "退出码=$?"
```

预期第一条退出码 1（BRE 里 `|` 是字面量，匹配不到）、第二条退出码 0 并输出两行。

最后确认「零第三方依赖」这条没被破掉：

```bash
python main.py grep -rE "^import (requests|chardet|numpy)|^from (requests|chardet|numpy)" w2l/ tests/; echo "退出码=$?"
```

预期退出码 1（一条都搜不到）。真要加依赖，先按第 3 节的要求问过。
