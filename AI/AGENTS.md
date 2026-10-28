# AI 细则 · 定时任务执行口径

本文件是两个 cron tick 的权威细则。`cron.md` 与 `AI/cron-教程任务.md` 只写执行顺序，两者冲突时以本文件为准。

## 1. 两个任务的分工

| 任务 | prompt 真相源 | 能写哪些目录 | 进度文件 |
|---|---|---|---|
| 开发 | `cron.md` | `w2l/`、`tests/`、`README.md` | `AI/阅读进度.md` |
| 教程 | `AI/cron-教程任务.md` | `teach/` | `AI/教程进度.md` |

## 2. 每个 tick 的固定顺序

1. 读 `AI/AGENTS.md` 和本任务的进度文件，确认上次做到哪。
2. 取锁。
3. 干本 tick 的活。
4. 跑 `python -m pytest -q`。
5. 提交。
6. 追加 tick 日志。
7. 释放锁。

## 3. 取锁与释放

```bash
python AI/脚本/_t10_lock.py acquire --owner 开发
python AI/脚本/_t10_lock.py release --owner 开发
```

- 锁文件 `AI/锁/git.lock`，字段 `owner`、`acquired_ts`、`released_ts`。
- `acquire` 输出 JSON。`ok` 为 `false` 时本 tick 不动手，直接收尾报告。
- `released_ts` 为 `null` 且 `acquired_ts` 距今超过 30 分钟 = 僵尸锁，`acquire` 会直接接管。
- 两个任务共用一把锁，因为都要写 git 索引，同时提交会撞 `index.lock`。

## 4. 进度追加

```bash
python AI/脚本/_t11_progress.py --进度 AI/阅读进度.md --主题 "实现 ls 指令" --理由 "命令队列里下一个" --产出 w2l/commands/ls.py --收获 "..." --负面 "..."
```

- 字节追加，历史不覆盖。
- tick 号在写入前一刻现算，不靠推断。
- 负面结果照实写：翻车、判据误报、产出不足，下个 tick 会读它。

## 5. 提交纪律

- 测试有红就不提交。
- 一次提交一件事，消息格式 `feat(ls): 实现 ls 指令`。
- 提交信息 UTF-8。
- 不改 `git` 全局配置。

## 6. 产出路径

| 产出 | 路径 |
|---|---|
| 开发任务源码 | `w2l/commands/` |
| 开发任务测试 | `tests/` |
| 开发任务文档 | `README.md` |
| 教程任务产出 | `teach/` |
| 脚本、中间产物、日志 | `AI/` |

两处（prompt 与本文件）写同一份路径，不改动。

## 7. 硬红线

- 不改 `w2l/`、`tests/` 之外的项目代码（开发任务）。
- 教程任务只写 `teach/` 下的文件，不改源码。
- 不提交没跑过测试的代码。
- 不覆盖进度文件，只能追加。
- 不把 prompt 里的示例当成现状写进文档。
- 不动 `E:\1\NULL\AGENTS.md`（上级工作区守则）。
