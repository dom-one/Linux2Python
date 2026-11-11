# w2l/commands/wc.py — 列宽模型与词数判定

`w2l/commands/wc.py` 有 577 行。它统计的东西本身很简单——行、词、字符、字节、最长行——但「怎么算」这件事上，GNU wc 有一整套不写下来就会踩的规矩：列的顺序是固定的，词不只按空白切，`-L` 数的是显示宽度而不是字符数，列宽是所有计数列共用一个宽度。

这四条规矩，每一条都能让「照着 GNU 的输出手写一个 wc」写错。本篇把它们的实测依据写清楚，并如实标出本实现与 GNU 8.32 的三处真实差异。

## 为什么这么创建

### 决定一：列的顺序固定，不跟选项书写顺序走

GNU wc 的帮助里写死了这件事：

> The options below may be used to select which counts are printed, always in the following order: newline, word, character, byte, maximum line length.

本项目把它钉成一个常量：

```python
# 列的固定顺序：行 → 词 → 字符 → 字节 → 最长行。
_COLUMN_ORDER = ("lines", "words", "chars", "bytes", "max_line_length")
```

打印时按这个常量遍历，而不是按用户写选项的顺序。实测 `-lwc` 和 `-wlc` 输出完全一样：

```bash
printf 'a b\nc\n' | python main.py wc -wlc
```

预期输出（与 `wc -lwc` 一模一样）：

```
      2       3       6
```

**为什么要固定**：调用方要拿 wc 的输出做解析。如果列序跟着选项走，脚本就必须先解析一遍命令行才知道第几列是什么。固定列序意味着「第 1 列永远是行数」，解析代码只要按位置取。

### 决定二：词有两条「按空白切」之外的规则

朴素实现是「按空白切片段，片段个数就是词数」。GNU 8.32 不是这样，它多两条：

1. **片段里夹着控制字符不算断开**：`a\x01b` 算一个词，不是两个
2. **整个片段里一个可打印字符都没有时不算词**：纯二进制内容的词数是 0

第一条实测：

```bash
printf 'a\001b\n' | python main.py wc -lw
```

预期输出（1 行、1 个词）：

```
      1       1
```

第二条实测：

```bash
printf '\001\002\003\n' | python main.py wc -lw
```

预期输出（1 行、0 个词）：

```
      1       0
```

本项目的实现用一个状态机同时管这两条：

```python
def _count_words(text: str) -> int:
    words = 0
    in_word = False
    printable = False
    for char in text:
        if char in _WHITESPACE:
            if in_word:
                if printable:
                    words += 1
                in_word = False
                printable = False
            continue
        in_word = True
        if _is_printable(char):
            printable = True
    if in_word and printable:
        words += 1
    return words
```

`in_word` 管「片段有没有开始」，`printable` 管「片段里有没有出现过可打印字符」。空白只结束片段，不清 `printable` 之外的东西；控制字符既不是空白（不结束片段）也不是可打印字符（不置 `printable`）。两句话说完就是上面两条规则。

**「可打印」的判据**用的是 Unicode 类别，不是 ASCII 范围：

```python
def _is_printable(char: str) -> bool:
    return unicodedata.category(char) not in ("Cc", "Cf", "Cs")
```

`Cc` 是控制字符、`Cf` 是格式字符（如零宽连接符）、`Cs` 是代理区。中文（`Lo`）、字母（`Ll`/`Lu`）都不在这三类里，所以中文算可打印，中文文件里的中文算词。

空白集合也是照 GNU 的抄的，一共六个：

```python
_WHITESPACE = " \t\n\r\v\f"
```

### 决定三：`-L` 数的是显示宽度

`-L` 不是「最长行有几个字符」，也不是「最长行有几个字节」，而是**最长行在终端上占几列**。四条规则，每条都有实测：

**制表符展开到下一个 8 的倍数。** `a\tb\tc` 的显示宽度是 17（a 占 1 列，制表符跳到第 8 列，b 占 1 列到第 9 列，制表符跳到第 16 列，c 占 1 列到第 17 列）：

```bash
printf 'a\tb\tc\n' | python main.py wc -L
```

预期输出：

```
17
```

**回车把列号清零。** `abc\rdef` 的宽度是 3，不是 6——`\r` 之后的列号从头算：

```bash
printf 'abc\rdef\n' | python main.py wc -L
```

预期输出：

```
3
```

**取的是这一行出现过的最大列号，不是最后一行的长度。** `abcdef\rxy` 的宽度是 6：前半段最宽到第 6 列，`\r` 之后虽然又写了 2 个字符，但那一段的列号从 0 开始，最大也就 2，不超过前面的 6：

```bash
printf 'abcdef\rxy\n' | python main.py wc -L
```

预期输出：

```
6
```

**全角字符占 2 列，组合字符占 0 列。** 一个 UTF-8 的「中文」是 2 个字符、3 个字节、显示宽度 4：

```bash
printf '\xe4\xb8\xad\xe6\x96\x87\x0a' | python main.py wc -lwc -m -L
```

预期输出（1 行、1 词、3 字符、7 字节、显示宽度 4）：

```
      1       1       3       7       4
```

实现上，制表符和回车单独处理，其余字符交给 `_char_width`：

```python
def _display_width(text: str) -> int:
    width = 0
    widest = 0
    for char in text:
        if char == "\t":
            width = (width // _TAB_STOP + 1) * _TAB_STOP
        elif char == "\r":
            width = 0
        else:
            width += _char_width(char)
        if width > widest:
            widest = width
    return widest
```

`widest` 记的是「出现过的最大列号」，这就是为什么 `\r` 之后的内容不会覆盖掉前面更宽的那一段。

### 决定四：列宽按列算，GNU 是所有列共用一个宽度

这是本实现与 GNU 8.32 唯一一处**结构性**的差异，也是最容易被忽略的一处。

GNU 8.32 的 `src/wc.c` 里，列宽由一个函数算出来：

```c
static int
compute_number_width (size_t nfiles, struct fstatus const *fstatus)
{
  int width = 1;

  if (0 < nfiles && fstatus[0].failed <= 0)
    {
      int minimum_width = 1;
      uintmax_t regular_total = 0;

      for (size_t i = 0; i < nfiles; i++)
        if (! fstatus[i].failed)
          {
            if (S_ISREG (fstatus[i].st.st_mode))
              regular_total += fstatus[i].st.st_size;
            else
              minimum_width = 7;
          }

      for (; 10 <= regular_total; regular_total /= 10)
        width++;
      if (width < minimum_width)
        width = minimum_width;
    }

  return width;
}
```

拆开说是三条：

1. **所有计数列共用一个 `number_width`**（打印时 `printf ("%*s", number_width, ...)`），不是每列各算各的。
2. 这个宽度的值 = **所有普通文件字节数之和的位数**。注意是「之和」，不是「最大的那个」。
3. 只要有一个来源不是普通文件（标准输入、目录），宽度下限提到 **7**。
4. 另有一条特判在 `get_input_fstatus` 里：**只有一个文件、只打开一列**时直接 `failed = 1`，`compute_number_width` 就返回 1——此时连 `stat` 都不做，也就不补空格。

本项目把这条规则换成了另一套：

```python
floor = len(str(regular_bytes))
if unknown_size:
    floor = max(floor, _UNKNOWN_SIZE_WIDTH)
aligned = options.column_count >= 2 or total_printed

widths: dict[str, int] = {}
for column in _COLUMN_ORDER:
    if not options.enabled(column):
        continue
    width = 1
    for _, counts in rows:
        width = max(width, len(str(counts.value(column))))
    if aligned:
        width = max(width, floor)
    widths[column] = width
```

即：**每列先按自己这一列出现过的最大计数定下限，再按「普通文件字节数之和的位数」撑开**。

两套规则只在一种情况下会看出差别：**某一列自己的计数位数超过了字节总和的位数**。这在 `-l/-w/-m/-c` 上不可能发生（计数不会超过字节数），但 `-L` 会——制表符展开后显示宽度可以远大于字节数。

造两个文件看差别：`wide.dat` 是 `a\tb\tc\n`（6 字节，显示宽度 17），`small.dat` 是 `x\n`（2 字节）。字节总和 8，1 位；`-L` 列的值是 17，2 位。

项目：

```bash
m=$(pwd)/main.py && d=$(mktemp -d) && cd "$d" && printf 'a\tb\tc\n' > wide.dat && printf 'x\n' > small.dat && python "$m" wc -lL wide.dat small.dat
```

预期输出（第二列补到 2 位，`1` 前面多一个空格）：

```
1 17 wide.dat
1  1 small.dat
2 17 total
```

GNU：

```bash
d=$(mktemp -d) && cd "$d" && printf 'a\tb\tc\n' > wide.dat && printf 'x\n' > small.dat && wc -lL wide.dat small.dat
```

预期输出（两列共用一个宽度 1，`17` 直接写长不截断）：

```
1 17 wide.dat
1 1 small.dat
2 17 total
```

**为什么本实现要分开算**：`17` 这种超长值出现时，共用一个宽度会让别的列写歪（GNU 的 `1 1 small.dat` 里两列的数字是顶格对齐的，看起来不像一张表）。按列算让每一列各自整齐，代价是同一批文件里不同列的宽度可能不一样，与 GNU 不一致。

**共同的边界**：`%*s` 这类格式化不会截断，计数比预留宽度长时直接写长。所以 total 行的字节数可以比前面的行更宽——项目在 `_write_row` 里也是这么做的。

### 决定五：先判文本还是二进制，再决定怎么数

`-m`（字符数）必须先把字节解码成文本，解码就要知道编码。判定的链条是：

```python
def _pick_encoding(sample: bytes) -> str:
    if b"\x00" in sample:
        return _BINARY_ENCODING
    if _is_text(sample):
        return _detect_encoding(sample)
    return _BINARY_ENCODING
```

三步：含 NUL 字节 → 直接按二进制处理；能被某个候选编码**严格**解码 → 是文本，交给 `_detect_encoding` 打分选一个；都不是 → 二进制。

打分函数 `_text_score` 按「每字符平均分」算：ASCII 可打印字符 1 分、CJK 3 分、全角标点 1 分、制表符/换行/回车 0.5 分、高位乱码字节 0.2 分。取分最高的编码，而且要**领先当前最优 0.3 分以上**（`_SCORE_MARGIN`）才换人——分差不够就当平手，保留候选序里靠前的那个。候选序是 `utf-8` → 系统首选 → `gb18030` → `latin-1`，其中 `latin-1` 能解码任意字节，会把二进制全判成文本，所以在 `_is_text` 里被显式排除。

系统首选这一项在英文 Windows 上是 cp1252，它几乎不报错，能把 GBK 字节解成「乱码但成功」，所以**不能按顺序取第一个能解的编码**，必须打分。

实测两个中文样本：

```bash
printf '\xd6\xd0\xce\xc4\x0a' | python main.py wc -lwc -m -L
```

预期输出（GBK 的 2 个汉字：1 行、1 词、3 字符、5 字节、宽度 4）：

```
      1       1       3       5       4
```

## 这个文件是做什么

一句话：**按 GNU wc 的规矩统计行数、词数、字符数、字节数、最长行显示宽度**。

### 文件内的六块

| 行号 | 内容 |
|---|---|
| 1–31 | 模块文档字符串：把对齐 GNU 的部分和与 GNU 的差异逐条写下来 |
| 47–62 | 常量：嗅探大小、读取块大小、打分边际、CJK 区间、兜底编码、二进制编码、未知大小预留宽度 7、制表位 8、空白集合、固定列序 |
| 65–102 | 两个 `frozen dataclass`：`_Options`（哪些列要打印）、`_Counts`（五个计数值） |
| 105–125 | `build_parser()`：五个开关 + 一个位置参数 |
| 128–190 | `wc()` 主函数：遍历操作数、分类处理（`-`／目录／普通文件）、累加 total、算列宽、逐行输出、决定退出码 |
| 193–575 | 各种零件：`_build_options`、`_add`、`_column_widths`、`_write_row`、`_Source`、`_resolve`、`_stdin_chunks`、`_chunks`、`_count_stream`、`_split_lines`、`_count_words`、`_is_printable`、`_decode`、`_decode_bytes`、`_display_width`、`_char_width`，以及编码判定那一组 |

### 参数表

| 参数 | 含义 |
|---|---|
| `-l, --lines` | 打印行数 |
| `-w, --words` | 打印词数 |
| `-m, --chars` | 打印字符数 |
| `-c, --bytes` | 打印字节数 |
| `-L, --max-line-length` | 打印最长行的显示宽度 |
| `files ...` | 要统计的文件；`-` 表示标准输入；不填则读标准输入（且那一行不写文件名） |

不给任何开关时，打印「行 词 字节」三列。

### 退出码

| 码 | 什么时候 |
|---|---|
| 0 | 全部操作数都统计成功 |
| 2 | 至少有一个操作数打不开或是一个目录（GNU wc 这里是 1） |

出错时**不影响其它文件继续统计**，并且**打不开的文件不输出计数行**，目录则输出一行全 0。

### 不负责什么

- 不负责终端渲染，`-L` 只给数字，画格子是别人的事
- 不负责并发读多个文件，GNU 8.32 也不做
- 不支持 `--files0-from`、`--total=only`、`-t` 这些 GNU 的扩展选项
- **编码判定这套逻辑在 `cat.py` 里另写了一份**（`_pick_encoding` / `_is_text` / `_detect_encoding` / `_candidate_encodings` / `_decode_sample` / `_text_score` 两个文件里都有）。这是已知的重复，本轮没有动它

## 有什么用

- **快速看一个仓库的规模**：`wc -lwc` 一次拿到行、词、字节三个数
- **找代码里的长行**：`wc -L` 找显示宽度最长的行，配合 `-L` 和排序能揪出超长行
- **和 GNU 对不上时定位差异**：本篇第二节列的三处差异，是「项目输出和 GNU 不一样」的最常见来源
- **脚本里解析 wc 输出**：列序固定这一点，就是为这种用法准备的

## 怎么用（过程教程）

### 第 1 步：先看默认输出

不给任何选项时是三列：行、词、字节。

```bash
printf 'hello world\n' | python main.py wc
```

预期输出：

```
      1       2      12
```

### 第 2 步：只打开一列

打开一列时**不做对齐**（GNU 在「一个文件 + 一列」时连 `stat` 都不做，宽度就是 1）。

```bash
printf 'a b\nc\n' | python main.py wc -l
```

预期输出：

```
2
```

### 第 3 步：把五列全打开

列序永远是「行 → 词 → 字符 → 字节 → 最长行」，跟选项写的顺序无关。

```bash
printf 'a b\nc\n' | python main.py wc -lwc -m -L
```

预期输出：

```
      2       3       6       6       3
```

### 第 4 步：行只按 `\n` 计

末行没有换行，**不算一行**，但里面的词照样算：

```bash
printf 'a\nb' | python main.py wc -lwc
```

预期输出（1 行、2 词、3 字节）：

```
      1       2       3
```

空输入则是三个 0：

```bash
printf '' | python main.py wc -lwc
```

预期输出：

```
      0       0       0
```

### 第 5 步：词的两条特殊规则

片段里夹控制字符，不断开：

```bash
printf 'a\001b\n' | python main.py wc -lw
```

预期输出：

```
      1       1
```

整个片段没有可打印字符，不算词：

```bash
printf '\001\002\003\n' | python main.py wc -lw
```

预期输出：

```
      1       0
```

### 第 6 步：`-L` 的显示宽度

制表符展开到 8 的倍数：

```bash
printf 'a\tb\tc\n' | python main.py wc -L
```

预期输出：

```
17
```

回车把列号清零：

```bash
printf 'abc\rdef\n' | python main.py wc -L
```

预期输出：

```
3
```

取行内出现过的最大列号：

```bash
printf 'abcdef\rxy\n' | python main.py wc -L
```

预期输出：

```
6
```

### 第 7 步：多个文件和 total 行

操作数多于一个时最后打一行 `total`。行/词/字符/字节求和，**最长行取最大值**（不是求和）。

```bash
python main.py wc w2l/errors.py w2l/context.py
```

预期输出：

```
  9   9 202 w2l/errors.py
 15  28 302 w2l/context.py
 24  37 504 total
```

### 第 8 步：标准输入

`-` 表示标准输入，那一行会写上文件名 `-`：

```bash
printf 'x\n' | python main.py wc -
```

预期输出：

```
      1       1       2 -
```

不给操作数也是读标准输入，但**那一行不写文件名**：

```bash
printf 'x\n' | python main.py wc
```

预期输出：

```
      1       1       2
```

重复的 `-` 只读一次标准输入，第二次读到的是空的，total 也只算一次：

```bash
printf 'x\n' | python main.py wc -lw - -
```

预期输出：

```
      1       1 -
      0       0 -
      1       1 total
```

### 第 9 步：出错时的行为

文件打不开：不输出计数行，只报错，退出码 2。

```bash
python main.py wc -l nonexistent.txt
```

预期输出（错误信息走 stderr，退出码 2）：

```
wc: 无法打开 'nonexistent.txt': No such file or directory
```

目录会输出一行全 0 并报错；缺的文件不输出计数行。两者混在一起时，**错误信息先打，计数行后打**（stderr 与 stdout 是两条流，合并后看到的是这个顺序）：

```bash
python main.py wc -lwc w2l nonexistent.txt
```

预期输出（退出码 2）：

```
wc: 无法打开 'w2l': 是一个目录
wc: 无法打开 'nonexistent.txt': No such file or directory
      0       0       0 w2l
      0       0       0 total
```

注意 total 行也在了——目录虽然统计不出内容，但它仍然算一个操作数。

### 第 10 步：跟 GNU 对不上时，先看这三处

**差异一：高位字节的词数。** 三个 0xA1 字节：

```bash
printf '\xa1\xa1\xa1' | env LC_ALL=C wc -w
```

预期输出（GNU 在 C 区域设置下把 0xA1 当可打印字符，算 1 个词）：

```
1
```

```bash
printf '\xa1\xa1\xa1' | python main.py wc -w
```

预期输出（本实现判定成 gb18030，解不出这三个字节，兜底解码把它们丢掉，算 0 个词）：

```
0
```

GNU 在 C 区域设置下把 0xA1–0xFF 当作单字节可打印字符，所以词数是 1、字符数是 3；本实现先判编码，判成 gb18030 之后解不出这三个字节，兜底解码（`_decode_bytes`）把它们直接跳过，于是词数 0、字符数 0。这是**设计上的取舍**：宁可承认「这几个字节我读不懂」，也不猜。

**差异二：多文件时的列宽。** 见「决定四」里那两条命令——项目按列算宽度，GNU 所有列共用一个宽度。

**差异三：编码判定会误判。** `e` 加一个组合重音 U+0301（UTF-8 编码是 65 CC 81）：

```bash
printf '\x65\xcc\x81\x0a' | env LC_ALL=C.utf8 wc -m -L
```

预期输出（GNU 的 C.utf8 区域设置：3 个字符，组合字符占 0 列所以宽度 1）：

```
      3       1
```

```bash
printf '\x65\xcc\x81\x0a' | python main.py wc -m -L
```

预期输出（本实现把这段判成 gb18030，解出来是 `e虂`，于是 3 个字符、宽度 3）：

```
      3       3
```

判定的过程是打分：这段字节 utf-8 得分 0.5667、gb18030 得分 1.5000、latin-1 得分 0.4750，gb18030 领先超过 `_SCORE_MARGIN = 0.3`，于是被选中。短文件里 ASCII 占绝对多数，utf-8 的分数被稀释，gb18030 就容易翻盘。

### 第 11 步：区域设置对 GNU 的影响（排查分歧时必看）

GNU 的 `-m` 和 `-w` 依赖区域设置，同一份输入换区域设置就是另一个结果。本机 `locale -a` 里的名字是 `C.utf8`、`zh_CN`、`zh_CN.utf8`——**没有 `C.UTF-8` 这个名字**，写错会静默退回默认区域设置。

GBK 中文（`\xd6\xd0\xce\xc4`）：

```bash
printf '\xd6\xd0\xce\xc4\x0a' | env LC_ALL=zh_CN wc -m -L
```

预期输出（GBK 区域设置：2 个汉字 + 换行 = 3 字符，宽度 4）：

```
      3       4
```

```bash
printf '\xd6\xd0\xce\xc4\x0a' | env LC_ALL=C.utf8 wc -m -L
```

预期输出（C.utf8 解不出 GBK 的字节，字符数记 1，宽度记 0）：

```
      1       0
```

```bash
printf '\xd6\xd0\xce\xc4\x0a' | python main.py wc -m -L
```

预期输出（本实现判定成 gb18030，与 GNU 在 zh_CN 区域设置下一致）：

```
      3       4
```

**注意**：`env` 必须放在 `wc` 前面。写成 `LC_ALL=zh_CN wc ...` 只能影响 `wc` 自己，`printf` 那半截还是默认区域设置；要改整条管道就写 `printf ... | env LC_ALL=zh_CN wc ...`。

### 第 12 步：自己加一列看看

想知道项目是怎么把五列拼成一行输出的，看 `_write_row`：

```python
parts = []
for column in _COLUMN_ORDER:
    if not options.enabled(column):
        continue
    parts.append(f"{counts.value(column):>{widths[column]}d}")
line = " ".join(parts)
if name is not None:
    line = f"{line} {name}"
```

每一列按 `_COLUMN_ORDER` 的顺序取、格式化，右对齐到该列宽度，列之间用一个空格隔开，文件名跟在最后一个空格后面。第一列前面没有多余的空格，列间的那个空格是分隔符——这一点和 GNU 的 `printf (format_int, number_width, ...)` 写法一致（GNU 第一列用 `"%*s"`，后面几列用 `" %*s"`）。

### 第 13 步：跑一遍测试

`tests/test_wc.py` 有 23 个用例。`pyproject.toml` 里已经配了 `addopts = "-q"`，裸跑就是安静模式；这里用 `tail -1` 只留最后那行摘要，省掉进度点那行的对齐空格（那一行的空格数跟终端宽度有关，每次可能不同）。

```bash
python -m pytest tests/test_wc.py 2>&1 | tail -1
```

预期输出（耗时每次不同，用 `<T>` 占位）：

```
23 passed in <T>s
```
