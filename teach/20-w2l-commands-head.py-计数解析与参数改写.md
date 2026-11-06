# w2l/commands/head.py — 计数解析与参数改写

`w2l/commands/head.py` 有 642 行，是项目里最绕的一个指令实现。它要回答的问题只有一个：**`-n` 后面那个数字，到底是什么意思？**

GNU head 的计数语法有四层——正负号、数字、乘数后缀、还有紧凑写法——每一层都能改变含义：

| 写法 | 实际含义 | 容易误解成 |
|---|---|---|
| `-n 5` | 前 5 行 | — |
| `-n -5` | 除末 5 行之外的全部 | 末 5 行（这是 `tail` 的意思） |
| `-n +5` | 前 5 行 | 从第 5 行开始（这也是 `tail` 的意思） |
| `-n 0` | 一行都不要 | — |
| `-n -0` | 全部 | 一行都不要 |
| `-n 1b` | 512 **行** | 512 字节 |
| `-c 1b` | 512 字节 | — |
| `-3` | 前 3 行（紧凑写法） | — |

再加上 argparse 根本不认 `-3`（实测它把 `-3` 当成位置参数），这个文件里有一整套自己实现的参数改写与计数解析。

## 为什么这么创建

### 决定一：计数语法必须自己解析

argparse 只负责「`-n` 这个选项需要一个值」，值是字符串。字符串 `1b`、`-5`、`+3` 各自代表什么，argparse 一概不管。

GNU head 的计数表达式是三段拼起来的一个整体：

```
[符号] [数字] [乘数后缀]
  +      5        b
```

`_NUMBER_RE` 一次就把三段拆出来：

```python
_NUMBER_RE = re.compile(r"[+-]?(\d+)(b|[kKmMGTPEZY](?:B|iB)?)?$")
```

三个捕获组分别是：符号（`[+-]?` 可选）、数字（`\d+`）、后缀（`b` 或者字母加可选的 `B`/`iB`）。后缀那一段写成 `(?:B|iB)?` 是因为 `k`、`kB`、`kiB` 三种写法都合法，`B` 和 `iB` 两段各自可选。

乘数本身查表：

```python
_SUFFIX_EXPONENT = {
    "k": 1, "K": 1, "m": 2, "M": 2, "G": 3,
    "T": 4, "P": 5, "E": 6, "Z": 7, "Y": 8,
}
```

单字母是 1024 进制（`k` = 1024），字母加 `B` 是 1000 进制（`kB` = 1000），字母加 `iB` 是二进制前缀（`KiB` = `K` = 1024）。`b` 不在表里，它单独处理：`b` 固定乘 512。

### 决定二：argv 必须自己改写

argparse 对 `-3` 和 `-n -3` 这两种写法的处理，都跟 GNU head 的要求对不上。实测裸 argparse（选项定义与 head.py 完全一致）的解析结果：

| 命令行 | 裸 argparse 的解析结果 | 对不对 |
|---|---|---|
| `-3 f.txt` | `files=['-3', 'f.txt']` | **错**：`-3` 被当成位置参数，会去打开一个叫 `-3` 的文件 |
| `-2k f.txt` | `files=['-2k', 'f.txt']` | 同上 |
| `-n -3 f.txt` | `count_specs=['-3']` | 结果对，但依赖 argparse 的「负数不是选项」特判 |

第一行是硬伤：argparse 的选项解析靠「单横线 + 字母」识别选项，`-3` 里的 `3` 不是字母，于是 `-3` 整个被当成操作数。GNU head 的 `-NUM` 是 `-n NUM` 的紧凑写法，所以必须自己认。

第三行是个**当前能过、但不牢靠**的情况。argparse 有一条特判：长得像负数的 token（`-3`）在「本解析器没有长得像负数的选项」时按值处理。head.py 现在确实没有这种选项，所以 `-n -3` 能过。但一旦将来加了 `-3` 这个选项，argparse 的这条特判就会失效，`-n -3` 立刻报错。改成 `-n=-3` 之后，值跟着 `=` 绑定，不再受那条特判影响。

改写还带来一个额外好处：**值长得像已知选项时，报错信息更准**。`-n -v` 里的 `-v` 是 head 自己的选项，裸 argparse 会报 `expected one argument`；改写成 `-n=-v` 之后，值被原样交给计数解析器，报的是项目自己的「无效的行数 '-v'」。

所以 `_rewrite_argv` 做两件事：

```python
# 紧凑写法 -NUM -> -n NUM
compact = _COMPACT_RE.fullmatch(arg)
if compact:
    out.extend(["-n", compact.group(1)])

# 值以负号开头 -> -n=-NUM
if arg in ("-n", "-c", "--lines", "--bytes") and index + 1 < len(args):
    value = args[index + 1]
    if value.startswith("-"):
        out.append(f"{arg}={value}")
```

改写挂在 `parse_known_args` 上，因为那是 argparse 真正开始解析的入口：

```python
class _HeadParser(argparse.ArgumentParser):
    def parse_known_args(self, args=None, namespace=None):
        if args is None:
            args = sys.argv[1:]
        return super().parse_known_args(_rewrite_argv(list(args)), namespace)
```

`--` 之后的参数一律不动（`_rewrite_argv` 里有个 `literal` 标志），所以 `head -- -3` 里的 `-3` 仍然是文件名。

### 决定三：`-n` 和 `-c` 要用自定义 Action

GNU 的规则是「`-n` 与 `-c` 同时给时，后写的那个生效」。argparse 的默认 `store` 动作虽然也是后写覆盖前写，但它**只留值，不留「是哪个选项写的」**。

而 head 恰恰需要知道这个：`count_specs` 里如果只剩一个字符串 `7`，那它是 `-n 7` 还是 `-c 7`？模式不一样，输出的单位就不一样（行 vs 字节）。

所以自定义了一个 Action，把每次出现按顺序记进列表：

```python
class _CountAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        specs = getattr(namespace, self.dest, None)
        if specs is None:
            specs = []
            setattr(namespace, self.dest, specs)
        specs.append((self.const, values))
```

`self.const` 是这个选项的身份（`"lines"` 或 `"bytes"`），`values` 是它带的值。列表里每一项是 `(身份, 值)`。最后取 `specs[-1]` 就是「后写的那个生效」：

```python
specs = getattr(args, "count_specs", None) or []
if specs:
    mode, text = specs[-1]
else:
    mode, text = "lines", str(_DEFAULT_LINES)
```

`-q` 与 `-v` 不需要这么麻烦：它们语义对称（一个关标题一个开标题），argparse 默认的 `store_const` 后写覆盖就够用，最后只留下一个值。

### 决定四：负号语义跟 `tail` 相反

`tail -n -5` 是取末 5 行，`head -n -5` 是**除末 5 行之外全部**。同一个符号，两个命令含义相反，这是 GNU 自己的规定，不是本项目的发明。

实现上这两条路的算法不一样。正数模式是「数够 N 行就停」，读一行少一行：

```python
remaining = options.amount
for line in _split_lines(source.chunks(), delimiter):
    if remaining <= 0:
        break
    _write(ctx, line, encoding)
    remaining -= 1
```

负数模式是「除末 N 行外全要」，得先把最后 N 行扣在手里，读到文件头再倒出来，所以要用 `deque` 缓一下：

```python
pending: deque[bytes] = deque()
for line in _split_lines(source.chunks(), delimiter):
    pending.append(line)
    if len(pending) > options.amount:
        _write(ctx, pending.popleft(), encoding)
```

### 决定五：`0` 和 `-0` 必须分开

`-n 0` 是一行都不要，`-n -0` 是全部都要。两个写法的**数值**都是 0，只有符号不同。

所以 `_parse_amount` 判断的是「文本里有没有负号」，不是「数值是不是负数」：

```python
negative = raw.startswith("-")
digits = match.group(1)
amount = int(digits) * _suffix_multiplier(suffix)
```

`-0` 走到 `negative=True, amount=0`：负数模式 + 扣 0 行 = 全部输出。正数模式 + 0 = 一行不输出。

### 决定六：文本要先解码再输出

Windows 控制台默认代码页是 936（GBK），把 GBK 字节原样写出去就是乱码。本项目先判定文件编码、再解码、最后统一输出 UTF-8，所以 GBK 文件在控制台上能正常显示中文。

代价是：**`-c` 的字节数按源文件算，输出的字节数会变多**。源文件 2 个 GBK 字节（一个汉字）解出来是 1 个字符，再按 UTF-8 写出去是 3 个字节。GNU head 是字节透传，输出还是 2 个字节。

### 决定七：管道里要关掉换行翻译

Windows 上 Python 默认把 `"\n"` 写成 `"\r\n"`。那会把 LF 文件和 CRLF 文件的区别抹掉——而 head 的职责恰恰是原样转交。所以 `_prepare_stdout` 在输出不是终端时把换行翻译关掉：

```python
reconfigure(errors="surrogateescape")
if not _isatty(ctx.stdout):
    reconfigure(newline="")
```

`errors="surrogateescape"` 是另一半：解不开的字节用代理码位占位，写回时还原成原字节，二进制内容因此不会被改写。

## 这个文件是做什么

按职责分成六层，自上而下：

| 层 | 成员 | 干什么 |
|---|---|---|
| 常量与正则 | `_DEFAULT_LINES`、`_NUMBER_RE`、`_COMPACT_RE`、`_SUFFIX_EXPONENT`、`_BLOCK_SIZE` | 计数语法的常量与解析规则 |
| 数据结构 | `_Options`、`_Source` | 一组生效的选项；一个待读的数据源（文件或标准输入） |
| 参数层 | `_CountAction`、`_HeadParser`、`_rewrite_argv` | 记录选项出现顺序、改写 argv |
| 主流程 | `head()`、`_build_options`、`_resolve_headers` | 逐个文件处理，打不打标题 |
| 输出层 | `_emit_lines`、`_emit_bytes`、`_split_lines`、`_write` | 按行或按字节切分输出 |
| 编码层 | `_pick_encoding`、`_detect_encoding`、`_text_score` | 判定文件是文本还是二进制、用什么编码解 |

### 两条输出路径

`_emit()` 按模式分流到两条路，这两条路的差别就是 `-n` 和 `-c` 的全部区别：

| | `_emit_lines` | `_emit_bytes` |
|---|---|---|
| 切分单位 | 行（`\n`，`-z` 时是 NUL） | 字节 |
| 正数模式 | 数够 N 行就停 | 拿够 N 个字节就停 |
| 负数模式 | `deque` 扣住最后 N 行 | `bytearray` 扣住最后 N 字节 |
| 会不会切坏内容 | 不会，分隔符跟着行走 | 会，可能停在半个字符中间 |

`_split_lines` 只认 `\n` 作分隔符，`\r` 留在行内容里。这样 CRLF 文件的空行内容是 `\r` 而不是空行，跟 GNU 的判定一致。

### 关键函数速查

| 函数 | 行号 | 作用 |
|---|---|---|
| `_rewrite_argv` | 160 | 紧凑写法与负号值的 argv 改写 |
| `build_parser` | 195 | 声明 `-n`/`-c`/`-q`/`-v`/`-z` |
| `head` | 257 | 主流程，逐文件处理 |
| `_build_options` | 312 | 取最后一次出现的计数规格，解析成 `_Options` |
| `_resolve_headers` | 328 | 决定要不要打 `==> 文件名 <==` 标题 |
| `_parse_amount` | 341 | 解析符号与数字，判上界 |
| `_suffix_multiplier` | 368 | 算后缀倍数（b=512、kB=1000、KiB=1024） |
| `_emit_lines` | 470 | 按行输出 |
| `_emit_bytes` | 495 | 按字节输出 |
| `_split_lines` | 522 | 按分隔符切行，分隔符跟着行走 |
| `_pick_encoding` | 554 | 判文本还是二进制 |

### 入口点

```python
@command("head", "打印文件开头部分（GNU head 风格子集）", build_parser)
def head(args: argparse.Namespace, ctx: RunContext) -> int:
```

`@command` 来自 `w2l/registry.py`，`commands` 包在首次分发时自动导入本模块完成注册，主干代码不需要改。退出码规则：正常 0，出错 2（GNU head 返回 1，本项目按「用法或运行错误返回 2」的约定）。

## 有什么用

**1. 三种计数语义，一个选项区分。**

`-n` 数行、`-c` 数字节、`-N`（负数）反着来。行和字节的单位换算只在 `_Options` 里发生一次，输出层各走各的路。

**2. 后写的选项生效，符合 GNU 直觉。**

`-c 7 -n 2` 取 2 行，`-n 2 -c 7` 取 7 字节。这个「记住顺序」的能力来自 `_CountAction`，不是 argparse 白送的。

**3. 管道里内容逐字节不变。**

LF 文件的 `\n` 不会被翻译成 `\r\n`，二进制文件不会被改写，`head` 后接校验和工具得到的和源文件一致。

**4. 中文在 Windows 控制台上不乱码。**

GBK 文件判定出编码后统一输出 UTF-8。GNU head 是字节透传，直接把 GBK 字节写出去。

**5. argv 改写是可以照抄的模板。**

`tail.py` 有同样的需求（`-n +20`、`-n -20`），做法一致：自定义 Parser 子类，在 `parse_known_args` 里改写 argv。加新指令遇到 GNU 的怪语法时，这个模式可以直接搬。

## 怎么用（过程教程）

下面所有命令都实测过，输出与文档一致。用 `AI/脚本/_t12_verify_teach.py` 可以自动核对本篇的命令。

### 第 1 步：先看清这个文件有多大

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat w2l/commands/head.py | wc -l
```

预期输出：

```
642
```

642 行里有一半在处理「怎么把命令行解析对」，另一半在处理「怎么把字节切出来」。这比例说明这个文件的难点不在输出，在参数。

### 第 2 步：默认取前 10 行

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head w2l/registry.py
```

预期输出：

```
"""指令注册表。

新增指令只需在 w2l/commands/ 下放一个模块，用 @command 装饰处理函数，
commands 包在首次分发时自动导入全部子模块，因此无需改动 main.py。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
```

不给 `-n` 时默认 10 行（`_DEFAULT_LINES = 10`）。

### 第 3 步：`-n` 指定行数，紧凑写法 `-N` 等价

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head -n 2 w2l/registry.py
```

预期输出：

```
"""指令注册表。

```

紧凑写法：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head -2 w2l/registry.py
```

预期输出：

```
"""指令注册表。

```

`-2` 没有经过 argparse 的选项识别，是 `_rewrite_argv` 改写成 `-n 2` 之后才被解析的。

### 第 4 步：`-n -N` 是「除末 N 行之外全部」

这是最容易记错的一条。`-n -3` 不是「取末 3 行」，而是「取除末 3 行之外的部分」：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head -n -3 w2l/registry.py | wc -l
```

预期输出：

```
45
```

文件一共 48 行，扣掉末 3 行剩 45 行。同一台机器上的 GNU head 结果一样：

```bash
cd E:\1\NULL\Windows-to-Linux
head -n -3 w2l/registry.py | wc -l
```

预期输出：

```
45
```

### 第 5 步：`0` 和 `-0` 意思不同

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head -n 0 w2l/registry.py | wc -l
```

预期输出：

```
0
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head -n -0 w2l/registry.py | wc -l
```

预期输出：

```
48
```

`-n 0` 一行不要，`-n -0` 全部输出。判断依据是文本里有没有负号，不是数值大小。

### 第 6 步：`+N` 等价 `N`

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head -n +3 w2l/registry.py | wc -l
```

预期输出：

```
3
```

head 没有 `tail` 那种「从第 N 行开始」的语义，`+N` 就是 `N`。想从第 20 行开始到最后，要用 `tail -n +20`。

### 第 7 步：`-c` 按字节，不是按行

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'l1\nl2\nl3\n' | python main.py head -c 7 - | od -c
```

预期输出：

```
0000000   l   1  \n   l   2  \n   l
0000007
```

7 个字节切进了第 3 行中间，所以第 3 行只剩一个 `l`。同样的输入按行切：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'l1\nl2\nl3\n' | python main.py head -n 2 -
```

预期输出：

```
l1
l2
```

### 第 8 步：`-n` 与 `-c` 同时给，后写的生效

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head -c 7 -n 2 w2l/registry.py
```

预期输出：

```
"""指令注册表。

```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head -n 2 -c 7 w2l/registry.py | od -c
```

预期输出：

```
0000000   "   "   " 346 214 207 344
0000007
```

第二种写法取 7 个字节，切在「令」字的第一个字节上。`22 22 22` 是三个引号（ASCII），`346 214 207` 是「指」字的 UTF-8 三字节，`344` 是「令」字的第一字节。

解不开的半个字符用代理码位占位，写回时还原成原字节，所以**字节不会丢**——`od -c` 里那个孤零零的 `344` 就是证据。

### 第 9 步：乘数后缀

`-n` 的后缀乘**行数**，`-c` 的后缀乘**字节数**：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head -n 1b w2l/commands/head.py | wc -l
```

预期输出：

```
512
```

`-n 1b` 是 512 **行**，不是 512 字节。同一个后缀给 `-c` 就是 512 字节：

```bash
cd E:\1\NULL\Windows-to-Linux
for s in 1b 1k 1kB 1KiB; do printf '%s=' "$s"; python main.py head -c $s w2l/commands/head.py | wc -c; done
```

预期输出：

```
1b=512
1k=1024
1kB=1000
1KiB=1024
```

`b` 固定 512，单字母是 1024 进制，加 `B` 是 1000 进制，加 `iB` 是二进制前缀（等于单字母）。

### 第 10 步：多个文件会打标题

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head -n 1 w2l/context.py w2l/errors.py
```

预期输出：

```
==> w2l/context.py <==
"""指令运行上下文：把当前目录与标准流传给指令实现。"""

==> w2l/errors.py <==
"""指令执行过程中使用的两类异常。"""
```

标题格式是 `==> 文件名 <==`，第二个及以后的标题**前面先空一行**（`_print_header` 里 `header_count > 0` 时多写一个 `\n`）。单个文件时默认不打标题。

### 第 11 步：`-q` 关标题，`-v` 强制标题

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head -q -n 1 w2l/context.py w2l/errors.py
```

预期输出：

```
"""指令运行上下文：把当前目录与标准流传给指令实现。"""
"""指令执行过程中使用的两类异常。"""
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head -v -n 1 w2l/context.py
```

预期输出：

```
==> w2l/context.py <==
"""指令运行上下文：把当前目录与标准流传给指令实现。"""
```

`-q` 与 `-v` 同时给时后写的生效：`head -q -v` 打标题，`head -v -q` 不打。

### 第 12 步：标准输入

不给操作数就读标准输入，`-` 也表示标准输入：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 's1\ns2\ns3\n' | python main.py head -n 2
```

预期输出：

```
s1
s2
```

标题里的名字是 `standard input`：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 's1\ns2\n' | python main.py head -v -
```

预期输出：

```
==> standard input <==
s1
s2
```

### 第 13 步：`-z` 用 NUL 当行分隔符

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'z1\x00z2\x00z3\x00' | python main.py head -z -n 2 - | od -c
```

预期输出：

```
0000000   z   1  \0   z   2  \0
0000006
```

分隔符跟着行走，所以输出里带上了两个 NUL。

### 第 14 步：CRLF 原样转交，末行不补换行

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'c1\r\nc2\r\nc3\r\n' | python main.py head -n 2 - | od -c
```

预期输出：

```
0000000   c   1  \r  \n   c   2  \r  \n
0000010
```

`\r` 留在行内容里，没有被翻译成别的。文件末尾没有换行符时，输出也不加：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'p1\np2\np3' | python main.py head - | od -c
```

预期输出：

```
0000000   p   1  \n   p   2  \n   p   3
0000010
```

### 第 15 步：二进制逐字节透传

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'a\x00b\xff' | python main.py head - | od -c
```

预期输出：

```
0000000   a  \0   b 377
0000004
```

含 NUL 字节的文件被判定为二进制，按原字节输出，不做编码转换。

### 第 16 步：GBK 文件在本项目里显示中文，GNU 里是原样字节

这是本项目与 GNU head 唯一一处**故意不同**的地方。

本项目：

```bash
cd E:\1\NULL\Windows-to-Linux
printf '\xd6\xd0\xce\xc4\n' | python main.py head - | od -c
```

预期输出：

```
0000000 344 270 255 346 226 207  \n
0000007
```

`344 270 255` 是「中」的 UTF-8 三字节，`346 226 207` 是「文」。GNU head：

```bash
cd E:\1\NULL\Windows-to-Linux
printf '\xd6\xd0\xce\xc4\n' | head - | od -c
```

预期输出：

```
0000000 326 320 316 304  \n
0000005
```

`326 320 316 304` 是「中文」的 GBK 四个字节，GNU 原样透传。

代价是字节数会变：源文件取 2 个字节（一个汉字），本项目输出 3 个字节（UTF-8），GNU 还是 2 个字节。

```bash
cd E:\1\NULL\Windows-to-Linux
printf '\xd6\xd0\xce\xc4\n' | python main.py head -c 2 - | wc -c; printf '\xd6\xd0\xce\xc4\n' | head -c 2 | wc -c
```

预期输出：

```
3
2
```

第一行是本项目，第二行是 GNU。`-c` 的字节数**始终按源文件算**，变的是输出。

### 第 17 步：出错的路径

打不开的文件：只报错，不打标题，继续处理后面的文件，退出码 2。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head w2l/nope.txt; echo "退出码=$?"
```

预期输出：

```
head: 无法打开 'w2l/nope.txt': No such file or directory
退出码=2
```

目录：先打标题再报「是一个目录」。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head w2l; echo "退出码=$?"
```

预期输出：

```
head: 读取 'w2l' 出错: 是一个目录
退出码=2
```

计数写错时是**用法错误**，报的是项目自己的消息：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head -n abc w2l/registry.py; echo "退出码=$?"
```

预期输出：

```
错误: 无效的行数 'abc'
退出码=2
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head -c 1g w2l/registry.py; echo "退出码=$?"
```

预期输出：

```
错误: 无效的字节数 '1g'
退出码=2
```

`1g` 非法，因为 GNU 的后缀表里没有 `g`（有 `G`）。

### 第 18 步：跑相关测试

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest tests/test_head.py 2>&1 | tail -1
```

预期输出：

```
32 passed in 0.16s
```

（耗时每次不同，核对器会把 `in 0.16s` 这类归一化后再比对。）

### 第 19 步：确认整体没坏

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest 2>&1 | tail -1
```

预期输出：

```
180 passed in 6.23s
```

（耗时每次不同。）
