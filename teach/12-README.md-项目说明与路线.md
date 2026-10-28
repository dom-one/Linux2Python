# README.md — 项目说明与路线

`README.md` 是项目根目录下的对外说明：它是什么、怎么用、能力边界在哪、接下来要做什么。164 行，8 个二级小节。

## 为什么这么创建

一个仓库的 README 回答三个问题：**这是什么**、**我为什么关心它**、**我下一步怎么做**。这个项目的读者分两类，所以 README 同时承担两个角色：

- **使用者视角**：「快速开始」和「grep 能力清单」让人五分钟内能敲出有效命令，不用读源码。
- **贡献者视角**：「架构设计」「如何新增一个指令」「后续演进路线」告诉想改代码的人边界在哪、哪些事已经规划过了。

单独维护一份 README 的成本是「和代码不同步」。所以项目把「哪些内容写在哪」定死：`AGENTS.md` 第 2 节的目录分工表写明 `README.md` 放「项目说明、路线、用法」，`cron.md` 第 4 步要求开发任务每加一个指令就补一张新的选项表——README 是靠流程保证同步的，不是靠自觉。

**为什么 README 里也贴代码片段。**「如何新增一个指令」一节贴了 `ls` 的完整实现。理由是：抽象描述（「写一个 build_parser 和一个处理函数」）不如一段能抄的代码。新人照着抄一遍就能上手，不用先读懂四层架构。

**为什么不把细节全塞进 README。** README 是入口，不是手册。所以它只写「有哪些能力、怎么用」，实现细节留给源码和 `teach/` 教程。9 个 grep 选项的行为差异、BRE 与 ERE 的坑、编码判定顺序这些东西，README 只给一句话概括，展开讲会让 README 迅速膨胀到没人愿意读。

## 这个文件是做什么

小节与用途：

| 小节 | 内容 | 读者 |
|---|---|---|
| 标题 + 简介 | 定位、当前实现了什么、零依赖 | 所有人 |
| 快速开始 | 5 条可直接跑的命令 | 使用者 |
| grep 能力清单 | 9 个选项的表格 + 6 条「行为细节对齐 GNU grep」 | 使用者 |
| 目录结构 | 当时的源码树 | 贡献者 |
| 架构设计 | 四层划分 + 5 个关键设计点 | 贡献者 |
| 如何新增一个指令 | 4 步 + 一段 `ls` 示例代码 | 贡献者 |
| 后续演进路线 | 四个阶段（补齐 grep → 常用命令族 → 工程化 → 分发） | 所有人 |
| 性能优化要点 | 5 条，按收益排序 | 贡献者 |
| Git / GitHub 协作约定 | 分支模型、提交信息、PR 要求、CI、版本发布 | 贡献者 |
| 本地首次使用 | `git init` 到 `git push` 的 5 行命令 | 新贡献者 |

不负责：源码实现、测试怎么写（那是 `tests/` 和 `teach/08-...`）、定时任务怎么跑（`teach/16-...`）、项目守则（`AGENTS.md`）。

## 有什么用

- 新用户第一份文档：读完「快速开始」就能开始用。
- 已知缺口清单：「后续演进路线」把 grep 还没做的 `--include`、`-A/-B/-C`、`--color` 明确列出来，避免有人重复提 issue。
- 架构契约的书面版：「四层，每层职责单一」和「指令自动发现」「解析器工厂」「异常到退出码的映射集中在一处」「上下文注入」这四条，是新指令必须遵守的约定。
- 协作规则的入口：分支模型、Conventional Commits、PR 要求在这里，细节在 `AGENTS.md`。

## 怎么用（过程教程）

### 第 1 步：先跑「快速开始」里的命令

README 的「快速开始」给了 5 条命令。前 3 条在这个仓库里能直接跑：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py                          # 列出可用指令
python main.py grep --help              # 查看 grep 用法
python main.py grep -ril "error" .      # 递归列出含匹配的文件名
```

预期：`python main.py` 列出 `grep`；`--help` 打印 9 个选项和 4 条示例；`-ril` 输出一列文件名。

后两条用的文件在这个仓库里不存在（`src/`、`app.log`），照抄会报错：

```bash
python main.py grep -rn "TODO" src      # src 目录不存在
python main.py grep -cE "ERROR|FATAL" app.log   # app.log 不存在
```

要用它们，指向真实存在的路径：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -rn "def " w2l
python main.py grep -cE "ERROR|warn" tests/test_grep.py
```

### 第 2 步：用「grep 能力清单」当速查表

选项表和源码一一对应（`w2l/commands/grep.py:52` 到 `:60`）：

| README 里写的 | 源码里的 `add_argument` |
|---|---|
| `-i` 忽略大小写 | `("-i", "--ignore-case", action="store_true")` |
| `-v` 反向匹配 | `("-v", "--invert-match", action="store_true")` |
| `-n` 显示行号 | `("-n", "--line-number", action="store_true")` |
| `-r` 递归搜索目录 | `("-r", "--recursive", action="store_true")` |
| `-E` 使用扩展正则 ERE | `("-E", "--extended-regexp", action="store_true")` |
| `-w` 只匹配完整单词 | `("-w", "--word-regexp", action="store_true")` |
| `-c` 只输出匹配行数 | `("-c", "--count", action="store_true")` |
| `-l` 只输出含匹配的文件名 | `("-l", "--files-with-matches", action="store_true")` |
| `-o` 只输出匹配到的部分 | `("-o", "--only-matching", action="store_true")` |

README 里「行为细节对齐 GNU grep」那 6 条，逐条对应到代码：

| README 的说法 | 代码依据 |
|---|---|
| 正则默认 BRE，`+ ? \| ( ) { }` 是字面量 | `_translate_bre()` + `_BRE_LITERALS` |
| 退出码 0/1/2 | `grep()` 末尾 `return 2 / return 0 if matched_any else 1` |
| 编码自动判定：按文本可信度择优，GBK 文件在英文 Windows 上也能搜到 | `_detect_encoding()` + `_text_score()` |
| 二进制文件输出 `Binary file xxx matches` | `_search_binary()` |
| 多文件前缀 `文件:行号:内容` | `_line_prefix()` + `show_prefix` |
| 不给路径时终端搜当前目录、管道读 stdin | `grep()` 里的 `stdin_mode` 判断 + `_search_stdin()` |

编码判定不是「按顺序取第一个能解码的」，而是给每个候选解码结果按文本可信度打分（`_text_score()`），明显更优才替换。原因见 `07-w2l-commands-grep.py-检索实现.md` 第 8 步：英文 Windows 的系统编码是 `cp1252`，它能把 GBK 字节无错解成乱码。

### 第 3 步：改代码前先读「架构设计」

README 的四层划分：

1. 入口层 `main.py`
2. 分发层 `w2l/cli.py`
3. 注册层 `w2l/registry.py`
4. 指令层 `w2l/commands/*.py`

「新增一个指令」的 4 步（README 版本）和 `AGENTS.md` 第 4 节的 6 步内容一致，区别是 AGENTS.md 多了一步「提交」和一步「跑测试」。完整可照做的流程见 `teach/13-新增一个指令的完整过程.md`。

### 第 4 步：查「后续演进路线」知道什么还没做

阶段一（补齐 grep）列了 5 项：`--include` / `--exclude`、`-A` / `-B` / `-C`、`-h` / `-H`、`--color=auto|always|never`、`--binary-files=without|with`。

对照源码确认这些确实还没有：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep --help
```

帮助里只有 9 个选项，没有上面任何一个。（顺带一提，GNU grep 最常用的 `-q` 也不在 README 的规划列表里，当前 `python main.py grep -q "x" .` 会报 `unrecognized arguments: -q`。）

阶段二列的常用命令族（`ls`、`cat`、`head`、`tail`、`wc`、`find`、`tree`、`du`、`cp`、`mv`、`rm`、`chmod`、`sed`、`awk-lite`）和 `cron.md` 里的开发队列一致，队列顺序是 `ls → cat → head → tail → wc → find → tree → du → sed → awk-lite`。

### 第 5 步：知道 README 哪里已经过期

这是维护 README 时要注意的几处（截至当前代码状态）：

- **目录结构小节不完整。** 它列了 `main.py`、`w2l/`（缺 `w2l/__init__.py`）、`tests/`、`pyproject.toml`、`.github/workflows/ci.yml`，但没列 `teach/`、`AI/`、`cron.md`、`AGENTS.md`、`.gitignore`。这些目录后来才建立，README 没跟上。
- **快速开始的示例路径在仓库里不存在**（`src/`、`app.log`）。示例是通用写法，不是本仓库的真实路径。
- **`ls` 示例代码是最小版**。它没有 `-a`（隐藏文件）、没有目录不存在时的错误处理，而且 `ctx.cwd.joinpath(args.path).iterdir()` 在路径不存在时会抛 `FileNotFoundError`。真要上线 `ls`，按 `teach/13-...` 里的版本走。
- **版本号有两处**：`pyproject.toml` 的 `version = "0.1.0"` 和 `w2l/__init__.py` 的 `__version__ = "0.1.0"`，手工同步。

### 第 6 步：改 README 的规矩

- 加了新指令：在 grep 选项表后面加一张新指令的选项表，每行写清行为和一行示例（`cron.md` 第 4 步的规定）。
- 加了新能力：在「后续演进路线」里把对应条目从待办移到已实现，或者直接删掉。
- 不要在 README 里写「已验证」这类结论——`AGENTS.md` 第 5 节明确要求「测试跑不起来就是没验证」。
- 改完跑一遍 README 里「快速开始」的命令，确认每条都还能用。

### 第 7 步：README 和其它文档的分工

| 想找什么 | 去哪 |
|---|---|
| 怎么用某个命令 | README 的速查表，或 `teach/07-...` |
| 源码怎么组织的 | README 的「架构设计」+ `teach/00-...` |
| 加指令的完整步骤 | `teach/13-...` |
| 提交信息怎么写 | README 的「Git / GitHub 协作约定」+ `AGENTS.md` 第 6 节 |
| 定时任务怎么跑 | `teach/16-...` |
| 逐文件讲解 | `teach/` 目录 |
