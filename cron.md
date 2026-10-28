# Windows-to-Linux · 开发任务 cron prompt

这份文件是「补 Linux 常用命令」定时任务的执行说明。每次触发的会话都读它，调度器里的 prompt 字段与本文件内容一致，本文件是唯一真相源。

工作区根目录：`E:\1\NULL\Windows-to-Linux`

**权威细则在 `AI/AGENTS.md`**：任务分工、取锁协议、进度追加格式、提交纪律、产出路径、硬红线。本 prompt 只规定执行顺序与命令口径，两处冲突时以 `AI/AGENTS.md` 为准。

--- 以下为 prompt 正文 ---

session：`mode=new`。

## 0. 读守则

读 `AGENTS.md`、`AI/AGENTS.md`、`AI/阅读进度.md`。

从 `AI/阅读进度.md` 的命令队列里确认哪些命令已经做完、下一个该做哪个。命令队列顺序固定：

```
ls → cat → head → tail → wc → find → tree → du → sed → awk-lite
```

本 tick 的产出范围就是队列里第一个没做完的命令，一次只做这一个。

## 1. 取锁

```bash
python AI/脚本/_t10_lock.py acquire --owner 开发
```

输出 JSON 里 `ok` 为 `false` 时，本 tick 不动手：写清锁被谁占着，直接进第 7 步收尾。

## 2. 实现指令

新指令写进 `w2l/commands/<指令名>.py`，结构照 `w2l/commands/grep.py`：

- `build_parser()` 返回 `argparse.ArgumentParser`，`prog` 写 `python main.py <指令名>`
- 处理函数签名 `(args: argparse.Namespace, ctx: RunContext) -> int`
- 用 `@command("<指令名>", "一句话说明", build_parser)` 装饰
- 退出码：`0` 成功，`1` 无结果，`2` 用法或运行错误
- 正常输出写 `ctx.stdout`，报错写 `ctx.stderr`
- 只用 Python 标准库
- 参数取同名 Linux 命令的常用选项，范围收在日常够用

新指令放在 `w2l/commands/` 下即被自动发现，分发层和 `main.py` 都不动。

## 3. 写测试

在 `tests/test_<指令名>.py` 写 pytest 测试：正常路径至少一条、选项组合至少一条、错误路径至少一条。

跑：

```bash
python -m pytest -q
```

有红就改到全绿，测试跑不起来就是没验证，不许提交。

## 4. 补文档

在 `README.md` 的 grep 选项表后面加一张新指令的选项表，写清每个选项的行为和一行用法示例。

选项表写三列：选项、含义、示例命令。示例里的路径用 `w2l/` 下真实存在的文件，不要写不存在的名字。改完把新增指令补进 `README.md` 的能力清单，命令名和选项字母与实现保持一致。

## 5. 提交

```bash
git add w2l tests README.md
git commit -m "feat(<指令名>): 实现 <指令名> 指令"
git push origin main
```

提交信息 UTF-8，一次提交一件事。提交前确认 `git status` 里没有本次范围之外的文件。

推送失败时（凭据或网络问题）本地提交保留，把「推送未成功」和报错原文写进报告，下个 tick 重推。

## 6. 追加进度

```bash
python AI/脚本/_t11_progress.py --进度 AI/阅读进度.md --主题 "实现 <指令名> 指令" --理由 "<为什么这个 tick 做它>" --产出 "<新增或修改的文件路径>" --收获 "<关键收获>" --负面 "<翻车或判据误报，没有就写 无>"
```

再把命令队列里当前这一项的状态标为完成。进度文件的历史段落只能追加，不许重写。

## 7. 释放锁与报告

```bash
python AI/脚本/_t10_lock.py release --owner 开发
```

报告写四行：本 tick 实现了哪个命令、测试结果、新增文件路径、队列里下一个待做命令。

## 8. 收尾状态

本 tick 算完成的条件：指令实现并注册、测试全绿、文档已补、提交完成、进度已追加、锁已释放。六条齐了才是完成态，任何一条没做，报告里写清缺哪一条。
