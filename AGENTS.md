# Windows-to-Linux · 项目守则

## 1. 项目是什么

命令行工具，在 Windows 上提供类 Linux 命令。统一入口：

```
python main.py <指令> [参数]
```

纯标准库实现，没有第三方依赖，Python 3.10 及以上可跑。

## 2. 目录分工

| 路径 | 放什么 | 写入方 |
|---|---|---|
| `w2l/` | 源码 | 人和 AI |
| `tests/` | pytest 测试 | 人和 AI |
| `teach/` | 逐文件教程 | 人和 AI |
| `AI/` | 脚本、中间产物、tick 进度、教程任务的 prompt | AI |
| `cron.md` | 开发任务的定时 prompt | AI |
| `README.md` | 项目说明、路线、用法 | 人和 AI |

`AI/` 之外不落中间产物和日志。

## 3. 硬约束

- 源码零第三方依赖。要加依赖先问。
- 一个新指令 = `w2l/commands/<名字>.py` 一个文件 + `tests/test_<名字>.py` 一个文件，主干不动。
- 新指令必须提供 `build_parser()` 和一个用 `@command` 装饰的处理函数。
- 退出码：`0` 成功，`1` 无结果（命中类指令），`2` 用法或运行错误。
- 输出统一 UTF-8。Windows 控制台靠 `SetConsoleOutputCP(65001)` 保证中文不乱码。
- 文件读写走 Python 脚本，不写内联解释器、不写 heredoc、不用 PowerShell 文件操作命令。
- 正则默认 BRE，与 GNU grep 一致；要 ERE 就加 `-E`。

## 4. 加一个指令的步骤

1. 在 `w2l/commands/` 建 `<名字>.py`，写 `build_parser()` 与处理函数。
2. 处理函数用 `@command("<名字>", "一句话说明", build_parser)` 装饰。
3. 在 `tests/` 建 `test_<名字>.py`，覆盖正常路径、选项组合、错误路径。
4. 在 `README.md` 的指令表补一行。
5. 跑 `python -m pytest -q`。
6. 提交。

## 5. 测试

```bash
python -m pytest -q
```

全绿才允许提交。测试跑不起来就是没验证，不写「已验证」。

## 6. 提交

- 消息格式：Conventional Commits，例如 `feat(ls): 实现 ls 指令`、`fix(grep): 修正 GBK 编码判定`。
- 一次提交一件事。
- 提交前 `git status` 里只应有本次改动。
- 提交信息 UTF-8。

## 7. 定时任务

两个 cron 任务，共用一把锁，都改这个仓库：

| 任务 | 干什么 | prompt 真相源 |
|---|---|---|
| 开发 | 补 Linux 常用命令 | `cron.md` |
| 教程 | 补 `teach/` 教程 | `AI/cron-教程任务.md` |

执行细则在 `AI/AGENTS.md`。
