# w2l/commands/find.py — 表达式语法与遍历语义

`w2l/commands/find.py` 有 905 行，是项目里最长的指令实现之一。它和别的指令最大的不同是：**find 的命令行不是「选项 + 参数」，而是一门语言**。

别的指令（`ls`、`cat`、`grep`）的参数表是平的：`ls -l -a 目录`。find 不是。find 的参数分成两截：

```
find <路径>... <表达式>
```

路径是「开头连续的、不以 `-` 开头的参数」，从第一个像选项的参数开始，后面全是表达式。表达式里有括号、`!`、`-o`，还能嵌套：

```text
find . \( -name '*.py' -o -name '*.md' \) -print
```

这一条命令要处理的东西，比 `ls` 一整页选项加起来还多：隐式 `-print` 什么时候生效、`-a` 与 `-o` 谁先算、`-prune` 算不算动作、`-delete` 会不会把目录删不干净。本实现把这套规则做成了一棵**表达式树**，再对这棵树求值。

本篇的实测依据：61 个场景与 Git Bash 的 GNU findutils 4.10 逐条对拍，60 个字节级一致；另外单独核对了 `-exec`、运算符优先级、`-printf`、`-mmin` 计数等边界。**对拍中查出的 9 处与 GNU 不一致已逐条列在文末**，其中 3 处是本实现的缺陷，不是取舍。

## 为什么这么创建

### 决定一：find 的命令行不能交给 argparse

项目里其他指令都用 argparse 建解析器。find 不行——argparse 见到 `(`、`!`、`-o`、裸参数就会报错或当成位置参数吃掉。

`_FindParser`（第 175~189 行）干脆不让 argparse 参与，只在 `--help` 时用它：

```python
class _FindParser(argparse.ArgumentParser):
    """find 的命令行不能交给 argparse。

    find 的表达式里混着括号、-o、! 和裸参数，argparse 会把它们当选项或位置参数报错，
    所以这里只在 --help 时用 argparse，其余原样把 argv 交给指令自己解析。
    """

    def parse_args(self, args=None, namespace=None):  # type: ignore[override]
        argv = list(sys.argv[1:] if args is None else args)
        if "-h" in argv or "--help" in argv:
            self.print_help()
            raise SystemExit(0)
        result = argparse.Namespace()
        result.raw_args = argv
        return result
```

`parse_args` 不做任何解析，只把 `argv` 原样塞进 `raw_args`。真正的解析在 `_split_args`（第 266~333 行）和 `_ExprParser`（第 351~422 行）里手写。

代价是这个解析器没法自动生成 `--help`，所以帮助文案是手写字符串（第 199~224 行）。代价换来的是：`find` 的行为完全由自己说了算，不会被 argparse 的「负数不是选项」「`--` 之后全是位置参数」之类的特判绊住。

### 决定二：表达式是一棵树，不是一串选项

表达式节点分五类：

| 类 | 行 | 职责 |
|---|---|---|
| `_Test` | 81~88 | 只返回真假，不产生副作用 |
| `_Action` | 91~104 | 执行副作用，恒返回真，带 `is_action` 标记 |
| `_And` | 107~119 | 与 |
| `_Or` | 122~132 | 或 |
| `_Not` | 135~142 | 非 |

`_Test` 与 `_Action` 的分家不是为了好看，而是为了让**动作能截断运算**（见决定三）。`_Action` 多了一个 `is_action = True` 的类属性，就是给 `_And` / `_Or` 判断用的。

节点统一有一个 `evaluate(item, state)` 方法。`item` 是当前待判定的文件（`_Item`，第 50~69 行），`state` 是一次运行的全局状态（`_State`，第 145~172 行）。谓词工厂（`_make_glob_test`、`_make_size_test` 这类）都返回 `Callable[[_Item, _State], bool]`，被 `_Test` 包一层。

优先级在 `_ExprParser` 里用递归下降实现（第 372~416 行）：`parse_or` → `parse_and` → `parse_not` → `parse_primary`。所以 `!` 最高、`-a` 次之、`-o` 最低，和 GNU 一样。相邻的两个谓词默认是 `-a`（`parse_and` 里的循环把缺省的连接符补上）。

### 决定三：动作要截断与运算链

这是 GNU find 最容易被忽略的一条规则：**动作恒为真，而且一旦执行过，同一层 `and` 链的右半边不再计算**。

`_And.evaluate` 就是照这条写的：

```python
def evaluate(self, item: _Item, state: "_State") -> bool:
    if not self.left.evaluate(item, state):
        return False
    if self.left.is_action:
        return True
    return self.right.evaluate(item, state)
```

为什么要这条规则？因为动作有副作用。如果 `-print` 执行完还继续算右半边，`-name '*.txt' -print -o -name '*.md' -print` 这类写法会打印出重复的内容。

实测这条规则和 GNU 完全一致（对拍场景「动作截断与链」两边都是 6 行，一字不差）。

### 决定四：`-prune` 不算动作，所以隐式 `-print` 照样生效

GNU 手册的规则是：「表达式里除了 `-prune` 或 `-print` 之外没有动作时，自动补一个 `-print`」。换句话说 **`-prune` 不算动作**。

实现里体现为 `_PRINT_SUPPRESSORS`（第 47 行）只列了会打印的动作：

```python
# 这些动作之外就不再补隐式 -print；-prune 不算（GNU 手册明确说 -prune 不算动作）
_PRINT_SUPPRESSORS = ("print", "print0", "printf", "exec", "delete")
```

`_has_print_action`（第 476~490 行）只认这五个名字。所以 `find . -type d -prune` 仍然会把命中的目录打印出来——实测 GNU 与本项目都只输出 `./sub` 一行。

### 决定五：隐式 `-print` 挂在整条表达式的末尾

`find` 函数（第 231~258 行）里补隐式 `-print` 的写法是**追加一个 `_And` 节点**，不是把表达式整个包进括号：

```python
if expression is None:
    expression = _Action(lambda item, st: st.write(item.display + "\n"), name="print")
elif not _has_print_action(expression):
    expression = _And(
        expression,
        _Action(lambda item, st: st.write(item.display + "\n"), name="print"),
    )
```

挂在末尾（而不是包住整棵树）是为了让 `-prune` 生效：`-prune` 命中的目录照样往下走 `_And` 的右半边，打印出来，但不再进入该目录。

### 决定六：`-delete` 隐含 `-depth`

`-delete` 要先删子项再删父目录，否则目录删不掉（目录非空时 `os.rmdir` 会报错）。所以函数开头有一段：

```python
if _has_delete_action(expression):
    # -delete 隐含 -depth：必须先删子项再删父目录
    options["depth"] = True
```

`_has_delete_action`（第 493~503 行）和 `_has_print_action` 是一对镜像的实现：一个查有没有打印动作，一个查有没有删除动作。

### 决定七：Windows 上 `fnmatch` 默认不区分大小写

`-name` 区分大小写、`-iname` 不区分。Python 的 `fnmatch` 有两个函数：

| 函数 | 行为 |
|---|---|
| `fnmatch.fnmatch` | 先过 `os.path.normcase`，**在 Windows 上会把大小写抹平** |
| `fnmatch.fnmatchcase` | 不做 normcase，严格区分大小写 |

本机实测：

```
fnmatch.fnmatch('B.TXT', '*.txt')      = True
fnmatch.fnmatchcase('B.TXT', '*.txt')  = False
```

所以 `-name` 必须用 `fnmatchcase`（`_make_glob_test`，第 511~520 行）：

```python
matcher = fnmatch.fnmatchcase if not ignore_case else fnmatch.fnmatch
```

直接在 Windows 上用 `fnmatch.fnmatch` 实现 `-name`，`-name '*.txt'` 会连 `B.TXT` 一起匹配上——这与 GNU 不符。

### 决定八：目录的大小按 0 算

Windows 的目录 `st_size` 不稳定：空目录是 0，条目一多就变成 4096。GNU 侧（MSYS 的 stat）看到的目录大小恒为 0。

`_effective_size`（第 546~555 行）统一按 0 处理：

```python
if item.is_dir:
    return 0
return item.st.st_size
```

这样同一条命令的结果不会随目录内容多少而变。

### 决定九：`-mmin` 的整分钟计数多 1

GNU findutils 4.10 的 `-mmin` 精确形式把「当前这一分钟」算作**第 1 分钟**，所以整分钟计数比直觉多 1。`_make_time_test`（第 569~586 行）里写死了：

```python
if minutes:
    # GNU findutils 4.10 的 -mmin 精确形式把「当前这一分钟」算作第 1 分钟，
    # 所以整分钟计数比 -mtime 的天数计数多 1（实测 90 秒的文件落在 -mmin 2）。
    count = age // 60 + 1
else:
    count = age // unit
```

实测后果：**`-mmin 0` 永远匹配不到任何东西**，刚建好的文件落在 `-mmin 1`。GNU 与本项目一致。

另外两个方向也不一样：`-mmin` 的负数是「小于等于」（`count <= number`），`-mtime` 的负数是「小于」（`count < number`）。这是 GNU 的原始口径，代码里用一行三元区分：

```python
return count <= number if minutes else count < number
```

### 决定十：`-printf` 的 `%T@` 用整数纳秒算

`%T@` 要打印「纪元以来的秒数带小数」。用浮点秒算会有二进制噪声，末几位差 1；而 Windows 的文件时间是 100 纳秒精度，浮点算出来的末位会错。

`_format_epoch`（第 667~675 行）改用整数纳秒：

```python
seconds, fraction = divmod(st.st_mtime_ns, 10**9)
return f"{seconds}.{fraction:09d}0"
```

末尾那个多出来的 `0` 是为了对齐实测：GNU findutils 4.10 的 MSYS 构建小数点后印 10 位（纳秒被算大了 10 倍）。

另外，单独的 `%T` 在 GNU 那边会直接崩（报 `memory exhausted`），所以本实现只支持 `%T@`。

### 决定十一：路径统一用正斜杠

Windows 的路径分隔符是反斜杠。`_run_operand`（第 789~803 行）和 `_child_display`（第 846~849 行）把显示用的路径统一成 `/`：

```python
display = operand.replace("\\", "/")
```

但**文件系统访问用的路径保持原样**（`fs_path`），两套路径分开存：`_Item` 里 `display` 给用户看，`fs_path` 给 `os` 用。

### 决定十二：`-exec` 在 Windows 上退回 `cmd /c`

GNU 直接 fork/exec 目标程序，不经过 shell。Windows 上 `echo`、`dir`、`type` 是 cmd 的内建命令，没有对应的可执行文件。

`_run_command`（第 749~769 行）先按可执行文件找，找不到才退回 `cmd /c`：

```python
try:
    subprocess.run(args, check=False)
except FileNotFoundError:
    if os.name != "nt":
        state.ctx.stderr.write(f"find: 无法执行 '{args[0]}': 没有那个文件或目录\n")
        state.had_error = True
        return
    try:
        subprocess.run(["cmd", "/c", subprocess.list2cmdline(args)], check=False)
    except OSError as exc:
        ...
```

退回时整条命令必须作为**一个**参数交给 cmd。拆成多个参数时 cmd 会按自己的编码重新拼命令行，中文路径会变成 GBK 字节；合成一个字符串则原样透传 UTF-8。

补充一点本机的实际情况：`where echo` 显示 `E:\software\Git\Git\usr\bin\echo.exe` 排在前面，所以 `echo` 在本机会先命中 Git 自带的可执行文件，**根本走不到 `cmd /c` 这条回退分支**。

### 决定十三：退出码按项目约定

| 情况 | GNU find 4.10 | 本项目 |
|---|---|---|
| 成功且有结果 | 0 | 0 |
| 什么都不匹配 | 0 | **1** |
| 用法错误 / 运行错误 | 1 | **2** |

「无结果返回 1」是本项目「命中类指令」的统一约定（`grep`、`wc` 等同理）。

但「有没有结果」是按**表达式是否命中**算的，不是按打印了几行算的。`find` 函数末尾的注释写明了这一点：

```python
# 「有没有结果」按表达式是否命中来算，而不是按打印了几行：
# -delete 这种只做动作不打印的用法，命中的文件照样算结果。
return 0 if state.matched else 1
```

所以 `find . -name '*.tmp' -delete` 删掉了文件但一行都没打印，退出码仍是 0。

## 这个文件是做什么

### 文件规模与段落分布

| 段落 | 行范围 | 行数 | 占比 |
|---|---|---|---|
| 模块文档、导入、常量 | 1~49 | 49 | 5.4% |
| 表达式节点类（`_Item` / `_Test` / `_Action` / `_And` / `_Or` / `_Not`） | 50~142 | 93 | 10.3% |
| 运行状态与解析器（`_State` / `_FindParser`） | 145~189 | 45 | 5.0% |
| 入口（`build_parser` / `find`） | 192~258 | 67 | 7.4% |
| 命令行拆分（`_split_args` / `_parse_depth`） | 266~343 | 78 | 8.6% |
| 表达式解析（`_ExprParser` / `_build_leaf` / 动作检测） | 351~503 | 153 | 16.9% |
| 谓词（`-name` / `-type` / `-size` / `-mtime` / `-newer` / `-empty`） | 511~624 | 114 | 12.6% |
| 动作（`-printf` / `-exec` / `-delete`） | 632~781 | 150 | 16.6% |
| 遍历（`_walk` / `_walk_children` / `_evaluate`） | 789~862 | 74 | 8.2% |
| 辅助（`_parse_number_spec` / `_compare`） | 870~905 | 36 | 4.0% |

表达式解析与动作两段合计 303 行，占 33.5%——这个文件的一半难度在这两处。

### 关键函数速查

| 函数 | 行 | 干什么 |
|---|---|---|
| `build_parser()` | 192 | 只负责 `--help`，其余原样放行 |
| `find(args, ctx)` | 231 | 入口：拆参数 → 解析表达式 → 补隐式 `-print` → 遍历 → 定退出码 |
| `_split_args(argv)` | 266 | 拆成「全局选项 / 路径 / 表达式记号」 |
| `_parse_depth(value, name)` | 336 | 解析 `-maxdepth` / `-mindepth` 的非负整数 |
| `_ExprParser` | 351 | 递归下降解析表达式，优先级 `!` > `-a` > `-o` |
| `_build_leaf(parser, token)` | 429 | 把一个谓词记号变成节点，是谓词的总入口 |
| `_has_print_action(node)` | 476 | 判断要不要补隐式 `-print` |
| `_has_delete_action(node)` | 493 | 判断要不要隐含 `-depth` |
| `_make_glob_test(option, pattern)` | 511 | `-name` / `-iname` / `-path` / `-ipath` |
| `_make_regex_test(option, pattern)` | 523 | `-regex` / `-iregex` |
| `_make_type_test(kind)` | 536 | `-type f/d/l` |
| `_effective_size(item)` | 546 | 文件大小，目录一律按 0 |
| `_make_size_test(spec)` | 558 | `-size N[cwkMG]`，向上取整 |
| `_make_time_test(spec, unit, minutes)` | 569 | `-mtime` / `-mmin` |
| `_make_newer_test(reference)` | 589 | `-newer FILE` |
| `_make_empty_test(item, state)` | 612 | `-empty` |
| `_make_prune_action(item, state)` | 622 | `-prune` |
| `_make_printf_action(fmt)` | 632 | `-printf` |
| `_format_printf(fmt, item)` | 640 | 解析 printf 格式串 |
| `_format_epoch(st)` | 667 | `%T@` 的整数纳秒换算 |
| `_printf_directive(directive, item)` | 678 | `%p` `%f` `%h` `%s` `%y` `%T@` `%t` `%%` |
| `_make_exec_action(parser)` | 701 | 解析 `-exec CMD ;` / `-exec CMD +` |
| `_expand_placeholder(command_args, paths, uses_placeholder)` | 737 | 展开 `{}` |
| `_run_command(args, state)` | 749 | 执行 `-exec` 的命令，Windows 上退回 `cmd /c` |
| `_make_delete_action(item, state)` | 772 | `-delete` |
| `_run_operand(operand, ...)` | 789 | 从一个操作数出发遍历 |
| `_walk(item, ...)` | 806 | 先序遍历；`-depth` 改成后序 |
| `_walk_children(item, ...)` | 817 | 列目录项并逐个下钻 |
| `_walk_children_first(item, ...)` | 840 | 后序遍历的「先子项后自己」 |
| `_evaluate(item, ...)` | 852 | 判定一个文件，处理 `mindepth` |
| `_parse_number_spec(spec, option)` | 870 | 解析 `+N` / `-N` / 单位后缀 |
| `_compare(op, left, right)` | 900 | 比较三个操作符 |

### 入口点

```python
@command("find", "在目录树中按条件查找文件（GNU find 风格子集）", build_parser)
def find(args: argparse.Namespace, ctx: RunContext) -> int:
```

`@command` 装饰器把它注册进 `w2l/registry.py`，`main.py` 通过 `python main.py find ...` 调用。

### 相关文件

| 文件 | 关系 |
|---|---|
| `w2l/registry.py` | 注册表，`@command` 最终写进这里 |
| `w2l/context.py` | `RunContext`，带 `cwd` / `stdout` / `stderr` / `stdin` |
| `w2l/errors.py` | `UsageError`，本文件的用法错误都抛这个 |
| `w2l/entry.py` | `command_prog("find")`，决定帮助文案里显示 `python main.py find` 还是 `dmlinux find` |
| `tests/test_find.py` | 335 行，37 个用例 |
| `README.md` | 「find 能力清单」一节（第 319~375 行） |

## 有什么用

### 能做的

- 按文件名、路径、正则筛文件：`-name` / `-iname` / `-path` / `-ipath` / `-regex` / `-iregex`
- 按类型筛：`-type f`（普通文件）、`-type d`（目录）、`-type l`（符号链接）
- 按大小筛：`-size N[cwkMG]`，默认 512 字节块，支持 `+N` / `-N`
- 按时间筛：`-mtime` / `-mmin` / `-newer FILE`
- 按内容状态筛：`-empty`（空文件或空目录）
- 组合条件：`-a` / `-o` / `!` / `-not` / `( )`，优先级 `!` > `-a` > `-o`
- 控制遍历：`-maxdepth` / `-mindepth` / `-depth` / `-prune`
- 控制输出：`-print` / `-print0` / `-printf FORMAT`
- 对结果做事：`-exec CMD ;` / `-exec CMD +` / `-delete`

### 不能做的

- **只认 `-type f` / `d` / `l`**：块设备、字符设备、FIFO 在 Windows 上不存在
- **`-H` / `-L` / `-P` 只兼容接收，不改行为**：Windows 上建符号链接要管理员权限（`os.symlink` 报 WinError 1314），符号链接目录遍历的收益远小于引入环路风险
- **没有 `-mtime` 以外的精细时间谓词**：没有 `-newermt`、`-newerXY`、`-amin`、`-cmin`
- **没有 `-links` / `-user` / `-group` / `-perm`**：Windows 上取不到这些信息
- **`-printf` 只支持 8 个指令**：`%p` `%f` `%h` `%s` `%y` `%T@` `%t` `%%`，不认识的按字面量原样输出
- **没有 `-ok` / `-okdir`**：交互确认类谓词一个没做
- **`-exec` 的 `{}` 展开有缺陷**：见文末「与 GNU 的差异」

## 怎么用（过程教程）

### 第 1 步：准备演示夹具

后面的例子全部用固定夹具，不用项目源码。理由是源码会变：拿 `w2l/registry.py` 当例子，源码一改教程里写死的预期输出就全过期了。

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t700_make_find_demo.py
```

预期输出：

```
已生成 AI/数据/find_demo/（14 个条目）
```

夹具清单：

| 路径 | 内容 | 字节 |
|---|---|---|
| `a.txt` | `hello\n` | 6 |
| `B.txt` | `upper\n` | 6 |
| `notes.md` | `# t\n` | 4 |
| `empty.log` | 空文件 | 0 |
| `.hidden` | `x\n` | 2 |
| `old.txt` | `old\n`，mtime 设为 10 天前 | 4 |
| `big.bin` | 2000 个 `X` | 2000 |
| `sub/deep.txt` | `deep\n` | 5 |
| `sub/code.py` | `print(1)\n` | 9 |
| `sub/empty_dir/` | 空目录 | — |
| `sub2/nested.txt` | `nested\n` | 7 |

夹具落在 `AI/数据/find_demo/`，这个目录在 `.gitignore` 里，不进仓库。

### 第 2 步：先看清这个文件有多大

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat w2l/commands/find.py | wc -l
```

预期输出：

```
905
```

### 第 3 步：不给表达式就打印全部

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo
```

预期输出：

```
AI/数据/find_demo
AI/数据/find_demo/.hidden
AI/数据/find_demo/a.txt
AI/数据/find_demo/B.txt
AI/数据/find_demo/big.bin
AI/数据/find_demo/empty.log
AI/数据/find_demo/notes.md
AI/数据/find_demo/old.txt
AI/数据/find_demo/sub
AI/数据/find_demo/sub/code.py
AI/数据/find_demo/sub/deep.txt
AI/数据/find_demo/sub/empty_dir
AI/数据/find_demo/sub2
AI/数据/find_demo/sub2/nested.txt
```

路径用正斜杠，与 GNU 一致。顺序是目录项的原始顺序（`readdir` 顺序），先序遍历：先打印自己，再往下走。

### 第 4 步：`-name` 区分大小写

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -name '*.txt'
```

预期输出：

```
AI/数据/find_demo/a.txt
AI/数据/find_demo/B.txt
AI/数据/find_demo/old.txt
AI/数据/find_demo/sub/deep.txt
AI/数据/find_demo/sub2/nested.txt
```

`B.txt` 被匹配上了，因为它的小写形式 `b.txt` 符合 `*.txt`——匹配的是**整个文件名**，`*` 可以吃掉 `B` 那一段。

换个大小写就一个都不剩：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -name '*.TXT'
```

预期输出：

```
```

（空。退出码是 1——什么都不匹配是本项目的约定，不是 0。）

注意这里**退出码是 1**（什么都不匹配），不是 0。这是本项目的约定。

### 第 5 步：`-iname` 忽略大小写

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -iname '*.TXT'
```

预期输出：

```
AI/数据/find_demo/a.txt
AI/数据/find_demo/B.txt
AI/数据/find_demo/old.txt
AI/数据/find_demo/sub/deep.txt
AI/数据/find_demo/sub2/nested.txt
```

### 第 6 步：`-type` 分目录和普通文件

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -type d
```

预期输出：

```
AI/数据/find_demo
AI/数据/find_demo/sub
AI/数据/find_demo/sub/empty_dir
AI/数据/find_demo/sub2
```

换成 `-type f` 就只剩普通文件：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -type f
```

预期输出：

```
AI/数据/find_demo/.hidden
AI/数据/find_demo/a.txt
AI/数据/find_demo/B.txt
AI/数据/find_demo/big.bin
AI/数据/find_demo/empty.log
AI/数据/find_demo/notes.md
AI/数据/find_demo/old.txt
AI/数据/find_demo/sub/code.py
AI/数据/find_demo/sub/deep.txt
AI/数据/find_demo/sub2/nested.txt
```

隐藏文件也在里面——find 不像 shell 的通配符那样默认跳过点文件。

### 第 7 步：`-size` 的 512 字节块

`-size` 不带单位时按 512 字节块算，而且**向上取整**。6 字节的文件占 1 块：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -size 1
```

预期输出：

```
AI/数据/find_demo/.hidden
AI/数据/find_demo/a.txt
AI/数据/find_demo/B.txt
AI/数据/find_demo/notes.md
AI/数据/find_demo/old.txt
AI/数据/find_demo/sub/code.py
AI/数据/find_demo/sub/deep.txt
AI/数据/find_demo/sub2/nested.txt
```

`empty.log` 是 0 字节，占 0 块，不在结果里；`big.bin` 是 2000 字节，占 4 块，也不在。

加 `c` 后缀就是精确字节数：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -size 6c
```

预期输出：

```
AI/数据/find_demo/a.txt
AI/数据/find_demo/B.txt
```

`+N` 是「大于 N」：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -size +6c
```

预期输出：

```
AI/数据/find_demo/big.bin
AI/数据/find_demo/sub/code.py
AI/数据/find_demo/sub2/nested.txt
```

`sub/code.py` 是 9 字节、`sub2/nested.txt` 是 7 字节，都大于 6。

### 第 8 步：`-empty` 认空目录

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -empty
```

预期输出：

```
AI/数据/find_demo/empty.log
AI/数据/find_demo/sub/empty_dir
```

空文件与空目录都算。目录是不是空，代码用 `os.scandir` 实际扫一遍来判断（第 612~619 行），不是看 `st_size`。

### 第 9 步：`-o` 与括号

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -name '*.md' -o -name '*.py'
```

预期输出：

```
AI/数据/find_demo/notes.md
AI/数据/find_demo/sub/code.py
```

加括号把整个或运算括起来（bash 里 `(` 要转义成 `\(`）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo \( -name '*.md' -o -name '*.py' \)
```

预期输出：

```
AI/数据/find_demo/notes.md
AI/数据/find_demo/sub/code.py
```

这里加不加括号结果一样，因为整个表达式只有这一个或运算。真正能看出区别的例子是第 10 步。

### 第 10 步：`-a` 的优先级高于 `-o`

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -type f -name '*.txt' -o -name '*.md'
```

预期输出：

```
AI/数据/find_demo/a.txt
AI/数据/find_demo/B.txt
AI/数据/find_demo/notes.md
AI/数据/find_demo/old.txt
AI/数据/find_demo/sub/deep.txt
AI/数据/find_demo/sub2/nested.txt
```

这条命令按优先级解析成 `(-type f -a -name '*.txt') -o (-name '*.md')`：前一段命中 5 个 `.txt` 文件，后一段命中 `notes.md`。如果 `-o` 优先级更高，就会变成 `-type f -a (-name '*.txt' -o -name '*.md')`，结果里不会有 `notes.md`（它是文件但不是 `.txt`）——正好能从结果里看出差别。

`!` 优先级最高：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo ! -name '*.txt'
```

预期输出：

```
AI/数据/find_demo
AI/数据/find_demo/.hidden
AI/数据/find_demo/big.bin
AI/数据/find_demo/empty.log
AI/数据/find_demo/notes.md
AI/数据/find_demo/sub
AI/数据/find_demo/sub/code.py
AI/数据/find_demo/sub/empty_dir
AI/数据/find_demo/sub2
```

### 第 11 步：`-prune` 只挡下降

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -type d -name sub -prune -o -print
```

预期输出：

```
AI/数据/find_demo
AI/数据/find_demo/.hidden
AI/数据/find_demo/a.txt
AI/数据/find_demo/B.txt
AI/数据/find_demo/big.bin
AI/数据/find_demo/empty.log
AI/数据/find_demo/notes.md
AI/数据/find_demo/old.txt
AI/数据/find_demo/sub2
AI/数据/find_demo/sub2/nested.txt
```

`sub` 目录**本身没有出现在结果里**，它的子项也没有——`-prune` 命中后不再进入该目录，而且这个目录自己也不再往下走。

但注意 `-prune` 不算动作，所以隐式 `-print` 还在。写成 `-type d -name sub -prune`（不带 `-o -print`）时，命中的目录会被打印出来：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -type d -name sub -prune
```

预期输出：

```
AI/数据/find_demo/sub
```

这与 GNU 完全一致。

### 第 12 步：`-maxdepth` 与 `-mindepth`

操作数本身是第 0 层。`-maxdepth 0` 只剩操作数自己：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -maxdepth 0
```

预期输出：

```
AI/数据/find_demo
```

`-maxdepth 1` 多一层：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -maxdepth 1
```

预期输出：

```
AI/数据/find_demo
AI/数据/find_demo/.hidden
AI/数据/find_demo/a.txt
AI/数据/find_demo/B.txt
AI/数据/find_demo/big.bin
AI/数据/find_demo/empty.log
AI/数据/find_demo/notes.md
AI/数据/find_demo/old.txt
AI/数据/find_demo/sub
AI/数据/find_demo/sub2
```

`-mindepth` 反过来，比 N 层浅的不参与判定（但仍然会被遍历下去）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -mindepth 2
```

预期输出：

```
AI/数据/find_demo/sub/code.py
AI/数据/find_demo/sub/deep.txt
AI/数据/find_demo/sub/empty_dir
AI/数据/find_demo/sub2/nested.txt
```

### 第 13 步：`-depth` 改成后序

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -depth -type d
```

预期输出：

```
AI/数据/find_demo/sub/empty_dir
AI/数据/find_demo/sub
AI/数据/find_demo/sub2
AI/数据/find_demo
```

先子项后父项，操作数自己排在最后。

### 第 14 步：`-print0` 用 NUL 分隔

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -name '*.md' -print0 | od -c | tail -2
```

预期输出：

```
0000020   e   m   o   /   n   o   t   e   s   .   m   d  \0
0000035
```

末尾是 `\0` 而不是换行。这样路径里有换行符也不会把一条记录拆成两行。

### 第 15 步：`-printf` 按格式打印

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -name '*.md' -printf '%f|%s|%y\n'
```

预期输出：

```
notes.md|4|f
```

`%f` 是文件名、`%s` 是字节数、`%y` 是类型（`f` 文件 / `d` 目录）。`%h` 是所在目录：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -name '*.txt' -printf '%h\n'
```

预期输出：

```
AI/数据/find_demo
AI/数据/find_demo
AI/数据/find_demo
AI/数据/find_demo/sub
AI/数据/find_demo/sub2
```

### 第 16 步：`-exec` 的两种终止符

`;` 每个文件跑一次：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -name '*.md' -exec echo {} \;
```

预期输出：

```
AI/数据/find_demo/notes.md
```

`+` 攒成一批跑一次（这条只有一个匹配，看不出差别）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -name '*.md' -exec echo {} +
```

预期输出：

```
AI/数据/find_demo/notes.md
```

bash 里 `\;` 里的反斜杠是给 bash 看的——它会把 `\;` 变成 `;` 再交给 find。写 `\;` 而不是 `;`，是因为不转义的话 bash 会把 `;` 当命令分隔符。

### 第 17 步：`-delete` 隐含 `-depth`

先造一个可丢弃的小目录：

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t707_make_delete_demo.py && python main.py find AI/数据/find_delete_demo -name '*.tmp' -delete && python main.py find AI/数据/find_delete_demo -type f
```

预期输出：

```
已生成 AI/数据/find_delete_demo/（4 个文件）
AI/数据/find_delete_demo/keep.txt
AI/数据/find_delete_demo/sub/keep2.txt
```

两个 `.tmp` 文件被删掉了，剩下的只有 `.txt`。中间那条 `-delete` **一行都没打印**——`-delete` 算动作，隐式 `-print` 被抑制了；但因为表达式命中了，退出码仍是 0。

### 第 18 步：`-mtime` 与 `-mmin`

`-mtime +9` 找 9 天前改过的：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -type f -mtime +9
```

预期输出：

```
AI/数据/find_demo/old.txt
```

`-mmin` 的计数有个反直觉的地方：**当前这一分钟算第 1 分钟**，所以 `-mmin 0` 永远匹配不到东西。造一个刚建好的文件看：

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t708_make_mtime_demo.py && python main.py find AI/数据/find_mtime_demo -type f -mmin 1
```

预期输出：

```
已生成 AI/数据/find_mtime_demo/just_now.txt（mtime = 当前时间）
AI/数据/find_mtime_demo/just_now.txt
```

同一个文件用 `-mmin 0` 就找不到了：

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t708_make_mtime_demo.py && python main.py find AI/数据/find_mtime_demo -type f -mmin 0
```

预期输出：

```
已生成 AI/数据/find_mtime_demo/just_now.txt（mtime = 当前时间）
```

### 第 19 步：`-newer` 比参照文件新

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -type f -newer AI/数据/find_demo/old.txt
```

预期输出：

```
AI/数据/find_demo/.hidden
AI/数据/find_demo/a.txt
AI/数据/find_demo/B.txt
AI/数据/find_demo/big.bin
AI/数据/find_demo/empty.log
AI/数据/find_demo/notes.md
AI/数据/find_demo/sub/code.py
AI/数据/find_demo/sub/deep.txt
AI/数据/find_demo/sub2/nested.txt
```

`old.txt` 自己的 mtime 是 10 天前，其余文件都是刚建的，所以只有它被排除。`-newer` 的参照文件按当前工作目录解析相对路径。

### 第 20 步：出错的路径

未知谓词：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -没有这个谓词
```

预期输出：

```
错误: 未知谓词 '-没有这个谓词'
```

操作数不存在：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/没有这个目录
```

预期输出：

```
find: 无法访问 'AI/数据/没有这个目录': 系统找不到指定的文件。
```

路径写在表达式后面：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -name '*.md' 多余的操作数
```

预期输出：

```
错误: 路径必须写在表达式前面：'多余的操作数'
```

括号没闭合：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo \( -name '*.txt'
```

预期输出：

```
错误: 表达式无效：期待 ')' 但没有找到
```

`-type` 的取值非法：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -type x
```

预期输出：

```
错误: -type 的参数无效：'x'（本实现支持 f 普通文件、d 目录、l 符号链接）
```

注意错误文案说的是「支持 f、d、l」三个，但 `--help` 里写的是「`-type [fd]`」。帮助文案漏了 `l`。

### 第 21 步：跑相关测试

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest tests/test_find.py 2>&1 | tail -1
```

预期输出（耗时每次不同，用 `<T>` 占位）：

```
37 passed in <T>s
```

### 第 22 步：确认整体没坏

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest 2>&1 | tail -1
```

预期输出（耗时每次不同，用 `<T>` 占位）：

```
537 passed in <T>s
```

### 与 GNU findutils 4.10 的差异

61 个场景对拍，60 个字节级一致。下面 9 条是查出来的差异，其中**标「缺陷」的三条是本实现的问题，不是取舍**。

| 场景 | GNU find 4.10 | 本项目 | 性质 |
|---|---|---|---|
| `-exec CMD ;`（命令里没有 `{}`） | 命令原样跑，**不追加路径** | 把匹配到的路径追加到命令末尾 | 差异 |
| `-exec CMD +`（命令里没有 `{}`） | 报 `missing argument to \`-exec'`，退出码 1 | 接受，路径追加到末尾 | 差异 |
| `-exec` 的 `{}` 夹在参数中间（`A{}B`） | 就地替换成 `A<路径>B` | 只输出路径，`A` 和 `B` 丢了 | **缺陷** |
| 一个参数里有多个 `{}`（`{}={}`） | 每个 `{}` 都替换 | 只替换第一个 | **缺陷** |
| `-o` 左分支是裸动作（`-print -o -name ... -print`） | 左边执行过就短路，右边不再跑 | 右边还会跑，命中项**打印两遍** | **缺陷** |
| `-printf` 遇到不认识的指令 | stderr 给一条警告，指令原样输出 | 静默原样输出 | 差异 |
| 用法错误 / 运行错误 | 退出码 1 | 退出码 2 | 项目约定 |
| 什么都不匹配 | 退出码 0 | 退出码 1 | 项目约定 |
| 输出接到管道里 | LF | **CRLF** | **缺陷** |

#### 三条缺陷的根因

**一、`{}` 展开丢字**。`_expand_placeholder`（第 737~746 行）把整个参数替换掉了：

```python
def _expand_placeholder(command_args: list[str], paths: list[str], uses_placeholder: bool) -> list[str]:
    if uses_placeholder:
        expanded: list[str] = []
        for arg in command_args:
            if "{}" in arg:
                expanded.extend(path for path in paths)
            else:
                expanded.append(arg)
        return expanded
    return list(command_args) + list(paths)
```

`"A{}B"` 走 `expanded.extend(...)` 分支，结果只剩路径本身。正确写法应该是把 `{}` 两侧的文本保留下来、只替换占位符本身。

**二、`_Or` 的动作短路漏了一条**。`_Or.evaluate`（第 129~132 行）：

```python
def evaluate(self, item: _Item, state: "_State") -> bool:
    if self.left.evaluate(item, state) and not self.left.is_action:
        return True
    return self.right.evaluate(item, state)
```

左分支是**裸动作**（`_Action` 本身）时，`left.is_action` 为真，`not left.is_action` 为假，于是掉下去把右半边也算了。GNU 的规则是「左半边执行过动作就整条为真」，右半边不该再跑。实测 `-print -o -name '*.md' -print` 本项目把 `notes.md` 打印了两遍，GNU 只打一遍。

对比之下 `_And` 的写法是对的：动作在**左半边**时直接返回，不再算右半边。`_Or` 少的就是这个分支。

**三、管道里是 CRLF**。`w2l/commands/tail.py`（第 502~508 行）和 `w2l/commands/cat.py`（第 154~160 行）都做了这件事：

```python
reconfigure = getattr(ctx.stdout, "reconfigure", None)
if reconfigure is not None:
    reconfigure(errors="surrogateescape")
    reconfigure(newline="")
```

`newline=""` 关掉的是 Windows 文本模式把 `\n` 翻成 `\r\n` 的行为。**find.py 没做这一步**，所以它的输出接到管道里会多一个 `\r`。实测对照：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py find AI/数据/find_demo -name '*.md' | od -c | tail -2
```

预期输出：

```
0000020   e   m   o   /   n   o   t   e   s   .   m   d  \r  \n
0000036
```

GNU 同样命令是 LF：

```bash
cd E:\1\NULL\Windows-to-Linux
find AI/数据/find_demo -name '*.md' | od -c | tail -2
```

预期输出：

```
0000020   e   m   o   /   n   o   t   e   s   .   m   d  \n
0000035
```

多出来的 `\r` 会让 `grep -x`、`$(...)` 比较之类的操作对不上。

### 一条容易踩的环境坑

上面第二条命令用的是裸 `find`，那 **只在 Git Bash 里才是 GNU find**。在 cmd.exe 或 PowerShell 里，`find` 是 Windows 自带的文本搜索命令（`find /i "abc" file.txt`），跟 GNU find 完全是两回事，参数也不一样。本项目的指令一律要走 `python main.py find ...`。

### 常见疑问

**Q：路径为什么必须写在表达式前面？**

因为 find 的参数表是「路径在前、表达式在后」的两段式，GNU 就是这么定的。路径是开头连续的、不以 `-` 开头且不是 `(` / `!` 的参数；从第一个像选项的参数开始就算表达式。路径写在表达式后面会报「路径必须写在表达式前面」。

**Q：`find .` 和 `find` 有什么区别？**

没给路径时默认用当前目录，输出是 `./xxx` 的形式（操作数是 `.`）。显式写 `find .` 也是一样的。

**Q：`-maxdepth` 写在路径后面还有效吗？**

有效。`_split_args` 扫完路径之后还会继续认 `-maxdepth` / `-mindepth` / `-depth`（第 318~331 行），GNU 也是这个行为。

**Q：`-prune` 后面要不要跟 `-o -print`？**

两种写法都行，行为不同：

- `find . -type d -name sub -prune -o -print`：命中的目录**不打印**（因为 `-o -print` 这一侧接管了打印），只打印别的
- `find . -type d -name sub -prune`：命中的目录**会打印**（`-prune` 不算动作，隐式 `-print` 还在）

**Q：为什么 `-mmin 0` 什么都找不到？**

GNU findutils 4.10 把「当前这一分钟」算作第 1 分钟，所以整分钟计数最小是 1，`-mmin 0` 匹配不到任何东西。本项目按同样的口径实现。刚建好的文件用 `-mmin 1` 找。

**Q：`-delete` 删掉了文件但一行都没打印，是没生效吗？**

生效了。`-delete` 算动作，隐式 `-print` 被抑制，所以不打印。但「有没有结果」是按表达式是否命中算的，命中了退出码就是 0。

**Q：`find` 的输出能直接接管道吗？**

能，但注意本项目的 find 在管道里输出的是 **CRLF**（见「与 GNU 的差异」第三条），比 GNU 多一个 `\r`。做精确匹配前先 `tr -d '\r'`，或者等这个缺陷修掉。

### 相关教程

- `teach/07-w2l-commands-grep.py-检索实现.md`——另一个「自己解析表达式」的指令，可以对照着看
- `teach/13-新增一个指令的完整过程.md`——加一个新指令要动哪些文件
- `teach/23-w2l-commands-tail.py-起点语义与跟随模式.md`——`tail` 里 `reconfigure(newline="")` 那段，find 缺的就是它
