# w2l/commands/mv.py — 落点判定与覆盖策略

`w2l/commands/mv.py` 有 386 行，注册出来的指令叫 **`mv`**。它做的事只有一件：**把一个或多个源搬到目标上**。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py mv w2l/registry.py w2l/registry.py.bak   # 改名
python main.py mv w2l/commands backup/                  # 整个目录搬走
python main.py mv -v -b README.md docs/README.md       # 备份旧目标并显示过程
```

mv 看起来是最简单的命令，实际上它是**所有文件操作里语义分岔最多的一个**。因为「搬到哪里去」这个问题至少有六种答案：目标已存在且是目录、目标已存在且是文件、目标不存在、给了多个源、给了 `-t`、给了 `-T`……每一种的落点都不一样。更麻烦的是覆盖策略：**`-n` / `-u` / `-i` / `-b` / `-f` 五个选项各有各的判据，而且 GNU 里互斥选项是「后给的那个赢」**。

本实现把这些判定收在两个地方：`plan()`（规划落点）与 `move_source()`（执行单个源）。本轮实测查出：**6 处与 GNU coreutils 8.32 的行为差异**（其中 4 处是真实缺陷、1 处是「本实现更宽松」、1 处是 GNU 独有能力）。都写在最后一节。

## 为什么这么创建

### 决定一：移动按字节进行，不做编码转换

模块开头第一句就是这件事：

```python
"""mv：移动文件或目录（GNU mv 风格子集）。

同盘移动走 rename/replace，跨盘退回「拷贝 + 删除」；文件按字节搬，不做编码转换。
```

这是 `mv.py` 与 `cat.py`、`sed.py`、`wc.py` 最根本的区别。那三个指令要**读**文件，必须先判「这是文本还是二进制」，再判文本是 GBK 还是 UTF-8；`mv` 不读内容，只搬字节，所以整个文件里**没有一行编码判定逻辑**。

代价是：GBK 文件搬过去还是 GBK，用 `cat` 看仍是乱码。这是**对的**——移动不该改写内容。只有需要「读出来给人看」的指令才该碰编码。

### 决定二：落点由 `plan()` 一次算清

`plan()`（第 127~174 行）返回四样东西：源列表、目标路径、目标标签、目标是不是目录。整个 `mv` 的落点分支全在这一个方法里定下来，之后 `move_source()` 只管「拿这个源去落点」。

```python
def plan(self) -> tuple[list[str], Path, str, bool] | None:
    """拆出源列表与目标。返回 None 表示规划阶段已经报错。"""
```

返回 `None` 是一个刻意的设计：**规划阶段的问题一律在动手之前报出来**。如果一边搬一边发现「目标不是目录」，那前面几个源已经搬走了，调用方看到的是一个半成品状态。入口函数（第 78~91 行）拿到 `None` 就直接退 2，一个字节都不动。

三条互斥的分支：

| 条件 | 走哪条 | 目标怎么定 |
|---|---|---|
| 给了 `-T` | 第 132~143 行 | 最后一个操作数就是目标，**永远不当目录** |
| 给了 `-t` | 第 145~156 行 | `-t` 给的目录，所有操作数都是源 |
| 都没给 | 第 158~174 行 | 最后一个操作数是目标，前面全是源 |

第三种里还有一个细分：多个源时目标必须是已存在的目录（第 170~172 行），这条检查排在逐个源的存在性检查**前面**。

### 决定三：GNU 的 mv 不合并目录

这是 `mv` 与 `cp` 最容易被搞混的一点。`cp -r dir1 destdir/` 会把 `dir1` 的内容**逐个文件**覆盖进 `destdir/dir1/`，而 `mv dir1 destdir/` 遇到 `destdir/dir1` 已存在且非空时**直接报「目录非空」**，不合并。

源码里对应这一段：

```python
            # GNU 的 mv 不合并目录：目标同名目录非空时直接报错。
            if is_dir and dst_is_dir and _dir_not_empty(dst):
                self.error(f"无法把目录 '{source}' 移动到 '{dst_label}': 目录非空")
                return
```

为什么 GNU 要这样：`mv` 的语义是「改名字」，不是「复制内容」。`cp` 的语义是「复制内容」，所以合并是自然的。GNU 把这条写进了 `mv` 的手册，读者若把 `cp -r` 的直觉带过来就会踩。

同名目录**是空的**时移动照常进行——等于用源目录替换掉那个空目录。Windows 上 `os.replace()` 不能覆盖已存在的目录，所以实现里先 `os.rmdir(dst)` 再改名（第 266~268 行）。

### 决定四：`-i` 与 `-n` 互斥，后给的那个赢

GNU 的 `cp` 与 `mv` 都有这条：`cp -n -i a b` 会提示并照搬，`cp -i -n a b` 不提示也不搬。**重复给时取最后一次出现**，不是第一次。

argparse 默认不记录选项出现的先后（`store_true` 只留「给过没给过」），所以项目抽了个共享模块 `w2l/flags.py`：自定义 Action `FlagTracker` 把顺序攒进 `namespace.option_order`，`resolve_exclusive()` 据此裁决。`cp.py` 与 `mv.py` 共用这一份。

```python
        policy = resolve_exclusive(
            getattr(args, "option_order", None) or [],
            {"interactive": bool(args.interactive), "no_clobber": bool(args.no_clobber)},
        )
        return policy["interactive"], policy["no_clobber"]
```

`cp.py` 与 `mv.py` 都是「先给的那个赢」的旧写法被开发任务在 tick #19 改成「后给的赢」，改动就是接上了这个共享模块。

### 决定五：备份是「改名」不是「复制」

`-b` 的实现是 `_backup()`（第 251~262 行）：把旧目标**改名**成「目标名 + 后缀」，再把源改名过去。所以旧目标的 inode 直接挪过去，不是复制一份再删。

```python
    def _backup(self, dst: Path, dst_label: str) -> str:
        """把旧目标改名加后缀备份掉。返回备份标签，失败返回空串。"""
        backup = Path(str(dst) + self.suffix)
```

`-S` 单独给就等于隐含开备份（第 106 行）：

```python
        # GNU 里 -S 单独给就等于隐含开备份。
        self.backup = args.backup or args.suffix is not None
```

### 决定六：Windows 上覆盖只读文件要先清只读属性

```python
def _clear_readonly(path: Path) -> None:
    """Windows 上覆盖只读文件会失败，先去掉只读属性。

    GNU 的 mv 直接 rename 过去，不看目标文件的权限位，所以这里无条件清。
    """
```

Linux 上 `rename()` 覆盖目标文件不看权限位，Windows 上不行。所以 `_do_move()`（第 269 行）在 `os.replace()` 之前无条件清一次只读属性。

代价是 `-f` 与不加 `-f` 在本项目里**行为一样**（`-f` 只影响文档描述，不影响执行路径），这与 GNU 不同——GNU 的 `-f` 是「遇到权限错误也强行覆盖」。

## 这个文件是做什么

### 数据流

```
命令行 argv
    │
    ▼
build_parser()  ──► argparse 解析出 Namespace
    │               （-i/-n 额外记进 namespace.option_order）
    ▼
mv(args, ctx)  第 78~91 行
    │
    ├─► _State(args, ctx)   第 97~108 行
    │       选项归并：backup = -b 或 -S；suffix 默认 "~"
    │       覆盖策略归并：resolve_exclusive 裁决 -i 与 -n
    │
    ├─► state.plan()        第 127~174 行
    │       返回 (源列表, 目标路径, 目标标签, 目标是不是目录)
    │       返回 None = 规划阶段就报错，退 2
    │
    └─► 逐个源：state.move_source(source, dest, dest_label, dest_is_dir)
            第 178~238 行
                ├─ _destination_for()  第 240~247 行  算这个源的落点
                ├─ _same_file()        第 325~334 行  是不是同一个文件
                ├─ _is_inside()        第 337~347 行  是不是移进自己的子目录
                ├─ 覆盖策略：-n → -u → -i → 目录非空检查
                ├─ _backup()           第 251~262 行  备份旧目标
                ├─ _do_move()          第 264~284 行  rename，跨盘退回 shutil.move
                └─ -v 打印 "renamed '源' -> '目标'"
```

### 选项清单

| 选项 | 含义 | 示例命令 |
|---|---|---|
| （无） | 移动文件；目标是已存在的目录时落成「目录/源名」 | `python main.py mv w2l/registry.py w2l/registry.py.bak` |
| （无） | 目标不存在时，目标就是新名字本身 | `python main.py mv w2l/entry.py w2l/entry.py.bak` |
| `-f` / `--force` | 强制覆盖（先去掉目标的只读属性） | `python main.py mv -f w2l/cli.py w2l/cli.py.bak` |
| `-i` / `--interactive` | 覆盖已存在的目标前问一句 | `python main.py mv -i w2l/cli.py w2l/cli.py.bak` |
| `-n` / `--no-clobber` | 不覆盖已存在的目标 | `python main.py mv -n w2l/cli.py w2l/cli.py.bak` |
| `-u` / `--update` | 仅当源比目标新时才移动 | `python main.py mv -u w2l/cli.py w2l/cli.py.bak` |
| `-v` / `--verbose` | 逐条打印「renamed 源 -> 目标」 | `python main.py mv -v w2l/cli.py w2l/cli.py.bak` |
| `-b` / `--backup` | 覆盖前把旧目标改名备份（后缀 `~`） | `python main.py mv -b w2l/cli.py w2l/cli.py.bak` |
| `-S` / `--suffix=后缀` | 备份后缀（默认 `~`，单独给 `-S` 就隐含开备份） | `python main.py mv -S .bak w2l/cli.py w2l/cli.py.bak` |
| `-t` / `--target-directory=目录` | 把目标目录写死，可给多个源 | `python main.py mv -t backup/ w2l/cli.py w2l/context.py` |
| `-T` / `--no-target-directory` | 把目标当普通文件，不当目录 | `python main.py mv -T w2l/cli.py w2l/cli.py.bak` |

### 退出码

| 退出码 | 含义 |
|---|---|
| 0 | 成功（`-n` 跳过、`-u` 判定不更新、`-i` 答否，这三种「什么都没做」也算 0） |
| 2 | 用法或运行错误（GNU 用 1） |

### 关键函数速查

| 函数 | 行 | 作用 |
|---|---|---|
| `build_parser()` | 30 | 解析选项，`-i`/`-n` 用 `FlagTracker` 记顺序 |
| `mv()` | 78 | 入口：plan → 逐源 move_source → 按 `had_error` 定退出码 |
| `_State.plan()` | 127 | 算源列表与目标；`-T` / `-t` / 默认三条分支 |
| `_State.move_source()` | 178 | 单个源的完整流程：落点、同文件检查、覆盖策略、备份、搬 |
| `_State._destination_for()` | 240 | 目标是目录时落点变成「目录/源名」 |
| `_State._backup()` | 251 | 旧目标改名加后缀 |
| `_State._do_move()` | 264 | `os.replace()`；`EXDEV`（跨盘）退回 `shutil.move()` |
| `_State._confirm()` | 288 | `-i` 的提示与应答读取 |
| `_same_file()` | 325 | `os.path.samefile()` + 路径归一化双重判定 |
| `_is_inside()` | 337 | 挡住把目录移进它自己的子目录 |
| `_source_is_newer()` | 350 | `-u` 的判据：比 `st_mtime_ns` |
| `_clear_readonly()` | 369 | Windows 上覆盖前清只读属性 |
| `_remove_path()` | 382 | 删文件或目录树（备份位已存在时用） |

## 有什么用

- **改名**：`mv a.txt b.txt` 把文件换个名字，字节与时间戳原样带过去。
- **归档整理**：把散在项目根目录的文件收进 `backup/` 之类的目录。
- **批量归位**：`mv -t destdir a.txt b.txt c.txt` 一次把多个文件收进同一个目录。
- **安全覆盖**：`-b` 让旧目标自动改名备份，误覆盖了还能找回来；`-n` 则完全不覆盖。
- **只搬新的**：`-u` 让脚本只在源比目标新时才动它，适合做增量同步。

本实现**没有**做的事（GNU 有，别指望）：`-n` 之外的 `--no-target-directory` 以外的目录合并、`--backup=numbered` 的编号备份、`-Z` SELinux 上下文、`--exchange` 原子交换、`--parents` 保留路径层级（`cp` 有，`mv` 没有）。

## 怎么用（过程教程）

### 第 1 步：准备演示夹具

后面的例子全部用固定夹具，不用项目源码。理由是源码会变：拿 `w2l/commands/mv.py` 当例子，源码一改教程里写死的预期输出就全过期了。

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1503_make_mv_demo.py
```

预期输出：

```
已生成 AI/数据/mv_demo/（10 个文件）
mv_demo/ 下的内容：
  a.txt  (23 字节)
  b.txt  (13 字节)
  destdir/b.txt  (21 字节)
  dir1/inner.txt  (7 字节)
  dir1/sub/deep.txt  (6 字节)
  emptydir/
  future.txt  (7 字节)
  legacy.txt  (18 字节)
  old.txt  (7 字节)
  payload.bin  (256 字节)
```

夹具在 `AI/数据/mv_demo/`，这个目录在 `.gitignore` 里，不进仓库。

四种文件各代表一类：

- `a.txt` 两行 CRLF 文本——能看出「按字节搬，CRLF 不被改成 LF」
- `legacy.txt` GBK 编码的中文——能看出「移动不做编码转换」
- `payload.bin` 0~255 全字节——能看出「二进制逐字节保真」
- `dir1/` 两层目录树——能看出「目录整体改名」与「目录不合并」

**mv 是破坏性操作**：一条命令跑完文件就搬走了，同一个现场没法跑第二遍。所以每一步的演示命令前面都先跑 `AI/脚本/_t1504_prep_mv_case.py <案例名>` 重建现场，目录建在 `AI/数据/mv_demo/case/<案例名>/` 下。

### 第 2 步：文件改新名字

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s2
python main.py mv AI/数据/mv_demo/case/s2/a.txt AI/数据/mv_demo/case/s2/a.renamed.txt
python main.py ls AI/数据/mv_demo/case/s2
```

预期输出：

```
a.renamed.txt
b.txt
destdir
dir1
emptydir
future.txt
legacy.txt
old.txt
payload.bin
```

`mv` 成功时**什么都不打印**——这是 Unix 的老规矩。没输出就是成功，有输出通常是在 `-v` 模式或者出错了。

### 第 3 步：目标是已存在的目录时，落点是「目录/源名」

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s4
python main.py mv AI/数据/mv_demo/case/s4/a.txt AI/数据/mv_demo/case/s4/destdir
python main.py ls AI/数据/mv_demo/case/s4/destdir
```

预期输出：

```
a.txt
b.txt
```

落点是 `destdir/a.txt`，不是把 `destdir` 本身换掉。这是 Unix 的老规矩：给目录就是「放进去」。

### 第 4 步：目标不存在时，目标就是那个新名字本身

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s3
python main.py mv AI/数据/mv_demo/case/s3/dir1 AI/数据/mv_demo/case/s3/dir1.renamed
python main.py ls AI/数据/mv_demo/case/s3
```

预期输出：

```
a.txt
b.txt
destdir
dir1.renamed
emptydir
future.txt
legacy.txt
old.txt
payload.bin
```

注意 `dir1.renamed` 出现时**带着它原来的内容**（`inner.txt` 与 `sub/deep.txt` 都在里面）。目录是整体改名的，不是逐个文件搬的。

### 第 5 步：移动目录到已存在的目录

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s5
python main.py mv AI/数据/mv_demo/case/s5/dir1 AI/数据/mv_demo/case/s5/destdir
python main.py ls AI/数据/mv_demo/case/s5/destdir
```

预期输出：

```
b.txt
dir1
```

落点是 `destdir/dir1`。

### 第 6 步：源目录尾部带斜杠，落点不变

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s6
python main.py mv AI/数据/mv_demo/case/s6/dir1/ AI/数据/mv_demo/case/s6/destdir
python main.py ls AI/数据/mv_demo/case/s6/destdir
```

预期输出：

```
b.txt
dir1
```

`mv dir1/ destdir` 与 `mv dir1 destdir` 一样，都是 `destdir/dir1`。尾部斜杠不影响落点。

### 第 7 步：同名目录非空，报「目录非空」

**这是 mv 与 cp 最大的差别**。`cp -r` 会逐个文件覆盖过去，`mv` 不合并。

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s7-destdir-dir1-nonempty
python main.py mv AI/数据/mv_demo/case/s7-destdir-dir1-nonempty/dir1 AI/数据/mv_demo/case/s7-destdir-dir1-nonempty/destdir
```

预期输出：

```
mv: 无法把目录 'AI/数据/mv_demo/case/s7-destdir-dir1-nonempty/dir1' 移动到 'AI/数据/mv_demo/case/s7-destdir-dir1-nonempty/destdir/dir1': 目录非空
```

命令退 2，目标目录里的旧文件一个没动：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py ls AI/数据/mv_demo/case/s7-destdir-dir1-nonempty/destdir/dir1
```

预期输出：

```
inner.txt
stale.txt
```

### 第 8 步：同名目录是空的，移动照常

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s8-destdir-dir1-empty
python main.py mv AI/数据/mv_demo/case/s8-destdir-dir1-empty/dir1 AI/数据/mv_demo/case/s8-destdir-dir1-empty/destdir
python main.py ls AI/数据/mv_demo/case/s8-destdir-dir1-empty/destdir/dir1
```

预期输出：

```
inner.txt
sub
```

空目录被源目录替换掉了。Windows 上 `os.replace()` 不能覆盖已存在的目录，实现里先 `os.rmdir()` 掉那个空目录再改名。

### 第 9 步：多个源，目标必须是已存在的目录

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s9
python main.py mv AI/数据/mv_demo/case/s9/a.txt AI/数据/mv_demo/case/s9/b.txt AI/数据/mv_demo/case/s9/destdir
python main.py ls AI/数据/mv_demo/case/s9/destdir
```

预期输出：

```
a.txt
b.txt
```

这条检查**先于**逐个源的存在性检查：`mv a.txt nosuch.txt out.txt` 里有两个问题（源不存在、目标不是目录），报的是后者——「目标不是目录」意味着整条命令的形状就不对，改完形状下一轮才会看到哪个源真的不在。

### 第 10 步：`-v` 打印搬动过程

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s10
python main.py mv -v AI/数据/mv_demo/case/s10/a.txt AI/数据/mv_demo/case/s10/a.renamed.txt
```

预期输出：

```
renamed 'AI/数据/mv_demo/case/s10/a.txt' -> 'AI/数据/mv_demo/case/s10/a.renamed.txt'
```

`-v` 的输出沿用 GNU 的英文原文 `renamed '源' -> '目标'`（本项目的报错文案是中文，但 `-v` 这句保持 GNU 原样）。

### 第 11 步：`-v` 搬目录只打印一行

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s11
python main.py mv -v AI/数据/mv_demo/case/s11/dir1 AI/数据/mv_demo/case/s11/destdir
```

预期输出：

```
renamed 'AI/数据/mv_demo/case/s11/dir1' -> 'AI/数据/mv_demo/case/s11/destdir/dir1'
```

整个目录只打印**一行**，不是逐个文件。（`rm -v` 才是逐个文件打印。）

### 第 12 步：`-n` 不覆盖已存在的目标

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s12
python main.py mv -n AI/数据/mv_demo/case/s12/a.txt AI/数据/mv_demo/case/s12/b.txt
python main.py ls AI/数据/mv_demo/case/s12
```

预期输出：

```
a.txt
b.txt
destdir
dir1
emptydir
future.txt
legacy.txt
old.txt
payload.bin
```

`a.txt` 还在原地，`b.txt` 内容没变。`-n` 是**静默跳过**，退出码仍是 0——连「目录非空」那种结构性错误都不会报。

### 第 13 步：`-u` 源不够新就跳过

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s13
python main.py mv -u AI/数据/mv_demo/case/s13/old.txt AI/数据/mv_demo/case/s13/future.txt
python main.py ls AI/数据/mv_demo/case/s13
```

预期输出：

```
a.txt
b.txt
destdir
dir1
emptydir
future.txt
legacy.txt
old.txt
payload.bin
```

`old.txt` 钉在 2019 年、`future.txt` 钉在 2030 年，源不比目标新，跳过。

### 第 14 步：`-u` 源更新才搬

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s14
python main.py mv -u AI/数据/mv_demo/case/s14/future.txt AI/数据/mv_demo/case/s14/old.txt
python main.py ls AI/数据/mv_demo/case/s14
```

预期输出：

```
a.txt
b.txt
destdir
dir1
emptydir
legacy.txt
old.txt
payload.bin
```

`future.txt` 被搬成了 `old.txt`——`old.txt` 这个名字还在（内容换成了 `future.txt` 的），`future.txt` 那个名字不见了。`-u` 的判据是 `st_mtime_ns` **严格大于**（第 356 行），时间戳相等算没更新。

### 第 15 步：`-b` 覆盖前把旧目标改名备份

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s15
python main.py mv -b AI/数据/mv_demo/case/s15/a.txt AI/数据/mv_demo/case/s15/b.txt
python main.py ls AI/数据/mv_demo/case/s15
```

预期输出：

```
b.txt
b.txt~
destdir
dir1
emptydir
future.txt
legacy.txt
old.txt
payload.bin
```

旧目标没被删，改名成了 `b.txt~`。备份是**改名**不是复制，所以旧内容的 inode 直接挪过去。

### 第 16 步：`-S` 单独给就隐含开备份

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s16
python main.py mv -S .bak AI/数据/mv_demo/case/s16/a.txt AI/数据/mv_demo/case/s16/b.txt
python main.py ls AI/数据/mv_demo/case/s16
```

预期输出：

```
b.txt
b.txt.bak
destdir
dir1
emptydir
future.txt
legacy.txt
old.txt
payload.bin
```

GNU 里 `-S` 只是「改备份后缀」，单独给 `-S` 不开备份；本实现额外做了「`-S` 单独给就等于隐含开备份」（第 106 行）。**这是一个与 GNU 不同的地方**，用的时候要心里有数。

### 第 17 步：`-i` 覆盖前问一句

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s17
echo y | python main.py mv -i AI/数据/mv_demo/case/s17/a.txt AI/数据/mv_demo/case/s17/b.txt
```

预期输出：

```
mv: 覆盖 'AI/数据/mv_demo/case/s17/b.txt'?
```

提示写在**标准错误**上（不是标准输出），应答 `y` 就照搬。`-i` 只在**目标已存在**时才问；目标不存在时不问。

答完再看现场：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py ls AI/数据/mv_demo/case/s17
```

预期输出：

```
b.txt
destdir
dir1
emptydir
future.txt
legacy.txt
old.txt
payload.bin
```

### 第 18 步：`-t` 把目标目录写死

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s20
python main.py mv -t AI/数据/mv_demo/case/s20/destdir AI/数据/mv_demo/case/s20/a.txt
python main.py ls AI/数据/mv_demo/case/s20/destdir
```

预期输出：

```
a.txt
b.txt
```

给了 `-t` 之后，所有操作数都是源，源有两个也行。

### 第 19 步：`-T` 把目标当普通文件

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s21
python main.py mv -T AI/数据/mv_demo/case/s21/a.txt AI/数据/mv_demo/case/s21/destdir
```

预期输出：

```
mv: 不能用普通文件 'AI/数据/mv_demo/case/s21/a.txt' 覆盖目录 'AI/数据/mv_demo/case/s21/destdir'
```

`-T` 的意思就是「目标即使是个目录，也把它当成普通文件」。目标确实是目录，于是报「不能用普通文件覆盖目录」。

### 第 20 步：把文件移动到它自己

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s22
python main.py mv AI/数据/mv_demo/case/s22/a.txt AI/数据/mv_demo/case/s22/a.txt
```

预期输出：

```
mv: 'AI/数据/mv_demo/case/s22/a.txt' 和 'AI/数据/mv_demo/case/s22/a.txt' 是同一个文件
```

判定用 `os.path.samefile()`（比 inode），所以 `./a.txt` 这种别名、硬链接也都会被认出来。

### 第 21 步：把目录移进它自己的子目录

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s23
python main.py mv AI/数据/mv_demo/case/s23/dir1 AI/数据/mv_demo/case/s23/dir1/sub
```

预期输出：

```
mv: 不能把目录 'AI/数据/mv_demo/case/s23/dir1' 移动到它自己的子目录: 'AI/数据/mv_demo/case/s23/dir1/sub/dir1'
```

这条挡住了无限递归的搬法。注意报错里的落点已经算成了 `dir1/sub/dir1`——因为目标是目录，落点自动加了源名。

### 第 22 步：目标的父目录不存在

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s24
python main.py mv AI/数据/mv_demo/case/s24/a.txt AI/数据/mv_demo/case/s24/nodir/out.txt
```

预期输出：

```
mv: 无法把 'AI/数据/mv_demo/case/s24/a.txt' 移动到 'AI/数据/mv_demo/case/s24/nodir/out.txt': 没有那个文件或目录
```

`mv` **不会顺手建目录**（`cp` 也不会）。

### 第 23 步：二进制文件逐字节保真

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s25
python main.py mv AI/数据/mv_demo/case/s25/payload.bin AI/数据/mv_demo/case/s25/payload.moved
python main.py ls AI/数据/mv_demo/case/s25
```

预期输出：

```
a.txt
b.txt
destdir
dir1
emptydir
future.txt
legacy.txt
old.txt
payload.moved
```

`payload.moved` 是 256 字节，与原来的 `payload.bin` 逐字节相同（0~255 全字节，含 NUL）。

### 第 24 步：GBK 文件不被改写

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s26
python main.py mv AI/数据/mv_demo/case/s26/legacy.txt AI/数据/mv_demo/case/s26/legacy.moved
python main.py ls AI/数据/mv_demo/case/s26
```

预期输出：

```
a.txt
b.txt
destdir
dir1
emptydir
future.txt
legacy.moved
old.txt
payload.bin
```

`legacy.moved` 是 18 字节，和原来一样。移动不做编码转换，GBK 文件搬过去还是 GBK。

### 第 25 步：只读的目标照样能搬

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s34-readonly-b
python main.py mv AI/数据/mv_demo/case/s34-readonly-b/a.txt AI/数据/mv_demo/case/s34-readonly-b/b.txt
python main.py ls AI/数据/mv_demo/case/s34-readonly-b
```

预期输出：

```
b.txt
destdir
dir1
emptydir
future.txt
legacy.txt
old.txt
payload.bin
```

目标 `b.txt` 之前是只读的（444），照样被覆盖了。Windows 上 `rename()` 覆盖只读文件会失败，实现里先把目标的只读属性去掉（第 369~379 行）。GNU 的 `mv` 压根不看目标权限位，行为一样。

### 第 26 步：错误路径

源不存在：

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1504_prep_mv_case.py s28
python main.py mv AI/数据/mv_demo/case/s28/nosuch.txt AI/数据/mv_demo/case/s28/out.txt
```

预期输出：

```
mv: 无法访问 'AI/数据/mv_demo/case/s28/nosuch.txt': 没有那个文件或目录
```

只给一个操作数（缺目标）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py mv AI/数据/mv_demo/case/s28
```

预期输出：

```
mv: 缺少目标文件操作数: 'AI/数据/mv_demo/case/s28'
```

一个操作数都不给：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py mv
```

预期输出：

```
mv: 缺少文件操作数
```

这三条都退 2。`mv` 的用法错误是**自己判的**（`plan()` 里检查），不是 argparse 报的——所以报错文案是中文，不是 argparse 那一套英文 usage。

### 第 27 步：跑 mv 的测试

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest tests/test_mv.py 2>&1 | tail -1
```

预期输出：

```
53 passed in <T>s
```

`tests/test_mv.py` 的用例数是 53 条，覆盖正常路径、选项组合、错误路径三块。语义基线来自 GNU coreutils 8.32 的实跑对照。

## 实测出的与 GNU coreutils 8.32 的差异

本轮写了两轮差分：第一轮 `_t1501_diff_mv_gaps.py` 用 52 组用例攻前两轮差分脚本（`_t510` 的 68 组 + `_t1312` 的 10 组）没覆盖的角落，查出 13 处不一致；第二轮 `_t1502_probe_mv_defects.py` 逐条坐实。已存在的 `_t510` 68 组用例**全部一致**（本轮复跑确认，0 处不一致）。

下面 6 条是坐实后的差异。前 4 条属源码范围（开发任务可修），第 5 条是「本实现更宽松」，第 6 条是 GNU 独有能力。

### 差异一：`-i` 的应答解析与 GNU 不一致（真缺陷）

**现象**：GNU 的 `yesno()` 只看这一行的**第一个字符**是不是 `y`/`Y`；本实现是 `strip().lower()` 之后整串精确匹配 `"y"` / `"yes"`。

源码（第 288~293 行）：

```python
    def _confirm(self, dst_label: str) -> bool:
        self.ctx.stderr.write(f"mv: 覆盖 '{dst_label}'? ")
        self.ctx.stderr.flush()
        line = self.ctx.stdin.readline() if self.ctx.stdin is not None else ""
        answer = line.strip().lower()
        return answer in ("y", "yes")
```

**实测**（`_t1502` 逐条录下两边原文）：

| 应答 | GNU | 本实现 |
|---|---|---|
| `y` | 照搬 | 照搬 |
| `Y` / `yes` / `YES` | 照搬 | 照搬 |
| `yeah` | **照搬** | 跳过 |
| `yes please` | **照搬** | 跳过 |
| ` y`（前导空格） | **跳过** | 照搬 |
| `\ty`（前导制表符） | **跳过** | 照搬 |

两边的分叉是**双向**的：GNU 认「首字符是 y」的一切写法，本实现只认「整串正好是 y 或 yes」。

**根因**：`strip()` 把前导空白吃掉，`in ("y", "yes")` 又要求整串匹配。

**修法方向**：改成 `return line[:1] in ("y", "Y")`（与 `w2l/commands/rm.py` 第 424~437 行的 `confirm()` 一致——**rm.py 的写法是对的，mv.py 与 cp.py 的 `_confirm()` 用错了**）。

### 差异二：目标带尾斜杠时，本实现不认「目标必须是目录」（真缺陷）

**现象**：`mv a.txt newdir/`（`newdir` 不存在）时，GNU 报「目标必须是已存在的目录」，本实现把 `newdir` 建成一个**普通文件**。

| | GNU | 本实现 |
|---|---|---|
| 退出码 | 1 | 0 |
| 报错 | `cannot move 'a.txt' to 'newdir/': No such file or directory` | 无 |
| 落地 | `a.txt` 还在 | 变成 `newdir`（23 字节的普通文件） |

**根因**：`_resolve()`（第 303~308 行）用 `Path(operand)` 解析，pathlib 把末尾分隔符吃掉了，「尾斜杠 = 目标必须是目录」这个信号丢失。

```python
def _resolve(cwd: Path, operand: str) -> Path:
    """相对路径按运行上下文的工作目录解析（与本项目其它指令一致）。"""
    target = Path(operand)
```

**这是 `cp` 那一轮查出的同一类缺陷**（`cp` 的第 3 条：`cp a.txt newdir/` 落成普通文件），`mv` 里同款但表现不同——`cp` 落成普通文件后 GNU 报「Not a directory」什么都不创建，`mv` 则静默成功。

**修法方向**：`_resolve()` 保留尾斜杠信息，`plan()` 里据此判定「目标必须是已存在的目录」。

### 差异三：`--backup` 与 `--no-clobber` 互斥没有检查（真缺陷）

**现象**：GNU 在规划阶段就报互斥并退 1，本实现没这项检查，静默执行（`-n` 生效，什么都没搬，退出码 0）。

```
GNU: mv: options --backup and --no-clobber are mutually exclusive
本实现: （无输出，退出码 0）
```

**根因**：`plan()`（第 127 行起）没有互斥检查。`cp.py` **有**这项检查（第 198~200 行：`if self.suffix is not None and self.no_clobber`），`mv.py` 漏了。

**修法方向**：在 `plan()` 开头加与 `cp.py` 同样的检查。

### 差异四：`--no-clobber` 与 `--force` 互斥，本实现不是「后给的那个赢」（真缺陷）

**现象**：GNU 里 `-n` 与 `-f` 也互斥，同样是后给的那个赢。本实现的 `force` 与 `no_clobber` **各自独立**，`-n` 永远赢。

| 命令 | GNU | 本实现 |
|---|---|---|
| `mv -n -f a.txt b.txt` | **照搬**（`-f` 赢） | 跳过（`-n` 赢） |
| `mv -f -n a.txt b.txt` | 跳过（`-n` 赢） | 跳过 |

**根因**：`resolve_exclusive()` 只管 `interactive` 与 `no_clobber` 两个选项（第 119~123 行），`force` 不在里面。

**修法方向**：把 `force` 也纳入 `resolve_exclusive()` 的裁决集合。

### 差异五：备份目标已存在且是个目录时，本实现把它删了（真缺陷，且会丢数据）

**现象**：`-b` 时若备份名（`b.txt~`）已存在且是个目录，GNU 报「cannot backup ... Is a directory」退 1 且**不动任何东西**；本实现把那个目录**整个删掉**再改名。

| | GNU | 本实现 |
|---|---|---|
| 退出码 | 1 | 0 |
| 报错 | `cannot backup 'b.txt': Is a directory` | 无 |
| 落地 | `b.txt~/` 目录连同 `inside.txt` **都还在** | `b.txt~` 变成 13 字节的**普通文件**，目录与内容**全没了** |

**根因**：`_backup()`（第 256~257 行）在改名之前先删掉已存在的备份位：

```python
            if os.path.lexists(backup):
                _remove_path(backup)
```

`_remove_path()`（第 382~386 行）对目录走 `shutil.rmtree()`——**整个目录连内容一起删**。

**为什么这是最严重的一条**：备份位通常是用户自己的文件（`b.txt~` 是上一次备份的产物）。GNU 遇到同名目录会拒绝，本实现会**静默删掉用户的一个目录**并用文件替换它，用户连报错都看不到。

**修法方向**：备份位存在且是目录时报错退出，不删。

### 差异六：GNU 独有能力（不是缺陷，是本实现没做）

| GNU 有 | 本实现 | 说明 |
|---|---|---|
| `--backup=numbered` | argparse 报 `ignored explicit argument 'numbered'` 退 2 | 编号备份，备份名是 `b.txt.~1~`、`b.txt.~2~` |
| `--backup=none` | 同上报错 | 显式关闭备份 |
| `--backup=simple` | 同上报错 | 显式指定简单备份（等价于 `-b`） |

**根因**：`-b/--backup` 在 `build_parser()` 里是 `action="store_true"`（第 64 行），不接取值。GNU 的 `--backup` 是可选参数长选项，`--backup=numbered` 这种写法要靠解析前改写 argv 才能支持（`cp.py` 上一轮已经为 `--preserve` 做过同样的改写，见 `AI/脚本/_t1302` 的结论）。

**要不要补**：属功能取舍，不是 bug。本实现保留了「`-b` 等价于 `--backup=simple`」的常用路径。

### 附：`-v` 输出的换行符与 GNU 一致

`mv -v` 的那行输出是 `\n`（LF），与 GNU 一致——本项目的 `cli.py` 第 32~36 行给标准输出调了 `reconfigure(encoding="utf-8", errors="replace")`，没有动 `newline`。`cat.py` 与 `tail.py` 因为要输出文件原始内容，才显式 `reconfigure(newline="")`（`cat.py` 第 163 行、`tail.py` 第 511 行）。`mv` 的输出是程序自己造的文本，不涉及原始字节，所以保持平台默认即可。

## 相关教程

- `03-w2l-registry.py-指令注册表.md` — `@command` 装饰器怎么把 `mv` 注册进去
- `29-w2l-commands-cp.py-目标落点与属性保留.md` — `cp` 与 `mv` 的落点语义对照，`cp` 也有「目标带尾斜杠」的同款缺陷
- `26-w2l-commands-du.py-统计口径与去重规则.md` — Windows 上 `st_dev` / `st_ino` 的坑（`mv` 的 `_same_file()` 靠 `samefile()` 避开了它）
- `08-tests-测试怎么写怎么跑.md` — `tests/test_mv.py` 的写法
