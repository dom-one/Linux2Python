# w2l/commands/du.py — 统计口径与去重规则

`w2l/commands/du.py` 有 590 行，是 `w2l/commands/` 下中等体量的指令实现。表面上的活儿只是「统计目录占了多少字节」，真正难的是三件事：**统计的到底是什么字节数**、**同一个文件被数了几次**、**显示时怎么把字节数变成人能读的样子**。

第三个问题最容易出岔子。本轮实测查出**本实现在 `-h` 的换档边界上与 GNU coreutils 8.32 不一致**，差了一整段 24 KB 的区间——落在那段区间里，同一个字节数两边显示不同的单位。这处差异是本轮唯一一处「与 GNU 不一致」的**显示**问题，其余 15 个对拍案例逐字节一致，细节见最后一节。

## 为什么这么创建

### 决定一：默认口径就是表观大小，不是磁盘占用

GNU du 默认报的是「文件占了几个块」（按文件系统块大小向上取整），本实现默认报的是**文件字节数之和**。这不是偷懒，是 Windows 上做不到：Python 的 `os.stat_result` 没有 `st_blocks` 字段，MSYS 那个 `st_blocks` 是模拟层自己算的、跟 NTFS 的真实分配对不上。

所以本实现默认就等价于 GNU 的 `--apparent-size`。`--apparent-size` 这个选项本身保留着（命令行兼容 GNU 脚本），但写上也不改变任何行为。

代价是**默认输出与 GNU 的默认输出对不上**，这是本实现与 GNU 最大的表面差异：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du AI/数据/du_demo/tree
```

预期输出（本实现按字节数向上取整到 1K 块）：

```
0	AI/数据/du_demo/tree/empty
4	AI/数据/du_demo/tree/sub/deeper
5	AI/数据/du_demo/tree/sub
7	AI/数据/du_demo/tree
```

同样这条命令给 GNU 跑（不加 `--apparent-size`），报的是磁盘占用：

```
0	AI/数据/du_demo/tree/empty
4	AI/数据/du_demo/tree/sub/deeper
5	AI/数据/du_demo/tree/sub
11	AI/数据/du_demo/tree
```

`7` 与 `11` 的差别不是算错，是两个不同的口径。要跟 GNU 逐字节对齐，命令得写成 `du --apparent-size ...`。

### 决定二：目录自身按 0 算

目录自己的字节数一律算 0（`_scan_dir` 只累加文件的 `st_size`，目录不参与）。这跟本项目的 `find`、`tree` 是同一套口径，`tests/test_du.py` 也有对应用例：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -s AI/数据/du_demo/tree/empty
```

预期输出：

```
0	AI/数据/du_demo/tree/empty
```

### 决定三：去重的键是 `(st_dev, st_ino)`，不是路径

同一个文件被多个操作数覆盖时，只算一次。这件事由 `_claim`（第 304~317 行）管：

```python
def _claim(state, args, st) -> bool:
    key = (st.st_dev, st.st_ino)
    if args.count_links:
        return True
    if key in state.seen:
        return False
    state.seen.add(key)
    return True
```

**为什么用 inode 而不是路径？** 因为同一个文件可以有多个路径别名（硬链接、符号链接、同一个目录被写成 `tree` 和 `tree/` 两种形式）。按路径去重的话，`.` 和 `./` 会被算成两棵树。

`-l` 打开后 `_claim` 直接返回 True，每次都算。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du AI/数据/du_demo/tree AI/数据/du_demo/tree
```

预期输出（第二棵被去重掉了，不重复输出）：

```
0	AI/数据/du_demo/tree/empty
4	AI/数据/du_demo/tree/sub/deeper
5	AI/数据/du_demo/tree/sub
7	AI/数据/du_demo/tree
```

加 `-l` 之后两棵都报：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -l -s AI/数据/du_demo/tree AI/数据/du_demo/tree
```

预期输出：

```
7	AI/数据/du_demo/tree
7	AI/数据/du_demo/tree
```

### 决定四：阈值跟字节数比，不是跟块数比

`-t SIZE` 的判定在 `_passes_threshold`（第 504~513 行）：

```python
def _passes_threshold(size: int, threshold: int) -> bool:
    if threshold == 0:
        return True
    if threshold > 0:
        return size >= threshold
    return size <= -threshold
```

`size` 是字节数，不是显示时的块数。这条容易理解错：`-t 1K` 保留的是**字节数 ≥ 1024** 的条目，而不是「块数 ≥ 1」的条目。后者会把所有非空文件都留下，前者只留下至少 1 KB 的。

负阈值反过来：`-t -1K` 只留下字节数 ≤ 1024 的条目。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -t 1024 -a AI/数据/du_demo/tree
```

预期输出（`a.txt` 只有 10 字节，被滤掉；`b.txt` 有 2048 字节，留下）：

```
2	AI/数据/du_demo/tree/b.txt
4	AI/数据/du_demo/tree/sub/deeper/e.txt
4	AI/数据/du_demo/tree/sub/deeper
5	AI/数据/du_demo/tree/sub
7	AI/数据/du_demo/tree
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -t -1024 -a AI/数据/du_demo/tree
```

预期输出（反过来，`b.txt` 被滤掉）：

```
1	AI/数据/du_demo/tree/a.txt
1	AI/数据/du_demo/tree/c.txt
0	AI/数据/du_demo/tree/empty
1	AI/数据/du_demo/tree/sub/d.txt
0	AI/数据/du_demo/tree/zero.txt
```

### 决定五：`_rewrite_argv` 改写「负号开头的取值」

`-t -1K` 这种写法 argparse 取不到值——它会把 `-1K` 当成下一个选项。`_rewrite_argv`（第 133~157 行）在解析前把命令行改写成 `-t=-1K` 这种 argparse 认得的写法：

```python
_VALUE_OPTIONS = ("-d", "--max-depth", "-B", "--block-size", "-t", "--threshold")
```

只有这几个选项后面跟值。改写后 argparse 的 `type=int` 之类照常生效，而报错文案由指令自己给（`-t` 的取值非法时报「选项 '-t' 的取值无效」，而不是 argparse 默认的「expected one argument」）。

`--` 之后的参数一律不改写（`literal` 标志），所以 `du -- -t=-1K` 里的 `-t=-1K` 会被当成文件名。

### 决定六：`-h` 与 `--si` 共用一个 dest，靠命令行顺序决定进制

两个选项都往 `human_base` 里写值，后写的覆盖先写的。`_HumanAction`（第 94~103 行）就是干这个的：

```python
class _HumanAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None) -> None:
        setattr(namespace, self.dest, self.base)
        namespace.human = True
```

`-h` 传 `base="iec"`、`--si` 传 `base="si"`。所以：

- `du -h --si` → 1000 进制（`--si` 在后）
- `du --si -h` → 1024 进制（`-h` 在后）

GNU 也是这个规则。

### 决定七：`-h` 的换档用「商不超过 999」

`_format_human`（第 476~501 行）选单位的规则是：

```python
exponent = 1
divisor = base
while size > 999 * divisor:
    exponent += 1
    divisor *= base
```

意思是「一直除到商不超过 999 为止」。这个规则在 **1000 进制（`--si`）下与 GNU 完全一致**（实测 998000 / 999000 / 999001 / 1000000 / 1000001 五个点全部一致）。

**但在 1024 进制（`-h`）下与 GNU 不一致**，这是本轮查出的那处差异。GNU 的规则是「商不超过 1023」——1023 还能留在 K 档，1024 才换档。本实现的「999」是照着 1000 进制的直觉写的，换到 1024 进制就提前了一档。

尾数向上取整到一位小数这一步两边一致（`_format_human` 用整数运算 `-((-size * 10) // divisor)`，避免浮点噪声）。取整后达到 10 就改成整数显示：10239 字节是 `10K` 而不是 `9.9K`。

## 这个文件是做什么

它是 `w2l/commands/` 下的一个指令实现，590 行，职责边界是：**遍历一棵目录树，算出每个目录的字节数，按规则打印出来**。

### 数据流

```
du()                     第 233~270 行  入口：查选项冲突、定块大小、逐个操作数处理
 ├ _scan_operand()       第 278~301 行  处理一个操作数：文件直接算，目录递归进去
 │  ├ _claim()           第 304~317 行  按 (st_dev, st_ino) 去重
 │  ├ _should_follow()   第 319~328 行  -L / -H / -P 决定要不要跟随符号链接
 │  └ _scan_dir()        第 331~371 行  递归：累加子目录与文件，收集记录
 │     ├ _list_children() 第 374~402 行  读目录内容、按名字排序、按 -x 跳过别的卷
 │     │                 第 391~392 行  注释：不能用 item.stat()，Windows 上它给的是
 │     │                              目录枚举的缓存结果，st_dev 与 st_ino 全是 0
 │     └ _count_file()   第 405~426 行  统计一个普通文件的字节数
 ├ _flush()              第 434~457 行  按 -s / -d / -t 过滤，再逐条打印
 │  ├ _format_size()     第 464~468 行  字节数 → 显示文本
 │  │  ├ _blocks()      第 471~473 行  向上取整到块
 │  │  └ _format_human() 第 476~501 行  人类可读（1024 或 1000 进制）
 │  └ _passes_threshold() 第 504~513 行 阈值判定
 ├ _parse_size()         第 521~552 行  解析 SIZE（K/M/G/KB/MiB…）
 ├ _size_multiplier()    第 555~565 行  SIZE 后缀 → 倍数
 └ _resolve_block_size() 第 568~576 行  定下显示用的块大小
```

### 选项清单

| 选项 | 作用 | 备注 |
|---|---|---|
| （无） | 统计当前目录 | 操作数默认为 `.`（第 249 行） |
| （操作数） | 要统计的路径，可给多个 | 各自独立处理 |
| `-a` | 连普通文件一起列出 | |
| `-c` | 末尾多打一行 `total` | 在所有操作数之后 |
| `-s` | 每个操作数只打一行总数 | 与 `-a`、`-d N`（N>0）冲突 |
| `-d N` | 最多打印到第 N 层 | 操作数本身是第 0 层；只限制打印 |
| `-h` | 以 K/M/G 显示大小 | 1024 进制；不是 `--help` |
| `--si` | 同 `-h`，但用 1000 进制 | 单位是小写 `k` |
| `-b` | 以字节为单位显示 | |
| `-k` | 以 1K 为单位显示 | 默认值 |
| `-m` | 以 1M 为单位显示 | |
| `-B SIZE` | 以指定块大小为单位显示 | SIZE 支持 K/M/G 等后缀 |
| `-t SIZE` | 小于阈值的条目不显示 | 给负数则只显示不大于它的条目 |
| `-x` | 不跨越文件系统 | 见最后一节第 3 条 |
| `-S` | 目录大小不含子目录 | |
| `-l` | 硬链接的文件重复计入 | |
| `-L` / `-H` / `-P` | 符号链接的处理方式 | 全跟随 / 只跟命令行的 / 不跟随 |
| `--time` | 多打一列最后修改时间 | 目录取子树里最新的时间 |
| `-0` | 用 NUL 而不是换行分隔输出 | |
| `--apparent-size` | 按文件字节数统计 | 本实现默认口径，写上不改变行为 |

### 退出码

| 码 | 什么时候 |
|---|---|
| 0 | 正常 |
| 1 | 所有条目都被 `-t` 滤掉了（本项目「无结果返回 1」的约定，GNU 返回 0） |
| 2 | 用法错误（`-s` 与 `-a` 冲突、`-t` 取值非法、`-B 0`）、操作数不存在 |

## 有什么用

- **看哪棵目录树占地方**。`du -sh *` 是最常见的用法；`-d 1` 限制只看第一层，`-t` 滤掉小目录。
- **排查空间占用**。`-a` 连文件一起列，能直接看出是哪个文件大；`-S` 让目录大小不含子目录，能分清「这一层自己的文件」和「连子树一共」。
- **照抄口径实现**。它有两个值得搬走的设计：**去重用 `(st_dev, st_ino)` 而不是路径**，以及 **`_rewrite_argv` 改写负号开头的取值**。前者是硬链接去重的正解，后者是所有「选项后面跟一个可能为负的值」的指令都要处理的坑（`head.py`、`tail.py` 都做过类似的事）。

## 怎么用（过程教程）

### 第 1 步：准备演示夹具

后面的例子全部用固定夹具，不用项目源码。理由是源码会变：拿 `w2l/registry.py` 当例子，源码一改教程里写死的预期输出就全过期了。

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t900_make_du_fixture.py
```

预期输出：

```
已生成 AI/数据/du_demo/（6 个文件，合计 6259 字节）
  tree                     目录  0 字节  2024-09-25 17:15
  tree/a.txt               文件  10 字节  2024-01-15 10:30
  tree/b.txt               文件  2048 字节  2024-02-20 14:05
  tree/c.txt               文件  100 字节  2024-03-25 09:00
  tree/empty               目录  0 字节  2024-05-05 11:00
  tree/sub                 目录  0 字节  2024-08-20 13:50
  tree/sub/d.txt           文件  5 字节  2024-06-10 08:20
  tree/sub/deeper          目录  0 字节  2024-07-15 19:40
  tree/sub/deeper/e.txt    文件  4096 字节  2024-07-16 10:00
  tree/zero.txt            文件  0 字节  2024-04-30 16:45
```

夹具在 `AI/数据/du_demo/`，这个目录在 `.gitignore` 里，不进仓库。**mtime 是钉死的**（从深到浅设，否则改目录内容会把目录自己的 mtime 带偏），所以下面带 `--time` 的预期输出都稳定。

字节数刻意选在 1024 的边界两侧：`a.txt` 10 字节、`b.txt` 2048 字节、`c.txt` 100 字节、`zero.txt` 0 字节、`sub/d.txt` 5 字节、`sub/deeper/e.txt` 4096 字节，合计 6259 字节，默认 1K 块下向上取整是 7 块。

### 第 2 步：先看清默认输出长什么样

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du AI/数据/du_demo/tree
```

预期输出：

```
0	AI/数据/du_demo/tree/empty
4	AI/数据/du_demo/tree/sub/deeper
5	AI/数据/du_demo/tree/sub
7	AI/数据/du_demo/tree
```

三件事值得看：

1. **大小与路径之间是制表符**，不是空格。
2. **目录排在它自己的内容后面**（后序遍历）：`tree/sub/deeper` 在 `tree/sub` 前面，`tree/sub` 在 `tree` 前面。
3. **默认只列目录**，普通文件不列。

### 第 3 步：`-s` 只看总数

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -s AI/数据/du_demo/tree
```

预期输出：

```
7	AI/数据/du_demo/tree
```

`6259` 字节向上取整到 1K 块是 `7`。想看精确字节数用 `-b`：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -b -s AI/数据/du_demo/tree
```

预期输出：

```
6259	AI/数据/du_demo/tree
```

`-b` 是 `store_const`（把块大小定成 1），所以不取整。

### 第 4 步：`-a` 连文件一起列

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -a AI/数据/du_demo/tree
```

预期输出：

```
1	AI/数据/du_demo/tree/a.txt
2	AI/数据/du_demo/tree/b.txt
1	AI/数据/du_demo/tree/c.txt
0	AI/数据/du_demo/tree/empty
1	AI/数据/du_demo/tree/sub/d.txt
4	AI/数据/du_demo/tree/sub/deeper/e.txt
4	AI/数据/du_demo/tree/sub/deeper
5	AI/数据/du_demo/tree/sub
0	AI/数据/du_demo/tree/zero.txt
7	AI/数据/du_demo/tree
```

**同一层里按名字排序**，不是按目录原始顺序。GNU 用的是 readdir 顺序（NTFS 上是哈希序，基本随机），本实现排了名，输出才稳定——这也是对拍时能逐字节比对的前提。

### 第 5 步：`-d N` 限制打印的层数

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -d 1 AI/数据/du_demo/tree
```

预期输出：

```
0	AI/数据/du_demo/tree/empty
5	AI/数据/du_demo/tree/sub
7	AI/数据/du_demo/tree
```

`-d 0` 只打印操作数自己：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -d 0 AI/数据/du_demo/tree
```

预期输出：

```
7	AI/数据/du_demo/tree
```

**`-d` 只限制打印，不限制统计**。`-d 1` 时 `tree/sub` 显示的仍是它自己那一整棵子树的总数（`5`），不是只有它那一层的文件（`1`）。

### 第 6 步：`-t` 阈值过滤

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -t 1024 -a AI/数据/du_demo/tree
```

预期输出：

```
2	AI/数据/du_demo/tree/b.txt
4	AI/数据/du_demo/tree/sub/deeper/e.txt
4	AI/数据/du_demo/tree/sub/deeper
5	AI/数据/du_demo/tree/sub
7	AI/数据/du_demo/tree
```

`a.txt`（10 字节）、`c.txt`（100 字节）、`d.txt`（5 字节）、`zero.txt`（0 字节）都被滤掉，`b.txt`（2048 字节）留下。

注意阈值是跟**字节数**比的：`b.txt` 显示成 `2` 块，但它是按 2048 字节过的阈值。

负阈值只留不大于它的条目：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -t -1024 -a AI/数据/du_demo/tree
```

预期输出：

```
1	AI/数据/du_demo/tree/a.txt
1	AI/数据/du_demo/tree/c.txt
0	AI/数据/du_demo/tree/empty
1	AI/数据/du_demo/tree/sub/d.txt
0	AI/数据/du_demo/tree/zero.txt
```

### 第 7 步：`-h` 与 `--si` 人类可读

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -h -s AI/数据/du_demo/tree
```

预期输出：

```
6.2K	AI/数据/du_demo/tree
```

6259 字节 ÷ 1024 = 6.115，向上取整到一位小数是 `6.2`。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du --si -s AI/数据/du_demo/tree
```

预期输出：

```
6.3k	AI/数据/du_demo/tree
```

6259 ÷ 1000 = 6.259 → `6.3`。注意单位字母：`--si` 用小写 `k`，`-h` 用大写 `K`。

### 第 8 步：`-B` 自定块大小

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -B 100 -s AI/数据/du_demo/tree
```

预期输出：

```
63	AI/数据/du_demo/tree
```

6259 ÷ 100 = 62.59，向上取整是 `63` 块。`-B` 的取值走 SIZE 语法，所以 `-B 1K`、`-B 2M` 都能用。

### 第 9 步：`-S` 目录大小不含子目录

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -S -s AI/数据/du_demo/tree
```

预期输出：

```
3	AI/数据/du_demo/tree
```

只算 `tree` 这一层的文件（10 + 2048 + 100 + 0 = 2158 字节 → 3 块），不含 `sub` 子树。

### 第 10 步：`-c` 末尾加一行 total

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -s -c AI/数据/du_demo/tree
```

预期输出：

```
7	AI/数据/du_demo/tree
7	total
```

### 第 11 步：操作数是文件

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -b AI/数据/du_demo/tree/a.txt
```

预期输出：

```
10	AI/数据/du_demo/tree/a.txt
```

### 第 12 步：`--time` 多打一列时间

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du --time -a AI/数据/du_demo/tree
```

预期输出：

```
1	2024-01-15 10:30	AI/数据/du_demo/tree/a.txt
2	2024-02-20 14:05	AI/数据/du_demo/tree/b.txt
1	2024-03-25 09:00	AI/数据/du_demo/tree/c.txt
0	2024-05-05 11:00	AI/数据/du_demo/tree/empty
1	2024-06-10 08:20	AI/数据/du_demo/tree/sub/d.txt
4	2024-07-16 10:00	AI/数据/du_demo/tree/sub/deeper/e.txt
4	2024-07-16 10:00	AI/数据/du_demo/tree/sub/deeper
5	2024-08-20 13:50	AI/数据/du_demo/tree/sub
0	2024-04-30 16:45	AI/数据/du_demo/tree/zero.txt
7	2024-09-25 17:15	AI/数据/du_demo/tree
```

**目录那一行的时间是子树里最新的那个，不是目录自己的 mtime。** 看 `tree/sub/deeper` 这一行：

- 它自己的 mtime 是 `2024-07-15 19:40`（夹具里设的）
- 它里面 `e.txt` 的 mtime 是 `2024-07-16 10:00`（比目录自己还晚）
- 输出显示的是 `2024-07-16 10:00`

所以那一行取的是**子树里最新的修改时间**（含目录自身的 mtime）。GNU 也是这个口径。

这跟 `find` 的 `-newer` 语义不一样，值得记一下：`find` 比的是「某个参照文件的 mtime」，`du --time` 报的是「这一整棵子树里最新的时间戳」。

### 第 13 步：出错时的退出码

操作数不存在：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du nosuch
```

预期输出（退出码 2）：

```
du: 无法访问 'nosuch': 系统找不到指定的文件。
```

有一个不存在、其余照常统计：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du nosuch AI/数据/du_demo/tree
```

预期输出（退出码 2，错误行在前面是因为 stderr 不缓冲、stdout 重定向到管道时是块缓冲）：

```
du: 无法访问 'nosuch': 系统找不到指定的文件。
0	AI/数据/du_demo/tree/empty
4	AI/数据/du_demo/tree/sub/deeper
5	AI/数据/du_demo/tree/sub
7	AI/数据/du_demo/tree
```

选项互相矛盾：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -s -a AI/数据/du_demo/tree
```

预期输出（退出码 2）：

```
错误: 不能同时使用 '-s'（只给总数）与 '-a'（列出所有条目）
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -s -d 1 AI/数据/du_demo/tree
```

预期输出（退出码 2）：

```
错误: 不能同时使用 '-s'（只给总数）与 '--max-depth=1'
```

`-s` 等于 `--max-depth=0`，跟 `-d 1` 以上矛盾。GNU 对这个组合只警告不报错（退出码 1），本实现按用法错误处理（退出码 2）——这是有意取舍，README 第 479 行写着。

取值非法：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -t bogus AI/数据/du_demo/tree
```

预期输出（退出码 2）：

```
错误: 选项 '-t' 的取值无效: 'bogus'
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -B 0 AI/数据/du_demo/tree
```

预期输出（退出码 2）：

```
错误: 选项 '-B' 的取值无效: '0'
```

`-B 0` 会除零，所以直接拒掉。

所有条目都被阈值滤掉时按本项目约定返回 1（GNU 返回 0）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -t 1M AI/数据/du_demo/tree
```

预期输出：无输出（退出码 1）

### 第 14 步：跑相关测试

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest tests/test_du.py 2>&1 | tail -1
```

预期输出（耗时每次不同，用 `<T>` 占位）：

```
30 passed in <T>s
```

`tests/test_du.py` 里有 30 个用例，覆盖正常路径、选项组合、错误路径三块。注意命令末尾的 `| tail -1`：本项目的 `pyproject.toml` 里 `addopts = "-q"`，`pytest -q` 的输出被压成一行进度条，看不到用例数；`tail -1` 取的是最后那行汇总。

顺带看一眼收集到的用例数：

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest tests/test_du.py --collect-only -q
```

预期输出：

```
tests/test_du.py: 30
```

### 第 15 步：与 GNU coreutils 8.32 对拍

16 个案例逐条真跑比对，**15 个逐字节一致，1 个不一致**。不一致的是默认口径（见下一节），其余全部对齐。

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t901_diff_du_gnu.py
```

预期输出：

```
对照结果写入: E:\1\NULL\Windows-to-Linux\AI\数据\du_gnu_diff.txt
逐字节一致 15 例，有差异 1 例
```

### 实测出的与 GNU coreutils 8.32 的三处差异

#### 第 1 处：`-h` 的换档边界差了一整段区间

**这是本轮唯一一处「显示结果」与 GNU 不一致的地方**，其余差异都是口径或退出码的选择。

本实现选单位的规则是「商不超过 999」（第 492 行 `while size > 999 * divisor`），GNU 的规则是「商不超过 1023」。落到具体输出上：

| 字节数 | 本实现 | GNU |
|---|---|---|
| 1022975 | 999K | 999K |
| 1022976（999K） | 999K | 999K |
| 1022977（999K+1） | 1.0M | 1000K |
| 1024000 | 1.0M | 1000K |
| 1034240 | 1.0M | 1010K |
| 1046528 | 1.0M | 1022K |
| 1047551 | 1.0M | 1023K |
| 1047552（1023K） | 1.0M | 1023K |
| 1047553（1023K+1） | 1.0M | 1.0M |
| 1048576（1M） | 1.0M | 1.0M |

**不一致的区间是 [1022977, 1047552]，共 24576 字节（正好 24 KB）**。落在这段区间里，本实现显示 `1.0M`，GNU 显示 `1000K` ~ `1023K`。

根因是那个 `999` 常量：它在 1000 进制下恰好是对的（`--si` 实测五个采样点全部一致），但 1024 进制下应该用 `1023`。改法是把第 492 行的 `999` 改成 `1023`——但这只对 `-h` 生效，`--si` 还得保留 `999`，所以常量得分成两个。

这处差异**属源码范围**，本轮按只读原则没动。

#### 第 2 处：目录联接被当成普通目录钻进去

Windows 上 `mklink /J` 建的目录联接，在 Python 里 `S_ISLNK=False`、`S_ISDIR=True`（实测 `os.lstat` 的 `st_mode` 是 `0o40777`）。所以本实现把它当普通目录，**钻进去把内容算了一遍**；GNU 把它当符号链接，只报它自己占的那一块。

造一个联接看两边的差别：

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t913_make_du_junction.py
```

预期输出：

```
已生成 AI/数据/du_demo/junc/to_tree（目录联接）
  指向: AI/数据/du_demo/tree
  S_ISLNK=False  S_ISDIR=True
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py du -a AI/数据/du_demo/junc
```

预期输出（本实现钻进去了，10 行）：

```
1	AI/数据/du_demo/junc/to_tree/a.txt
2	AI/数据/du_demo/junc/to_tree/b.txt
1	AI/数据/du_demo/junc/to_tree/c.txt
0	AI/数据/du_demo/junc/to_tree/empty
1	AI/数据/du_demo/junc/to_tree/sub/d.txt
4	AI/数据/du_demo/junc/to_tree/sub/deeper/e.txt
4	AI/数据/du_demo/junc/to_tree/sub/deeper
5	AI/数据/du_demo/junc/to_tree/sub
0	AI/数据/du_demo/junc/to_tree/zero.txt
7	AI/数据/du_demo/junc/to_tree
7	AI/数据/du_demo/junc
```

GNU 同样这条命令（加 `--apparent-size` 对齐口径）只有 2 行：

```
1	AI/数据/du_demo/junc/to_tree
1	AI/数据/du_demo/junc
```

**顺带一个好消息**：自引用联接（`selfref/loop` 指向 `selfref` 自己）不会导致无限递归。实测 `du -a selfref` 稳定输出 3 行就结束——因为 `_claim` 的去重键 `(st_dev, st_ino)` 认出了第二次遇到的同一个 inode。这是 `tree.py` 那边踩过的坑（自引用联接一路递归到 64 层），`du.py` 因为有去重表所以躲过去了。

另外，符号链接（真符号链接）在本机建不了：`os.symlink` 报 `WinError 1314`（客户端没有所需的特权）。所以 `-L` / `-H` / `-P` 的行为在本机没法完整验证，README 第 487 行写着这一条。

#### 第 3 处：`-x` 挡住跨卷内容的方式是「钻进去再清空」

`-x` 的判定在 `_list_children` 第 397 行：

```python
if args.one_file_system and state.root_dev is not None and st.st_dev != state.root_dev:
    continue
```

`st` 来自 `os.stat(item.path, follow_symlinks=follow)`。这个口径跟根目录那边**不一致**：

| 调用 | 跨卷联接上的 st_dev |
|---|---|
| `os.lstat(联接)`（根目录用的口径） | C: 卷 |
| `os.stat(联接, follow_symlinks=False)`（子项用的口径） | C: 卷 |
| `os.stat(联接)`（跟随） | E: 卷（目标所在卷） |

所以**联接这一层并不会被 `-x` 挡住**（联接自己的 st_dev 与根目录相同），du 会钻进去；真正被挡住的是联接**里面的文件**——它们都在 E: 卷上，st_dev 与根目录的 C: 不同，逐个被跳过。

实测：在一个 C: 盘的目录里放一个指向 E: 盘的联接，`du -s` 报 `7`（内容算进去了），`du -s -x` 报 `0`（内容被挡住了）。

**结果是对的，代价是白走了一遍目录树。** 联接不是被「挡住」，而是被「钻进去再清空」——目录还是扫了一遍，只是里面的文件一个都没算数。

自引用联接在 `-x` 下也不会出问题：实测 `du -a selfref` 与 `du -a -x selfref` 输出完全一样（都是 3 行），因为同卷的联接根本不跨卷，而真正挡住递归的是 `_claim` 的 inode 去重。

这处差异**属源码范围**，本轮按只读原则没动。

### 常见疑问

**Q：为什么 `du` 报的数比资源管理器里看到的占用小？**

因为本实现报的是表观大小（字节数之和），资源管理器报的是「占用了多少磁盘空间」（含文件对齐、簇的大小）。GNU du 默认报后者，本实现报前者。要对齐 GNU 的默认口径得加 `--apparent-size`——但那在本实现里本来就是默认行为。

**Q：为什么目录自己不算大小？**

与本项目的 `find`、`tree` 保持一致。Windows 上目录的 `st_size` 本身就不稳定（空目录 0、条目一多变 4096），统一按 0 算结果才稳定。

**Q：`du` 和 `wc -c` 有什么区别？**

`wc -c` 统计的是**文件**的字节数（一次一个文件），`du` 统计的是**目录树**的总量，还会去重硬链接、按后序遍历输出每一级。

### 相关教程

- `teach/24-w2l-commands-find.py-表达式语法与遍历语义.md` — `find` 与 `du` 常配合用，`find` 给路径、`du` 给大小
- `teach/25-w2l-commands-tree.py-树形输出与画线规则.md` — `tree` 给层次结构、`du` 给每一层的占用；两篇都提到了目录联接的坑
- `teach/17-AGENTS.md-项目守则.md` — 退出码约定（0 成功 / 1 无结果 / 2 用法或运行错误）的出处

