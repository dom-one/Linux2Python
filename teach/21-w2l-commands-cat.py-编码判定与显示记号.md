# w2l/commands/cat.py — 编码判定与显示记号

`w2l/commands/cat.py` 有 392 行。它要回答的问题比 `head` 简单，但陷阱在别处：**文件里的字节，到底要不要动？**

GNU cat 是字节透传——文件里是什么字节，输出就是什么字节。但 Windows 控制台的代码页是 936（GBK），把 GBK 字节原样写出去就是乱码。本项目要在「原样转交」和「中文能看」之间找一条路，于是有了本文件最核心的一段逻辑：**先判断这堆字节是文本还是二进制，是文本就判定编码再解码，解码后统一输出 UTF-8**。

判定错了会有两种后果，都很实际：

| 判错 | 后果 |
|---|---|
| 二进制被当成文本 | 高位字节被错误解码，文件内容被改写 |
| 文本被当成二进制 | GBK 中文原样写出去，控制台上是乱码 |

文件里还有一层不显眼的规则：**编号和空行压紧的状态跨文件延续**，且 `-b` 覆盖 `-n` 与选项顺序无关。这两条都容易记错。

## 为什么这么创建

### 决定一：文本必须先解码再输出

Windows 控制台默认代码页 936（GBK）。GBK 文件的字节原样写出去，控制台按 GBK 解，能显示中文——但前提是**字节本身就是 GBK**。而本项目统一用 UTF-8 输出，理由是 Python 的输出流按 UTF-8 编码，管道和重定向后的下游工具也普遍按 UTF-8 读。

所以流程是：读原始字节 → 判定编码 → 解码成字符串 → 按 UTF-8 写出。

代价是**字节数会变**。一个 GBK 汉字占 2 字节，解码成字符后再按 UTF-8 写出占 3 字节。实测 `AI/数据/gbk_demo.txt`（4 个汉字 + 5 个汉字 = 9 个汉字，GBK 下 9 个汉字占 18 字节，加 2 个换行共 20 字节）：

| 路径 | 输出字节数 | 说明 |
|---|---|---|
| 走文件 | 29 | 解码成 UTF-8，汉字从 2 字节变 3 字节 |
| 走 stdin | 20 | 编码写死 utf-8，字节守恒 |

### 决定二：文本与二进制的分界是「能不能被真正的文本编码严格解码」

判据不能是「看起来像不像文本」，得是可执行的。`_pick_encoding` 分两步：

```python
def _pick_encoding(sample: bytes) -> str:
    if b"\x00" in sample:
        return _BINARY_ENCODING
    if _is_text(sample):
        return _detect_encoding(sample)
    return _BINARY_ENCODING
```

第一步查 NUL 字节。含 NUL 的一定是二进制——文本格式里几乎不会出现 NUL，这是最省事也最可靠的判据。

第二步 `_is_text` 挨个试候选编码，看有没有哪个能**严格**解码：

```python
def _is_text(sample: bytes) -> bool:
    for encoding in _candidate_encodings():
        if encoding == "latin-1":
            continue
        if _decode_sample(sample, encoding) is not None:
            return True
    return False
```

**latin-1 被显式排除，这是关键。** latin-1 能解码任意字节（0x00–0xFF 一一对应），所以它「永远成功」。如果把它算进文本判定，所有二进制文件都会被判成文本，然后被错误解码改写内容。源码注释里写明了这一点：

```python
# latin-1 永远能解任何字节，所以判定文本时不把它算进去，
# 否则所有二进制都会被误判成文本。
```

实测高位字节文件 `b"\x80\xa0\xff\n"`：utf-8 解不出，gb18030 也解不出，只有 latin-1 能解 —— 所以判定结果是二进制，字节原样转交。

### 决定三：编码判定要打分，不能取第一个能解的

文本文件能解出好几种编码，挑哪个？直觉是「取第一个能解的」，但那是错的。

`_candidate_encodings()` 的顺序是 `utf-8`、系统首选编码、`gb18030`、`latin-1`。在**英文 Windows** 上系统首选编码是 cp1252，而 cp1252 几乎不报错——它把每个字节都映射成某个字符。GBK 中文用 cp1252 解出来是 `ÖÐÎÄÄÚÈÝ` 这种乱码，但解码过程完全成功。

所以 `_detect_encoding` 给每种解码结果打分，取分最高的：

```python
def _detect_encoding(sample: bytes) -> str:
    best_encoding = "utf-8"
    best_score = -1.0
    for encoding in _candidate_encodings():
        text = _decode_sample(sample, encoding)
        if text is None:
            continue
        score = _text_score(text)
        if score > best_score + _SCORE_MARGIN:
            best_score = score
            best_encoding = encoding
    return best_encoding
```

打分规则在 `_text_score`：ASCII 可打印字符记 1 分，CJK 记 3 分，全角标点记 1 分，**高位乱码字节只记 0.2 分**。这样 GBK 正文的分数（汉字占 3 分）能压过 cp1252 的乱码结果。

实测同一串 GBK 字节的两种解法：

| 解码方式 | 解出的文本 | 分数 |
|---|---|---|
| gb18030 | `中文内容` | 3.0 |
| latin-1 | `ÖÐÎÄÄÚÈÝ` | 0.2 |

差 15 倍，判定结果稳定落在 `gb18030`。

`_SCORE_MARGIN = 0.3` 是「换冠军的门槛」：后来的编码必须比当前最优高出 0.3 分才能取代它。

纯 ASCII 文件用三种编码解出来，分数**完全一样**——因为三种编码解同一串 ASCII 字节，得到的是同一串字符。门槛挡住了后面来的一次次平分替换，最终留在候选表第一个 `utf-8`。

这里要说清一件事：**分数不是纯 ASCII 文本的通值，它随内容变化**。得分是「可打印字符 1 分 + 换行 0.5 分」再除以总字符数，所以每个文件都不一样：

| 样本 | 三种编码的得分 |
|---|---|
| `hello world\n` | 0.958333 |
| `hello\n` | 0.916667 |
| `abc\n` | 0.875000 |
| `plain ascii text\n` | 0.970588 |

四行里三种编码的分数都相同——这才是「纯 ASCII 不区分编码」的真正含义。而 GBK 正文之所以能被 utf-8 之外的编码压过，是因为解成乱码时每个高位字节只记 0.2 分，分数被拉低到和正经正文不在一个量级。

### 决定四：二进制按 utf-8 + surrogateescape 逐字节转交

二进制路径不走「保持原编码」，而是固定用 utf-8 解码，但带上 `errors="surrogateescape"`：

```python
_BINARY_ENCODING = "utf-8"
```

surrogateescape 的机制是：解不出的字节用 U+DC80–U+DCFF 这一段代理码位占位，写回时再还原成原字节。所以「解码」这步不丢信息，输出仍是原来的字节。

同一个手法也用在输出流上。`_prepare_stdout` 做了两件事：

```python
reconfigure(errors="surrogateescape")
if not _isatty(ctx.stdout):
    reconfigure(newline="")
```

`errors="surrogateescape"` 让输出流能写出代理码位（否则 Python 会报错）；`newline=""` 关掉换行翻译——Windows 上 Python 默认把 `\n` 写成 `\r\n`，那会把 LF 文件和 CRLF 文件的区别抹掉，而 cat 的职责恰恰是原样转交。管道与重定向时关掉，控制台里保持默认（老控制台只认 CRLF）。

实测全 256 字节的二进制文件：输出长度 256，首尾字节与源文件一致。

### 决定五：只认 `\n` 作行分隔符，`\r` 留在行内容里

`_split_lines` 只找 `\n`：

```python
index = buffer.find(b"\n", start)
```

`\r` 留在行内容里。这样做有个直接后果：**CRLF 文件的「空行」内容是 `\r`，不是空行**。

判断空行的代码是 `raw == b""`，严格的字节相等。所以 CRLF 文件里那两个「看起来是空行」的行，实际内容是 `\r`，`-s` 不压它们，`-b` 照样给它们编号。实测 `printf 'a\n\r\n\r\nb\n' | python main.py cat -b -` 给出了 4 个行号。

这与 GNU cat 一致（GNU 也只按 LF 切行），实测逐字节相同。

### 决定六：`-b` 覆盖 `-n`，与选项顺序无关

GNU 的规则是 `-n` 给所有行编号，`-b` 只给非空行编号，两者同开时以 `-b` 为准，且**与给出的先后顺序无关**。

实现上不需要「记住顺序」——两个选项各存一个布尔值，`_build_options` 里直接让 `-b` 优先：

```python
number_all=args.number and not args.number_nonblank,
number_nonblank=args.number_nonblank,
```

`-n -b` 和 `-b -n` 结果相同，实测两边输出一致。

还有一条容易忽略的细节：**`-b` 模式下计数器只在真正编号时才前进**。`_number_prefix` 里：

```python
if options.number_nonblank:
    if raw == b"":
        return b""
    state.line_number += 1
```

空行直接返回空前缀，计数器不动。所以 `w2l/errors.py` 有 9 行，其中 4 行空行，`-b` 的编号是 1、2、3、4、5，而不是 1 到 9。

### 决定七：跨文件延续的状态

`_State` 对象在主流程里只建一次，跨所有文件共用：

```python
state = _State()
for name in files:
    ...
    _emit_stream(_chunks(handle), encoding, options, state, ctx)
```

里面两个字段：行号计数器、空行压紧标记。都不在文件边界重置。

- 行号跨文件连续累计：`cat -n w2l/errors.py w2l/context.py` 的编号从 1 排到 21，不在第二个文件开头重新数。
- `-s` 的压紧状态也跨文件延续：第一个文件末尾是空行、第二个文件开头是空行的话，这两个空行会被当成连续的，只保留一个。

这个状态对象是「连接」语义的一部分——GNU cat 把多个文件当一条连续的字节流，编号自然连续。

### 决定八：出错不影响其余文件，退出码按项目约定取 2

```python
had_error = False
for name in files:
    ...
    except OSError as exc:
        ctx.stderr.write(f"cat: 无法打开 '{name}': {exc.strerror or exc}\n")
        had_error = True
        continue
```

某个文件打不开，只报错、继续处理后面的文件，最后统一返回 2。GNU cat 出错返回 1，本项目按「用法或运行错误返回 2」的约定取 2，这是项目里统一的退出码规则，不是 cat 特有的。

目录当操作数也走这条路，报「是一个目录」。

## 这个文件是做什么

按职责分成五层，自上而下：

| 层 | 成员 | 干什么 |
|---|---|---|
| 常量 | `_SNIFF_SIZE`、`_READ_SIZE`、`_SCORE_MARGIN`、`_CJK_RANGES`、`_FALLBACK_ENCODINGS`、`_BINARY_ENCODING`、`_NUMBER_WIDTH` | 嗅探大小、读块大小、换冠军门槛、CJK 区间、兜底编码表、二进制用的编码、编号列宽 |
| 数据结构 | `_Options`、`_State` | 一组生效的显示选项；跨文件延续的行号与压紧状态 |
| 参数层 | `build_parser`、`_build_options` | 声明选项；把选项归一成 `_Options` |
| 主流程 | `cat`、`_resolve` | 逐个处理操作数，分派到文件或标准输入 |
| 输出层 | `_emit_stream`、`_split_lines`、`_number_prefix`、`_show_content`、`_show_nonprinting`、`_control_notation` | 切行、编号、显示记号 |
| 编码层 | `_pick_encoding`、`_is_text`、`_detect_encoding`、`_candidate_encodings`、`_decode_sample`、`_text_score` | 判文本还是二进制、判定编码 |

### 两条数据路径

`cat()` 对每个操作数分两条路：

```python
if name == "-":
    _emit_stream(_stdin_chunks(ctx), "utf-8", options, state, ctx)
    continue
...
encoding = _pick_encoding(sample)
_emit_stream(_chunks(handle), encoding, options, state, ctx)
```

**stdin 的编码写死 utf-8，不做编码判定**；文件才走 `_pick_encoding`。这是本文件最容易被忽略的一处不对称，也是「同一份 GBK 内容走文件会被解码、走 stdin 不会」的原因。

标准输入还要走底层二进制流。文本模式的 stdin 会把 CRLF 归一成 LF、丢掉 lone CR，那不是 cat 该做的事：

```python
buffer = getattr(stream, "buffer", None)
if buffer is not None:
    yield from _chunks(buffer)
    return
```

### 关键函数速查

| 函数 | 行号 | 作用 |
|---|---|---|
| `build_parser` | 66 | 声明 10 个选项 |
| `cat` | 95 | 主流程，逐个处理操作数 |
| `_build_options` | 128 | 把选项归一成 `_Options` |
| `_prepare_stdout` | 142 | 输出流改成 surrogateescape + 非终端关换行翻译 |
| `_stdin_chunks` | 182 | 从 stdin 取原始字节 |
| `_emit_stream` | 208 | 按行输出，处理编号与压紧 |
| `_split_lines` | 233 | 按 `\n` 切行 |
| `_number_prefix` | 255 | 算行号前缀 |
| `_show_content` | 271 | 按选项加工行内容 |
| `_show_nonprinting` | 279 | 非打印字符转 `^` / `M-` 记号 |
| `_pick_encoding` | 305 | 判文本还是二进制、选编码 |
| `_detect_encoding` | 335 | 按可信度打分选编码 |
| `_text_score` | 371 | 给解码结果打「像不像正文」的分 |

### 入口点

```python
@command("cat", "连接文件内容并输出到标准输出（GNU cat 风格子集）", build_parser)
def cat(args: argparse.Namespace, ctx: RunContext) -> int:
```

`@command` 来自 `w2l/registry.py`，`commands` 包在首次分发时自动导入本模块完成注册，主干代码不需要改。退出码：正常 0，出错 2。

### 相关文件

| 文件 | 关系 |
|---|---|
| `w2l/commands/grep.py` | 用同一套编码打分思路，判定口径一致 |
| `w2l/commands/head.py` | 同样的输出流处理（surrogateescape + 非终端关换行翻译），但计数语义不同 |
| `w2l/context.py` | `RunContext` 提供 `cwd` / `stdout` / `stderr` / `stdin` |
| `w2l/registry.py` | `@command` 装饰器，注册 `cat` 指令 |
| `tests/test_cat.py` | 34 个用例，逐条对照 Git Bash 的 GNU cat 输出 |
| `AI/脚本/_t95_probe_cat_tut.py` | 本篇的行为实测脚本 |
| `AI/脚本/_t101_make_gbk_demo.py` | 生成 GBK 演示文件并对比文件路径与 stdin |
| `AI/脚本/_t102_probe_teach21_mismatch.py` | 取证 4 处「预期输出与实际不符」的根因 |
| `AI/脚本/_t103_compute_od_dump.py` | 独立复算 od -c 的八进制转储（自算与 GNU od 互相印证） |
| `AI/脚本/_t104_verify_cat_tut_claims.py` | 复算正文里只有文字佐证、核对器查不到的数字 |

## 有什么用

**1. 中文在 Windows 控制台上不乱码。**

GBK 文件判定出编码后解码成 UTF-8 输出。这是本项目与 GNU cat 最大的行为差异，是刻意的取舍。

**2. 二进制内容不会被改写。**

判定为二进制后按字节原样转交，`cat` 后接校验和工具，得到的和源文件一致。

**3. 多个文件当一条连续字节流处理。**

行号与空行压紧状态跨文件延续，符合「连接」的语义。

**4. 选项组合行为可预测。**

`-b` 覆盖 `-n` 与顺序无关；`-e`/`-t`/`-A` 是固定展开的组合（`-e` = `-vE`，`-t` = `-vT`，`-A` = `-vET`），不需要理解 GNU 的优先级规则。

**5. 编码判定逻辑是可以照抄的模板。**

`grep.py` 用的是同一套打分思路。遇到「怎么判断这堆字节是什么编码」的问题，这套「排除万能解码 → 挨个严格解 → 打分取最优」的三步可以直接搬。

## 怎么用（过程教程）

下面所有命令都实测过，输出与文档一致。用 `AI/脚本/_t12_verify_teach.py` 可以自动核对本篇的命令。

### 第 1 步：先看清这个文件有多大、有哪些选项

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat w2l/commands/cat.py | wc -l
```

预期输出：

```
392
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat --help
```

预期输出：

```
usage: python main.py cat [-h] [-n] [-b] [-E] [-e] [-T] [-t] [-s] [-v] [-A]
                          [-u]
                          [files ...]

连接文件内容并输出到标准输出

positional arguments:
  files                 要输出的文件，- 表示标准输入；不填则读标准输入

options:
  -h, --help            show this help message and exit
  -n, --number          给所有输出行编号
  -b, --number-nonblank
                        只给非空行编号（与 -n 同开时以 -b 为准）
  -E, --show-ends       在每行末尾显示 $
  -e                    同 -vE
  -T, --show-tabs       把制表符显示成 ^I
  -t                    同 -vT
  -s, --squeeze-blank   把连续空行压成一行
  -v, --show-nonprinting
                        用 ^ 与 M- 记号显示非打印字符
  -A, --show-all        等价于 -vET
  -u, --unbuffered      立即输出，不缓冲（此实现无实际影响）

示例:
  python main.py cat w2l/cli.py
  python main.py cat -n w2l/registry.py
  python main.py cat -A w2l/context.py
  python main.py cat README.md AGENTS.md
```

### 第 2 步：默认就是原样输出

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat w2l/errors.py
```

预期输出：

```
"""指令执行过程中使用的两类异常。"""


class UsageError(Exception):
    """用法错误，退出码 2。"""


class CommandError(Exception):
    """指令执行失败，退出码 1。"""
```

### 第 3 步：多个文件连接，行号跨文件累计

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat w2l/errors.py w2l/context.py
```

预期输出：

```
"""指令执行过程中使用的两类异常。"""


class UsageError(Exception):
    """用法错误，退出码 2。"""


class CommandError(Exception):
    """指令执行失败，退出码 1。"""
"""指令运行上下文：把当前目录与标准流传给指令实现。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


@dataclass
class RunContext:
    cwd: Path
    stdout: TextIO
    stderr: TextIO
    stdin: TextIO
```

两个文件的内容直接首尾相接，中间**没有**任何分隔符——`errors.py` 的最后一行紧挨着 `context.py` 的第一行。

加上 `-n` 看行号：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat -n w2l/errors.py w2l/context.py
```

预期输出：

```
     1	"""指令执行过程中使用的两类异常。"""
     2	
     3	
     4	class UsageError(Exception):
     5	    """用法错误，退出码 2。"""
     6	
     7	
     8	class CommandError(Exception):
     9	    """指令执行失败，退出码 1。"""
    10	"""指令运行上下文：把当前目录与标准流传给指令实现。"""
    11	
    12	from __future__ import annotations
    13	
    14	from dataclasses import dataclass
    15	from pathlib import Path
    16	from typing import TextIO
    17	
    18	
    19	@dataclass
    20	class RunContext:
    21	    cwd: Path
    22	    stdout: TextIO
    23	    stderr: TextIO
    24	    stdin: TextIO
```

编号从 1 排到 21，**不在第二个文件开头重新数**。编号是右对齐占 6 位再跟一个制表符，所以第 1 行是 5 个空格加 `1`，第 10 行是 4 个空格加 `10`。

### 第 4 步：`-b` 只给非空行编号，且覆盖 `-n`

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat -b w2l/errors.py
```

预期输出：

```
     1	"""指令执行过程中使用的两类异常。"""


     2	class UsageError(Exception):
     3	    """用法错误，退出码 2。"""


     4	class CommandError(Exception):
     5	    """指令执行失败，退出码 1。"""
```

空行不编号，**计数器也不前进**。文件共 9 行、4 行空行，编号只到 5。

对比 `-n` 给每一行编号：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat -n w2l/errors.py
```

预期输出：

```
     1	"""指令执行过程中使用的两类异常。"""
     2	
     3	
     4	class UsageError(Exception):
     5	    """用法错误，退出码 2。"""
     6	
     7	
     8	class CommandError(Exception):
     9	    """指令执行失败，退出码 1。"""
```

`-b` 覆盖 `-n`，**与选项顺序无关**：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat -n -b w2l/errors.py
```

预期输出：

```
     1	"""指令执行过程中使用的两类异常。"""


     2	class UsageError(Exception):
     3	    """用法错误，退出码 2。"""


     4	class CommandError(Exception):
     5	    """指令执行失败，退出码 1。"""
```

反序写 `-b -n` 结果一样。

### 第 5 步：`-s` 压连续空行，含空格的行不算空行

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat -s w2l/errors.py
```

预期输出：

```
"""指令执行过程中使用的两类异常。"""

class UsageError(Exception):
    """用法错误，退出码 2。"""

class CommandError(Exception):
    """指令执行失败，退出码 1。"""
```

两行连续空行被压成一行。

「空行」的判定是内容**完全为空**。含空格的行不算：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'one\n   \ntwo\n' | python main.py cat -s -
```

预期输出：

```
one
   
two
```

中间那行（3 个空格）原样保留，没有被压掉。

含空格的行照样算「非空行」，`-b` 照样给它编号：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'one\n   \ntwo\n' | python main.py cat -b -
```

预期输出：

```
     1	one
     2	   
     3	two
```

### 第 6 步：`-E` 在行尾加 `$`

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat -E w2l/errors.py
```

预期输出：

```
"""指令执行过程中使用的两类异常。"""$
$
$
class UsageError(Exception):$
    """用法错误，退出码 2。"""$
$
$
class CommandError(Exception):$
    """指令执行失败，退出码 1。"""$
```

末行没有换行符时，`$` 也不补：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'one\ntwo' | python main.py cat -E -
```

预期输出：

```
one$
two
```

### 第 7 步：`-T` 把制表符显示成 `^I`，`-v` 不动它

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'col1\tcol2\n' | python main.py cat -T -
```

预期输出：

```
col1^Icol2
```

`-v` 不处理制表符（制表符是可打印字符，只是排版用）：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'col1\tcol2\n' | python main.py cat -v -
```

预期输出：

```
col1	col2
```

两个一起开就是 `^I`：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'col1\tcol2\n' | python main.py cat -vT -
```

预期输出：

```
col1^Icol2
```

注意实现里 `-T` 的替换发生在 `-v` 的转义**之后**，所以 `-v` 留下的真制表符最后才被 `^I` 换掉。

### 第 8 步：`-v` 的 `^` 与 `M-` 记号

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'bell\a del\177 esc\033\n' | python main.py cat -v -
```

预期输出：

```
bell^G del^? esc^[
```

`\a`（BEL）显示成 `^G`，DEL 显示成 `^?`，ESC 显示成 `^[`。规则是 `^` 加「原字节与 0x40 异或」——`0x07 ^ 0x40 = 0x47` 就是 `G`。

高位字节用 `M-` 记号：

```bash
cd E:\1\NULL\Windows-to-Linux
printf '\200\240\377\n' | python main.py cat -v -
```

预期输出：

```
M-^@M- M-^?
```

`0x80` 的低七位是 `0x00`，记号是 `^@`，加上 `M-` 前缀就是 `M-^@`。`0xa0` 的低七位是 `0x20`（空格），本身就是可打印字符，所以是 `M- `（`M-` 加一个空格）。

用 `od -c` 看确认这是六个 ASCII 字符，不含原始高位字节：

```bash
cd E:\1\NULL\Windows-to-Linux
printf '\200\240\377\n' | python main.py cat -v - | od -c
```

预期输出：

```
0000000   M   -   ^   @   M   -       M   -   ^   ?  \n
0000014
```

### 第 9 步：`-e`、`-t`、`-A` 是固定展开的组合

`-e` 等价 `-vE`：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'bell\a del\177 esc\033\n' | python main.py cat -e -
```

预期输出：

```
bell^G del^? esc^[$
```

`-t` 等价 `-vT`：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'col1\tcol2\n' | python main.py cat -t -
```

预期输出：

```
col1^Icol2
```

`-A` 等价 `-vET`：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'col1\tcol2\n' | python main.py cat -A -
```

预期输出：

```
col1^Icol2$
```

`-A` 遇上 CRLF 时，`\r` 也被转成 `^M`：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'l1\r\nl2\r\n' | python main.py cat -A -
```

预期输出：

```
l1^M$
l2^M$
```

### 第 10 步：CRLF 原样转交，`\r` 留在行内容里

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'l1\r\nl2\r\n' | python main.py cat -
```

预期输出：

```
l1
l2
```

看字节就知道 `\r` 没被吃掉：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'l1\r\nl2\r\n' | python main.py cat - | od -c
```

预期输出：

```
0000000   l   1  \r  \n   l   2  \r  \n
0000010
```

由此带来的一个后果：**CRLF 文件的「空行」内容是 `\r`，不算空行**。

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'a\n\r\n\r\nb\n' | python main.py cat -b -
```

预期输出：

```
     1	a
     2	
     3	
     4	b
```

中间两行内容是 `\r`，`-b` 照样给它们编号，编号一路数到 4。

### 第 11 步：二进制逐字节原样转交

含 NUL 字节的一律判定为二进制：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'a\000b\n' | python main.py cat - | od -c
```

预期输出：

```
0000000   a  \0   b  \n
0000004
```

高位字节文件（不含 NUL）也是二进制：

```bash
cd E:\1\NULL\Windows-to-Linux
printf '\200\240\377\n' | python main.py cat - | od -c
```

预期输出：

```
0000000 200 240 377  \n
0000004
```

对比第 8 步的 `-v` 版本——加了 `-v` 之后高位字节被换成了 `M-` 记号，没加就是原字节。

### 第 12 步：GBK 文件走**文件路径**会被解码

这条只在文件路径上成立。先造一个 GBK 编码的文件（`AI/数据/` 已被 `.gitignore` 忽略，不会污染仓库）：

```bash
cd E:\1\NULL\Windows-to-Linux
python -c "import pathlib;pathlib.Path('AI/数据/gbk_demo.txt').write_bytes('中文内容\n第二行内容\n'.encode('gb18030'))"
```

然后看它的原始字节（直接 od 文件，不经过本项目的 cat）：

```bash
cd E:\1\NULL\Windows-to-Linux
od -c AI/数据/gbk_demo.txt
```

预期输出：

```
0000000 326 320 316 304 304 332 310 335  \n 265 332 266 376 320 320 304
0000020 332 310 335  \n
0000024
```

`326 320` 就是「中」字的 GBK 字节。

用 `cat` 读它，判定出编码、解码成 UTF-8 输出：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat AI/数据/gbk_demo.txt
```

预期输出：

```
中文内容
第二行内容
```

对比一下字节：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat AI/数据/gbk_demo.txt | od -c
```

预期输出：

```
0000000 344 270 255 346 226 207 345 206 205 345 256 271  \n 347 254 254
0000020 344 272 214 350 241 214 345 206 205 345 256 271  \n
0000035
```

源文件 20 字节，输出 29 字节——9 个 GBK 汉字（18 字节）变成了 9 个 UTF-8 汉字（27 字节），两边各加 2 个换行字节。

**同一个文件走 stdin 就不解码**，因为 stdin 分支的编码写死 utf-8：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat - < AI/数据/gbk_demo.txt | od -c
```

预期输出：

```
0000000 326 320 316 304 304 332 310 335  \n 265 332 266 376 320 320 304
0000020 332 310 335  \n
0000024
```

字节守恒，与源文件完全一致。

这一处不对称是本文件最容易漏看的设计：编码判定是**按文件**做的，stdin 没有「文件头」可采样，也不做判定。

### 第 13 步：标准输入的三种写法

不给操作数就读标准输入：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'from stdin\n' | python main.py cat
```

预期输出：

```
from stdin
```

`-` 也表示标准输入：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'from stdin\n' | python main.py cat -
```

预期输出：

```
from stdin
```

文件和 `-` 可以混排，**位置就是读取顺序**：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'tail\n' | python main.py cat w2l/errors.py -
```

预期输出：

```
"""指令执行过程中使用的两类异常。"""


class UsageError(Exception):
    """用法错误，退出码 2。"""


class CommandError(Exception):
    """指令执行失败，退出码 1。"""
tail
```

stdin 的 CRLF 同样原样转交（走的是底层二进制流）：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'l1\r\nl2\r\n' | python main.py cat - | od -c
```

预期输出：

```
0000000   l   1  \r  \n   l   2  \r  \n
0000010
```

### 第 14 步：错误路径

文件不存在，退出码 2：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat nope.txt
```

预期输出（退出码 2）：

```
cat: 无法打开 'nope.txt': No such file or directory
```

出错不影响其余文件——打不开的文件只报错，后面的文件照常输出：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat nope.txt w2l/errors.py 2>&1
```

预期输出（退出码 2）：

```
cat: 无法打开 'nope.txt': No such file or directory
"""指令执行过程中使用的两类异常。"""


class UsageError(Exception):
    """用法错误，退出码 2。"""


class CommandError(Exception):
    """指令执行失败，退出码 1。"""
```

错误信息走 stderr、文件内容走 stdout，是两路输出。`2>&1` 把两路合并成一路后，错误行排在最前面，原因是 **stderr 不缓冲、而重定向到管道时 stdout 是块缓冲**：stderr 立刻落盘，stdout 要等进程退出才整体刷出。所以合并重定向时错误行先到。

目录当操作数：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat w2l
```

预期输出（退出码 2）：

```
cat: 无法打开 'w2l': 是一个目录
```

GNU cat 在这两种情况下返回 1，本项目按统一的退出码约定返回 2。

### 第 15 步：看看内部的判定过程

想看编码判定到底选了什么，可以直接调内部函数：

```bash
cd E:\1\NULL\Windows-to-Linux
python -c "from w2l.commands.cat import _candidate_encodings;print(_candidate_encodings())"
```

预期输出：

```
['utf-8', 'gb18030', 'latin-1']
```

本机开了 `PYTHONUTF8=1`，所以系统首选编码就是 utf-8，候选表里没有 cp1252。在没开这个开关的机器上，首选编码会是 `cp936`（中文 Windows）或 `cp1252`（英文 Windows），候选表相应变长。

打分对比：

```bash
cd E:\1\NULL\Windows-to-Linux
python -c "from w2l.commands.cat import _text_score;print(_text_score('中文内容'), _text_score('ÖÐÎÄÄÚÈÝ'))"
```

预期输出：

```
3.0 0.19999999999999998
```

同一串 GBK 字节，解成中文得 3.0 分，解成乱码得 0.2 分。差 15 倍，这就是 `_detect_encoding` 能稳定选对编码的原因。

含 NUL 判为二进制：

```bash
cd E:\1\NULL\Windows-to-Linux
python -c "from w2l.commands.cat import _pick_encoding;print(_pick_encoding(b'a\x00b'))"
```

预期输出：

```
utf-8
```

返回 `'utf-8'` 不是说它是文本，而是说「按二进制路径处理，用 utf-8 加 surrogateescape 解码，保证字节守恒」。

