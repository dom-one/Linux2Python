# Git 与 GitHub 协作流程

这篇讲这个仓库的版本控制约定：分支怎么开、提交信息怎么写、PR 怎么提、什么时候打 tag，以及两个自动任务和人工提交怎么不打架。

## 为什么这么创建

这个仓库有**三个写入方**：人、开发 cron 任务、教程 cron 任务。三方同时改同一个仓库，会遇到三类具体问题：

1. **索引冲突。** 两个进程同时 `git add` / `git commit`，会撞 `.git/index.lock`，报错 `Unable to create '.../index.lock': File exists`。这不是「提交冲突」，是文件系统层面的互斥，必须用锁解决。
2. **主干被写坏。** 如果任何一次提交都能直接落到 `main`，那么「main 保持可用」这条约定就没有强制力。
3. **不知道哪个改动是谁做的。** 提交信息乱写，半年后无法回溯是谁、为什么改的。

对应的三件套是：锁（`AI/脚本/_t10_lock.py`）、分支模型、Conventional Commits。

**为什么用 Conventional Commits 而不是随便写。** `feat(ls): 实现 ls 指令` 这种格式是**机器可读**的：`feat` 表示新功能，`fix` 表示修 bug，`(ls)` 表示作用域是 ls 指令。有了这个前缀，将来可以直接用 commitizen / conventional-changelog 自动生成 CHANGELOG、自动算语义化版本号，不用人工整理。

**为什么 PR 要「一个 PR 只做一件事」。** 因为 CI 的矩阵是 5 个 Python 版本，一个大 PR 一旦红在哪一版很难定位。拆小之后，出问题的改动范围一眼可见。

**为什么 `main` 必须保持可用。** 因为这是给别人 clone 的入口。`main` 上的代码应该是「随时能跑 `python main.py`」的状态，而不是「开发到一半的现场」。

## 这个文件是做什么

这是流程约定，涵盖：

| 环节 | 约定 | 出处 |
|---|---|---|
| 分支模型 | `main` 保持可用；功能分支 `feat/<名字>`；修复分支 `fix/<名字>`；实验性 `spike/<名字>` | README「Git / GitHub 协作约定」 |
| 提交信息 | Conventional Commits，例如 `feat(ls): 实现 ls 指令`、`fix(grep): 修正 GBK 编码判定` | `AGENTS.md` 第 6 节 |
| 提交粒度 | 一次提交一件事 | `AGENTS.md` 第 6 节 |
| 提交前检查 | `git status` 里只应有本次改动 | `AGENTS.md` 第 6 节 |
| 提交前测试 | `python -m pytest -q` 全绿才允许提交 | `AGENTS.md` 第 5 节 |
| 提交信息编码 | UTF-8 | `AGENTS.md` 第 6 节 |
| Git 配置 | 不改 git 全局配置 | `AI/AGENTS.md` 第 5 节 |
| PR | 一个 PR 只做一件事；写清「改了什么 / 为什么 / 怎么验证」；CI 必须绿 | README |
| CI | push/PR 到 main 触发，Python 3.10–3.14 矩阵 | `.github/workflows/ci.yml` |
| 版本 | 语义化版本，tag `v0.1.0` 对应一次可用的能力集，GitHub Release 附变更说明 | README |
| 并发 | 两个 cron 任务共用一把锁，避免同时写 git 索引 | `AI/AGENTS.md` 第 3 节 |

当前仓库的实际状态（可现场核对）：

```bash
cd E:\1\NULL\Windows-to-Linux
git branch -a
git remote -v
git log --oneline
```

- 只有一个分支 `main`。
- **没有配置远程仓库**（`git remote -v` 输出为空）。所以现在还没有 GitHub PR / Release 的实际对象，CI 也不会跑。
- 已有三个提交：`feat(grep): 实现 grep 子集与指令分发骨架`、`fix(grep): 修正无效正则未转异常与目录操作数校验时机`、`feat(workspace): 建 teach 教程夹、定时任务骨架与项目守则`。

## 有什么用

- 每条提交能看出「改了什么、为什么改」，`git log` 本身就是一个变更记录。
- CI 是唯一的合并闸门，PR 红了不能合。
- 锁机制让自动任务和人工提交不打架。
- tag 和 Release 让「哪个版本有什么能力」有确定答案。

## 怎么用（过程教程）

### 第 1 步：动手前先看工作区

```bash
cd E:\1\NULL\Windows-to-Linux
git status
git branch
```

`git status` 里如果有本次范围之外的文件，先搞清楚是谁留下的再决定怎么处理。`AGENTS.md` 第 6 节的要求是「提交前 `git status` 里只应有本次改动」。

### 第 2 步：开分支

```bash
cd E:\1\NULL\Windows-to-Linux
git switch -c feat/ls
```

命名规则：

| 前缀 | 用途 |
|---|---|
| `feat/<名字>` | 新指令、新功能 |
| `fix/<名字>` | 修 bug |
| `spike/<名字>` | 一次性实验，不一定保留 |

### 第 3 步：改代码

按 `teach/13-新增一个指令的完整过程.md` 走。

### 第 4 步：跑测试

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q
```

预期：`31 passed`（或加了新用例后的新数字）。**测试红着就不要提交**——`AGENTS.md` 第 5 节的原话是「测试跑不起来就是没验证，不写『已验证』」。

### 第 5 步：提交

```bash
cd E:\1\NULL\Windows-to-Linux
git add w2l/commands/ls.py tests/test_ls.py README.md
git status
git commit -m "feat(ls): 实现 ls 指令"
```

`git status` 确认暂存区只有本次改动的文件，再提交。

提交信息格式：`<type>(<scope>): <描述>`。

| type | 用在哪 |
|---|---|
| `feat` | 新指令、新功能 |
| `fix` | 修 bug |
| `docs` | 只改文档（比如 `docs(teach): 补充 grep.py 教程`） |
| `chore` | 配置、构建、杂项 |
| `refactor` | 不改行为的重构 |
| `test` | 只改测试 |

描述用中文，写清楚做了什么。提交信息是 UTF-8。

### 第 6 步：推分支、开 PR

```bash
cd E:\1\NULL\Windows-to-Linux
git push -u origin feat/ls
```

（当前仓库还没配远程，第一次要先 `git remote add origin <仓库地址>`。README 的「本地首次使用」一节给了完整的 5 行：`git init -b main` → `git add .` → `git commit` → `git remote add origin` → `git push -u origin main`。）

然后在 GitHub 上开 PR，描述里写三件事（小标题用三级标题即可）：

```markdown
### 改了什么
新增 ls 指令，支持多目录参数与 -a 选项。

### 为什么
命令队列第 1 项，Windows 上最常被抱怨缺失的命令。

### 怎么验证
python -m pytest -q    # 36 passed
python main.py ls -a
```

### 第 7 步：等 CI

PR 页面会显示 5 个 job（3.10～3.14）。全绿才能合。

CI 的定义见 `teach/11-github-actions-ci.yml-持续集成.md`。注意那个 workflow 的 `Install` 步骤没有装 pytest，这是当前配置的一个薄弱点。

### 第 8 步：合并

PR 合并方式建议用 squash merge（GitHub 默认），这样 `main` 上每个提交对应一个 PR，历史干净。

合并后 `main` 必须保持可用——合并前再确认一次 `python -m pytest -q` 绿。

### 第 9 步：打 tag

发一个可用能力集时：

```bash
cd E:\1\NULL\Windows-to-Linux
git tag -a v0.1.0 -m "grep 指令可用"
git push origin v0.1.0
```

然后在 GitHub 上建 Release，附变更说明。版本号是语义化的：`v0.1.0` 对应「有一个能用的指令」，`v0.2.0` 对应「加了一批命令」。

版本号在两处手工同步：`pyproject.toml` 的 `version` 和 `w2l/__init__.py` 的 `__version__`。

### 第 10 步：和 cron 任务并发时的规矩

两个 cron 任务也往这个仓库提交。如果你在它们跑的时候手动提交，会撞 `index.lock`。处理办法：

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t10_lock.py status
```

如果 `owner` 不是「未知」且 `released_ts` 是 `null`，说明锁被占着，等它释放（`AI/AGENTS.md` 第 3 节：超过 30 分钟的僵尸锁会被自动接管）。取锁和释放：

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t10_lock.py acquire --owner 人工
# ... 干活 ...
python AI/脚本/_t10_lock.py release --owner 人工
```

细节见 `teach/15-AI目录与脚本约定.md`。

### 第 11 步：不要做的事

- **不要改 git 全局配置**（`AI/AGENTS.md` 第 5 节）。`git config --global user.name` / `user.email` 是机器级设置，改它会影响这台机器上的所有仓库。想改就改仓库级的：`git config user.name "..."`。
- **不要一次提交多件事。** 想顺手改的地方另开一个提交。
- **不要提交没跑过测试的代码。**
- **不要用 `git add .`** 除非你确认过 `git status` 里没有意外文件。明确 `git add <路径>` 更安全。
- **不要 force push 到 `main`。**
