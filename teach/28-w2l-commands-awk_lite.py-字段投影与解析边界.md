# w2l/commands/awk_lite.py — 字段投影与解析边界

`w2l/commands/awk_lite.py` 有 580 行，注册出来的指令叫 **`awk-lite`**（注意是连字符，模块名是下划线）。它做的事只有一件：**把一行按字段切开，取其中几列打印出来**。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite '{print $1}' AI/数据/awk_demo/app.log          # 取第一列
python main.py awk-lite -F, '{print $NF}' AI/数据/awk_demo/access.csv  # 按逗号切，取最后一列
MSYS_NO_PATHCONV=1 python main.py awk-lite '/ERROR/ {print $2}' AI/数据/awk_demo/app.log
```

awk 的完整能力很大（算术、数组、函数、`BEGIN`/`END`、`printf`、管道输出……），本实现只做了「字段投影 + 正则筛行」这一小块。**没做的部分一律明确报错，不静默忽略**——这是本文件最重要的设计取向，也是它和 GNU awk 最大的分歧来源。

本轮实测查出：**16 处与 GNU awk 5.3.2 的行为差异**（其中 3 处是实质性的语义分歧，其余是有意的取舍），以及 **11 个能让程序抛 Python traceback 的输入**（属源码缺陷，本轮只记录不修）。另外还掉进了一个「探针自己骗人」的坑：差分脚本第一版报出的「GNU awk 不认 `{print}`」根本不是 GNU 的行为，是 MSYS 运行时改写了 argv。都写在最后两节。

## 为什么这么创建

### 决定一：只做「字段投影」，其余一律报错

`awk_lite()`（第 120~176 行）的主循环只有三件事：读文件、逐行切字段、按程序决定打印什么。程序文本在 `_parse_program`（第 184~205 行）里被拆成两段：

| 程序长什么样 | 解析结果 |
|---|---|
| `{print $1}` | 只有动作，没有模式 |
| `/ERROR/` | 只有模式，没有动作（打印整行） |
| `/ERROR/ {print $2}` | 模式 + 动作 |

拆不出这两段的，一律 `UsageError`：

```python
    raise UsageError(
        f"看不懂的程序 {text!r}：只支持 {{print ...}} 动作或 /正则/ 模式"
        "（在 Git Bash 里以 / 开头的参数会被 MSYS 改写成路径，试 MSYS_NO_PATHCONV=1）"
    )
```

**为什么宁可报错也不静默忽略**：awk 的默认行为是「算术表达式里的字符串自动转数字」「没赋值的变量当 0」「`$1 ""` 拼成 `$1`」。这些「宽容」在别的语言里是便利，在字段投影工具里是**算错还不报错**。本实现选择把「我算不了」说清楚。

实测代价是：同一个程序在 GNU awk 下能跑、在本实现下报错，会让人以为本实现更弱。哪些不支持、报错长什么样，第 8 步有实测。

### 决定二：模块名用下划线，指令名用连字符

```python
@command("awk-lite", "按字段取值（GNU awk 风格子集）", build_parser)
def awk_lite(args: argparse.Namespace, ctx: RunContext) -> int:
```

两个名字不一样是必须的：Python 的模块名不能带连字符（`import awk-lite` 是语法错误），而命令行上 `awk` 这个名字不能占——Windows 自带的 `awk` 不是 GNU 的，但 Git Bash 的 `awk` 是，得让开。

所以：**文件名 `awk_lite.py`，命令行 `awk-lite`**。`w2l/commands/__init__.py` 靠扫描模块里的 `@command` 装饰器自动发现指令，文件名和指令名不必一致（`sed.py` 注册成 `sed` 是巧合）。

### 决定三：模式是正则（ERE），用 Python 的 `re` 直接编译

`_compile_regex`（第 230~234 行）没有做任何方言翻译：

```python
def _compile_regex(pattern: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise UsageError(f"无效的正则表达式 '{pattern}': {exc}") from exc
```

Python 的 `re` 本来就是 ERE 语义，与 GNU awk 的默认方言一致，所以省掉一层翻译。代价是 `\w`、`\d` 这类在 gawk 里受 locale 影响、在 Python 里恒为 Unicode 语义——中文环境下 gawk 的 `\w` 不认汉字，Python 的认。

正则里的 `/` 用 `\/` 转义，`_split_regex`（第 208~227 行）逐字符扫。

### 决定四：分隔符分三档，与 GNU 的规则一致

`_make_splitter`（第 471~488 行）是本文件语义最需要记住的一段：

```python
    if separator is None or separator == "" or separator == " ":
        return _split_whitespace
    if len(separator) == 1:
        return lambda line: line.split(separator)
    try:
        pattern = re.compile(separator)
    except re.error as exc:
        raise UsageError(f"无效的分隔符正则 '{separator}': {exc}") from exc
    if pattern.search("") is not None:
        raise UsageError(f"分隔符正则 '{separator}' 能匹配空串，没法用来切字段")
    return lambda line: pattern.split(line)
```

| `-F` 给的值 | 怎么切 | 例 |
|---|---|---|
| 不给 / 空串 / 单个空格 | 按**空白串**切，连续空白算一个分隔，两端空白不算字段 | `a  b   c` → 3 个字段 |
| 单个字符 | 按**字面量**切（`.` 就是一个点，不是任意字符） | `a.b.c` → `a` `b` `c` |
| 多个字符 | 按**正则**切 | `-F '..'` 每两个字符切一刀 |

「空白串」用的是 `_WHITESPACE = " \t\n\r\v\f"`（第 42 行），**不是 `str.split()`**——`str.split()` 还认 NBSP 之类的 Unicode 空白，GNU 不认。

注意第三档：多字符分隔符按**正则**处理，所以 `-F '[XY]+'` 能用。但正则若能匹配空串，这里直接报错（GNU 是接受并给出别的结果，见后面差异一节）。

### 决定五：`-F` 的值解转义，`-v` 的值不解

这是文件里一处**不对称**：

- `_decode_separator`（第 455~468 行）只作用于 `-F` 的值：`\t` → 制表符、`\n` → 换行、`\r` → 回车、`\\` → 反斜杠。
- `-v name=value` 的值走 `_parse_assignments`（第 339~349 行），**只做 `partition("=")` 切一刀**，不解转义。

所以 `-F'\t'` 是制表符，`-v FS='\t'` 是**字面的反斜杠加 t**（两个字符），但后者因为长度是 2、会被当正则用，`\t` 这个正则恰好也匹配制表符——**碰巧对上了**，不是设计。

GNU 那边两条路都解转义，所以 `-v FS='\t'` 在 GNU 下是 1 个字符的制表符（按字面切），在本实现下是 2 个字符的正则（按正则切）。输入里只有制表符时结果一样，输入里有别的反斜杠序列时不一定。

### 决定六：数字输出走 CONVFMT `%.6g`，整数走 `int()` 快路径

`_format_number`（第 443~447 行）：

```python
def _format_number(number: float) -> str:
    """按 GNU awk 的 CONVFMT（默认 %.6g）把数字转成字符串。"""
    if number == int(number) and abs(number) < 1e16:
        return str(int(number))
    return "%.6g" % number
```

GNU awk 的默认 `CONVFMT` 就是 `%.6g`，所以小数部分两边一致（`3.14159265358979` → `3.14159`）。整数部分本实现走 `str(int(...))` 快路径。

**门槛 `1e16` 是本实现自己定的，GNU 不是这么算的**：GNU 对整数用精确算术打印，`1e23` 会打成 `99999999999999991611392`（双精度能表示的精确值），本实现在 `1e16` 就转科学计数了。这是一处实质差异，见后面差异一节。

**这一段同时是本文件的崩溃点**：`int(inf)` 抛 `OverflowError`，`int(nan)` 抛 `ValueError`，而 `_to_number`（第 433~440 行）用的是 Python 的 `float()`，它接受 `inf`/`nan`/`1e400`。

### 决定七：编码靠「文本可信度打分」，不靠「第一个能解的」

`_detect_encoding`（第 527~544 行）与 `cat.py`、`sed.py` 同一套思路：先嗅探前 8192 字节（`_SNIFF_SIZE`），挨个候选编码解码后打分（`_text_score`，第 564~579 行），得分最高的胜出。`_SCORE_MARGIN = 0.3` 是「换编码要领先这么多分才换」。

为什么不能取「第一个能解的」：英文 Windows 的系统首选编码是 cp1252，它几乎不报错，能把 GBK 字节解成乱码，按顺序取第一个可解码的会让中文内容彻底搜不到。

**代价是输出被统一成 UTF-8**：GBK 文件读进来解码成 Unicode，再按 UTF-8 写出。GNU 是字节透传。这是项目一贯的取舍。

### 决定八：字段取值与变量取值分成两条路

`_lookup`（第 384~401 行）处理变量，`_field_value`（第 404~423 行）处理 `$` 引用，两条路的兜底行为不同：

| 写法 | 本实现 | GNU awk |
|---|---|---|
| `{print foo}`（foo 没赋值） | 报错退出 2 | 打印空行（未初始化变量当空串） |
| `{print $foo}`（foo 没赋值） | 报错退出 2 | 打印整行（未初始化变量当 0，$0 就是整行） |
| `{print $n}`（`-v n=2`） | 取第 2 个字段 | 同 |
| `{print $n}`（`-v n=abc`） | 按整行处理 | 同（本实现没有具名字段） |

## 这个文件是做什么

### 数据流

```
命令行 argv
   │
   ├─ build_parser() 解析出 program / files / -F / -v
   │
   ├─ _parse_program(program) ──► _Program(pattern=正则 或 None, items=[_Item] 或 None)
   │        │
   │        └─ _parse_action → _split_commas → _parse_item（每个参数一个 _Item）
   │
   ├─ _parse_assignments(-v) ──► {"FS": "...", "OFS": ";", ...}
   │
   ├─ 分隔符定档：-F 优先，其次 -v FS=，都没有则按空白串
   │
   └─ 逐条记录 _Record(line, fields, nr, fnr, filename)
            │
            └─ _emit ──► 模式不命中就跳过
                         模式命中且 items 为 None → 打整行
                         否则 _value_of 逐个取值，用 OFS 连接，用 ORS 收尾
```

### 选项清单

| 选项 | 含义 | 源码位置 |
|---|---|---|
| `program`（位置参数） | 要执行的程序：`{print ...}` 动作、`/正则/` 模式，或两者组合 | 第 98 行 |
| `files`（位置参数） | 输入文件；不给则读标准输入；`-` 也表示标准输入 | 第 99 行 |
| `-F SEP` / `--field-separator SEP` | 字段分隔符，默认按空白串切分 | 第 100~107 行 |
| `-v NAME=VALUE` / `--assign NAME=VALUE` | 给变量赋值，可给多次 | 第 108~116 行 |

### 退出码

| 退出码 | 什么时候 |
|---|---|
| `0` | 处理完了。**没有输出也是 0**，与 GNU awk 一致（不是本项目「命中类指令无结果返回 1」那套） |
| `2` | 用法或运行错误：程序写错、变量没赋值、文件读不到、目录当文件用、正则无效 |

中间的文件读不到时会**跳过并继续处理后面的文件**，最后统一返回 2（GNU 是直接 fatal 停下，见差异一节）。

### 文件里的结构

| 分段 | 行 | 内容 |
|---|---|---|
| 参数解析 | 第 84~176 行 | `build_parser` 与 `awk_lite` 主函数 |
| 程序解析 | 第 184~349 行 | `_parse_program` / `_split_regex` / `_parse_action` / `_split_commas` / `_parse_item` / `_parse_assignments` |
| 取值 | 第 357~447 行 | `_emit` / `_value_of` / `_lookup` / `_field_value` / `_as_text` / `_to_number` / `_format_number` |
| 切分与读取 | 第 455~579 行 | `_decode_separator` / `_make_splitter` / `_split_whitespace` / `_iter_stdin` / `_decode_lines` / `_detect_encoding` / `_text_score` |

## 有什么用

### 它能替代什么

一行当整体看的时候用 `grep`，一行拆成几列取的时候用 `awk-lite`。典型场景：

- 从访问日志里取状态码：`awk-lite -F, '{print $3}' access.csv`
- 从日志里挑出错误行再取某列：`awk-lite '/ERROR/ {print $2}' app.log`
- 多文件合并统计时按行号对齐：`awk-lite '{print NR, $1}' a.log b.log`
- 把某一列固定住：`awk-lite -v n=2 '{print $n}' app.log`

### 它替代不了什么

GNU awk 的完整能力一概没有：**算术、字符串拼接、`printf`、`BEGIN`/`END`、数组、自定义函数、变量赋值语句、管道输出**都报用法错误。遇到这些，要么改用本项目的 `sed`（按行改写）、`wc`（统计）、`grep`（筛行），要么直接用 Git Bash 自带的 `awk`。

### 和 GNU awk 的关系

它是 GNU awk 的**子集**，不是替代品。设计目标不是「行为一致」，而是「常用的一小块能对得上 GNU，剩下的明确说不支持」。本轮对拍了 82 组用例，其中 59 组输出逐字节一致，23 组不一致——不一致的都在下面列出来了。

## 怎么用（过程教程）

### 第 1 步：准备演示夹具

夹具放在 `AI/数据/awk_demo/`（该目录在 `.gitignore` 里，不进版本库）。造它的脚本是 `AI/脚本/_t1306_make_awk_demo.py`：

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1306_make_awk_demo.py
```

产出 8 个文件：

| 文件 | 内容 |
|---|---|
| `app.log` | `INFO start app` / `ERROR failed db` / `warn  retry queue` / `ERROR again db` |
| `two.log` | `INFO second file` / `ERROR tail error` |
| `access.csv` | `10.0.0.1,GET,200,1024` 等三行 |
| `semi.log` | `a;b;c` / `d;e;f` |
| `gap.log` | `a;;c` |
| `blank.log` | 两个空行 + `x y` |
| `nonl.log` | `one two`（末行没有换行符） |
| `gbk.log` | GBK 编码的中文两行 |

下面的命令都在仓库根目录（`E:\1\NULL\Windows-to-Linux`）下跑，夹具路径写全成 `AI/数据/awk_demo/...`，这样每个块都能单独复制执行。

### 第 2 步：三种最基础的取字段

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite '{print $1}' AI/数据/awk_demo/app.log
```

预期输出：

```
INFO
ERROR
warn
ERROR
```

`$NF` 是最后一个字段：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite '{print $NF}' AI/数据/awk_demo/app.log
```

预期输出：

```
app
db
queue
db
```

裸 `print` 等价于 `{print $0}`，打整行：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite '{print}' AI/数据/awk_demo/app.log
```

预期输出：

```
INFO start app
ERROR failed db
warn  retry queue
ERROR again db
```

多个参数之间用 **OFS**（默认一个空格）连接：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite '{print $1, $2}' AI/数据/awk_demo/app.log
```

预期输出：

```
INFO start
ERROR failed
warn retry
ERROR again
```

注意 `warn  retry queue` 那一行：源文件里 `warn` 和 `retry` 之间有**两个空格**，但默认分隔符按「空白串」切，两个空格算一个分隔，所以打出来是 `warn retry`（一个空格）。

字段号超出范围是空串，不报错：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite '{print $9}' AI/数据/awk_demo/app.log
```

预期输出是四个空行。

### 第 3 步：用正则筛行

只给模式时，打印**命中的整行**：

```bash
cd E:\1\NULL\Windows-to-Linux
MSYS_NO_PATHCONV=1 python main.py awk-lite '/ERROR/' AI/数据/awk_demo/app.log
```

预期输出：

```
ERROR failed db
ERROR again db
```

**`MSYS_NO_PATHCONV=1` 不能省**。程序文本以 `/` 开头时，Git Bash 的 MSYS 运行时会把它当成 POSIX 路径改写：

```
错误: 看不懂的程序 'E:/software/Git/Git/ERROR/'：只支持 {print ...} 动作或 /正则/ 模式
（在 Git Bash 里以 / 开头的参数会被 MSYS 改写成路径，试 MSYS_NO_PATHCONV=1）
```

这是本项目已知的坑（README 里也写了），不是 `awk-lite` 的解析问题。**从 cmd.exe 或 PowerShell 里调用不用加这个变量**（那两条路上没有 MSYS 运行时）。

模式加动作，就只对命中的行做动作：

```bash
cd E:\1\NULL\Windows-to-Linux
MSYS_NO_PATHCONV=1 python main.py awk-lite '/ERROR/ {print $2}' AI/数据/awk_demo/app.log
```

预期输出：

```
failed
again
```

### 第 4 步：`-F` 换分隔符

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite -F, '{print $NF}' AI/数据/awk_demo/access.csv
```

预期输出：

```
1024
256
4096
```

同时取两列：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite -F, '{print $1, $3}' AI/数据/awk_demo/access.csv
```

预期输出：

```
10.0.0.1 200
10.0.0.2 404
10.0.0.3 200
```

**分号当分隔符要加引号**：`-F;` 会被 bash 当成命令分隔符，后面的 `{print ...}` 就成了另一条命令。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite -F';' '{print $2}' AI/数据/awk_demo/semi.log
```

预期输出：

```
b
e
```

单字符分隔符按**字面量**切，连续出现会切出**空字段**（GNU 行为）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite -F';' '{print $1, $2, $3}' AI/数据/awk_demo/gap.log
```

预期输出（`$1` 与 `$2` 之间是两个空格，因为 `$2` 是空串）：

```
a  c
```

多个字符的分隔符按**正则**切：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite -F'[XY]+' '{print $2}' AI/数据/awk_demo/multi.txt
```

`multi.txt` 的内容是 `aXXbXXc`，预期输出：

```
b
```

### 第 5 步：`-v` 变量

变量当字段号用：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite -v n=2 '{print $n}' AI/数据/awk_demo/app.log
```

预期输出：

```
start
failed
retry
again
```

变量直接打印：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite -v tag=INFO '{print tag}' AI/数据/awk_demo/app.log
```

输出四行 `INFO`。

改 OFS（多个参数之间的连接符）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite -v OFS=';' '{print $1, $2}' AI/数据/awk_demo/app.log
```

预期输出：

```
INFO;start
ERROR;failed
warn;retry
ERROR;again
```

**`-F` 优先于 `-v FS=`**（本实现的规定，与 GNU 不同，见差异一节）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite -v FS=, -F';' '{print $2}' AI/数据/awk_demo/semi.log
```

输出 `b` 和 `e`（用的是 `-F` 的分号）。

### 第 6 步：多文件与 NR / FNR / FILENAME

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite '{print NR, NF, FNR, FILENAME}' AI/数据/awk_demo/app.log AI/数据/awk_demo/two.log
```

预期输出：

```
1 3 1 AI/数据/awk_demo/app.log
2 3 2 AI/数据/awk_demo/app.log
3 3 3 AI/数据/awk_demo/app.log
4 3 4 AI/数据/awk_demo/app.log
5 3 1 AI/数据/awk_demo/two.log
6 3 2 AI/数据/awk_demo/two.log
```

- **NR** 跨文件连续（第 5、6 行是第二个文件的）
- **FNR** 每个文件从头算
- **NF** 是当前行的字段数
- **FILENAME** 是命令行里给的那个名字，**照抄不加工**（不是绝对路径，也不是 basename）

### 第 7 步：标准输入与 `-`

不给文件就读标准输入：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'a b\nc d\n' | python main.py awk-lite '{print $1}'
```

预期输出：

```
a
c
```

`-` 也表示标准输入，可以和文件混排，`NR` 照样连续：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'x y\n' | python main.py awk-lite '{print NR, $1}' AI/数据/awk_demo/app.log -
```

预期输出：

```
1 INFO
2 ERROR
3 warn
4 ERROR
5 x
```

读标准输入时 `FILENAME` 是 `-`（GNU awk 5.3.2 也是 `-`，两边一致）。

### 第 8 步：错误路径与退出码

不支持的写法一律报错，退出码 2：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite '{printf "%s", $1}' AI/数据/awk_demo/app.log
```

```
错误: 看不懂的 print 参数：'f "%s"'
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite '{print $1 + $2}' AI/数据/awk_demo/app.log
```

```
错误: 看不懂的字段引用 '$1 + $2'
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite '{print foo}' AI/数据/awk_demo/app.log
```

```
错误: 变量 'foo' 没有赋值：先用 -v foo=... 赋值
```

注意这三个报错的措辞都指向了**具体的语法位置**（`'f "%s"'`、`'$1 + $2'`、`'foo'`），这是 `_parse_item`（第 299~319 行）逐个参数解析、逐个报出来的结果。

文件读不到：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py awk-lite '{print $1}' AI/数据/awk_demo/nope.log
```

```
AI/数据/awk_demo/nope.log: No such file or directory
```

退出码 2。

### 第 9 步：跑相关测试

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest tests/test_awk_lite.py
```

```
45 passed in 0.25s
```

全量：

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q
```

615 条用例。`pyproject.toml` 里的 `addopts = "-q"` 让 `-q` 变成两个 `-q`，输出被压成三行进度点，看不到具体条数——这是项目里所有教程都提过的一点。

### 第 10 步：与 GNU awk 5.3.2 对拍

本轮的实测脚本在 `AI/脚本/` 下：

| 脚本 | 干什么 |
|---|---|
| `_t1301_probe_awk_diff.py` | 82 组用例逐条对拍，产出 `AI/产物/awk-diff/cases.json` |
| `_t1302_probe_msys_braces.py` | 查 MSYS 运行时怎么改写 argv |
| `_t1303_probe_awk_numbers.py` | 查数字转字符串的分界 |
| `_t1304_probe_awk_crash.py` | 查哪些输入会让程序抛 traceback |
| `_t1305_probe_awk_cases.py` | 从 `cases.json` 里查指定用例 |

跑一遍：

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1301_probe_awk_diff.py
```

它会打印 82 组用例里哪几组不一致，完整的逐条结果落在 `AI/产物/awk-diff/cases.json`。

**这个脚本第一版是错的**，得说清楚：它把程序直接放在 argv 里传给 GNU awk，于是报出一堆「GNU awk 不认 `{print}`」的假差异。真实情况见下一节。

## 实测出的与 GNU awk 5.3.2 的差异

82 组用例里 59 组输出逐字节一致，23 组不一致。按性质分成六组。

### A 组：数字与字符串（4 处）

**第 1 处：整数常量的门槛，本项目 1e16，GNU 没有门槛**

| 字面量 | 本项目 | GNU awk 5.3.2 |
|---|---|---|
| `1000000000000000`（1e15） | `1000000000000000` | `1000000000000000` |
| `10000000000000000`（1e16） | `1e+16` | `10000000000000000` |
| `100000000000000000`（1e17） | `1e+17` | `100000000000000000` |
| `1000000000000000000000`（1e21） | `1e+21` | `1000000000000000000000` |
| `100000000000000000000000`（1e23） | `1e+23` | `99999999999999991611392` |

GNU 对整数用精确算术打印，`99999999999999991611392` 是双精度能表示的 1e23 的**精确值**（不是 `1e23` 的近似）。本实现 `_format_number` 的 `abs(number) < 1e16` 是自己定的门槛，到 1e16 就转 `%.6g`。

小数两边一致（都走 `%.6g`）：`3.14159265358979` → `3.14159`，`0.1` → `0.1`。

**第 2 处：`-v` 赋的值，GNU 当字符串，本实现当数字**

| `-v` 的值 | 本项目 | GNU awk |
|---|---|---|
| `x=007` | `7` | `007` |
| `x=1e3` | `1000` | `1e3` |
| `x=1.5` | `1.5` | `1.5` |
| `x=0x10` | `0x10` | `0x10` |

GNU 把命令行赋值当**字符串**存，打印时原样输出；本实现的 `_as_text`（第 426~430 行）会把能转成数字的字符串转成数字再打。

**在动作里赋值就不一样了**——GNU 打的是数值：

```awk
BEGIN { x = 007; print x }     # GNU 打 7
```

所以 GNU 的规则是「命令行赋值是字符串，程序里赋值是数字」，本实现没有这个区分。

**第 3 处：Python 的 `float()` 接受的写法比 awk 多**

| `-v` 的值 | 本项目 | GNU awk |
|---|---|---|
| `x=1_000` | `1000` | `1_000` |
| `x=1_0.5` | `10.5` | `1_0.5` |

Python 3.6+ 的 `float()` 允许数字字面量里带下划线，awk 不允许。这跟第 2 处是同一个根因（`_to_number` 用了 `float()`）。

**第 4 处：无穷大与 NaN 会让程序崩**（下一节详列）

### B 组：分隔符（2 处）

**第 5 处：`-F ''`（空串）**

| `-F ''` | 行为 |
|---|---|
| 本项目 | 当成「没给分隔符」，按空白串切 |
| GNU awk | **逐字符切**，每个字符一个字段 |

实测 `app.log` 的四行（长度 14、15、17、14）：

```
本项目：3 3 3 3        （每行的空白串字段数）
GNU  ：14 15 17 14    （每行的字符数）
```

**第 6 处：`-F` 给一个能匹配空串的正则**

| `-F 'x*'` | 行为 |
|---|---|
| 本项目 | 报错退出 2：「分隔符正则 'x*' 能匹配空串，没法用来切字段」 |
| GNU awk | 接受，`NF` 恒为 1（整行当成一个字段） |

GNU 是「匹配空串但不真的切」，本实现选择直接拒绝。

### C 组：选项优先级（1 处）

**第 7 处：`-F` 与 `-v FS=` 谁赢**

| 命令 | 本项目 | GNU awk |
|---|---|---|
| `-F';' -v FS=,'` | `-F` 赢（分号） | `-v FS=` 赢（逗号） |
| `-v FS=,' -F';'` | `-F` 赢（分号） | `-F` 赢（分号） |

GNU 的规则是**命令行上后出现的覆盖先出现的**，所以 `-v FS=,` 写在 `-F';'` 后面会把分隔符改回逗号。本实现的 `_make_splitter` 调用处（第 125~128 行）写死「`-F` 优先」：

```python
    separator = variables.get("FS")
    if args.field_separator is not None:
        separator = _decode_separator(args.field_separator)
```

README 里写的「`-F` 优先于 `-v FS=...`」是这个实现自己的约定，与 GNU 不一致。

### D 组：变量与表达式（3 处）

**第 8 处：未赋值的变量**

| 写法 | 本项目 | GNU awk |
|---|---|---|
| `{print foo}` | 报错退出 2 | 打印空行 |
| `{print $foo}` | 报错退出 2 | 打印整行 |

GNU 把未初始化变量当空串（当数字用时当 0），所以 `$foo` 退化成 `$0`。本实现报错——这是有意的严格化。

**第 9 处：相邻的字符串常量**

| 写法 | 本项目 | GNU awk |
|---|---|---|
| `{print "a" "b"}` | `a" "b` | `ab` |

GNU 会把相邻字符串**拼接**起来。本实现的 `_split_commas`（第 270~296 行）只按逗号切，`"a" "b"` 是「一个参数」，然后 `_parse_item` 剥掉首尾引号，中间的内容原样保留。

**第 10 处：字段与字符串拼接**

| 写法 | 本项目 | GNU awk |
|---|---|---|
| `{print $1 "\t" $2}` | 报错退出 2 | `INFO\tstart` |

同一类问题：本实现的 print 参数是「字段 / 变量 / 数字 / 字符串」四种**互斥**的种类，没有「表达式」这个概念。

### E 组：错误处理与退出码（4 处）

**第 11 处：中间的文件读不到**

| 命令 `awk-lite '{print $1}' app.log nope.log two.log` | 结果 |
|---|---|
| 本项目 | 打 app.log 和 two.log 的内容，跳过 nope.log，退出码 2 |
| GNU awk | **fatal**，打 app.log 的内容就停，two.log 根本不处理，退出码 2 |

GNU 把「打不开文件」当致命错误，本实现当成「跳过一个，继续」。这是有意取舍（README 里写了）。

**第 12 处：目录当文件用**

| 本项目 | GNU awk |
|---|---|
| 报错 `subdir: 是一个目录`，退出码 2 | 警告 `command line argument 'subdir' is a directory: skipped`，**退出码 0** |

**第 13 处：空程序**

| `awk-lite '' app.log` | 结果 |
|---|---|
| 本项目 | 报错「程序是空的」，退出码 2 |
| GNU awk | 空程序等于「没有规则」，什么都不打，退出码 0 |

**第 14 处：语法错误的退出码**

| 本项目 | GNU awk |
|---|---|
| 2 | 1 |

两边都失败，只是码不一样。本项目的约定是「0 成功 / 1 无结果 / 2 用法或运行错误」，本指令没有「无结果」这个状态。

### F 组：环境差异（2 处，README 已记录）

**第 15 处：换行符**。本实现输出走 Windows 文本模式，是 **CRLF**；GNU 输出 LF。82 组用例里有 63 组只差这个。管道出去比对字节时别把它当成内容差异。

**第 16 处：GBK 文件的输出**。本实现把 GBK 解码成 Unicode 再按 UTF-8 写出：

```
python ../../main.py awk-lite '{print $2}' gbk.log
```

```
开始
失败
```

GNU 是字节透传，打出来是原始 GBK 字节（终端上显示为 `¿ªÊ¼`）。

## 实测出的崩溃面：11 个输入

`_format_number` 第 445 行那句 `if number == int(number) and abs(number) < 1e16:`，在值是无穷大或 NaN 时会**先炸在 `int()` 上**：

```python
if number == int(number) and abs(number) < 1e16:
                 ^^^^^^^^^^
OverflowError: cannot convert float infinity to integer
```

而 `_to_number`（第 433~440 行）用的是 Python 的 `float()`，它接受 `inf`、`infinity`、`nan`、`1e400`。异常一路冒到 `main.py` 顶层，用户看到的是 Python 的 traceback，而不是本项目统一的 `错误: ...` 格式。

11 个触发输入（全部实测复现）：

| 输入 | 异常 |
|---|---|
| `-v x=inf` | OverflowError |
| `-v x=INF` | OverflowError |
| `-v x=Infinity` | OverflowError |
| `-v x=-inf` | OverflowError |
| `-v x=nan` | ValueError |
| `-v x=NaN` | ValueError |
| `-v x=1e400` | OverflowError |
| `-v n=inf '{print $n}'` | OverflowError |
| `-v n=nan '{print $n}'` | ValueError |
| `{print 1e400}` | OverflowError |
| `{print -inf}` | OverflowError |

GNU awk 对应的输入都不崩（`{print 1e400}` 打 `+inf`，`-v x=inf` 打 `inf`）。

顺带一个不对称：`{print inf}` 在本实现下**不崩**，因为 `_parse_item` 先判 `_IDENT.fullmatch(piece)`——`inf` 是个合法的标识符，被当成变量名，于是报「变量 'inf' 没有赋值」。而 `{print -inf}` 里 `-` 不是标识符字符，落到了 `_to_number` 分支 → 崩。

**修法方向**（属源码范围，本轮按只读原则没动）：`_to_number` 里把 `math.isfinite()` 判一下，无穷大与 NaN 不当数字（或明确报错）；`_format_number` 里也加一道同样的保险，免得别处再喂进来。

## 一个把探针带进沟里的坑：MSYS 改写 argv

差分对拍的第一版把程序直接放在 argv 里传给 GNU awk，报出一堆「GNU awk 不认 `{print}`」的**假差异**。真相是：**GNU awk 是 MSYS 程序，原生 Windows 程序 spawn 它时，MSYS 运行时会对未加引号的 argv 元素做花括号展开**。

`_t1302_probe_msys_braces.py` 让 awk 自己把收到的 argv 打出来，实测：

| 传给 awk 的字符串 | awk 实际收到的 |
|---|---|
| `{print}` | `print` |
| `{print$1}` | `print$1` |
| `a{b}c` | `abc` |
| `{a,b}` | `a`（另一个元素 `b` 另算一个 argv） |
| `{print $1}` | `{print $1}`（原样） |
| `{print($1, $2)}` | `{print($1, $2)}`（原样） |

规律：**带空格的参数被 Python 的 `subprocess` 加了引号，MSYS 的解析器就不动它；不带空格的裸参数被展开**。这跟 bash 的花括号展开一个道理——`echo {print}` 就是 `print`。

`MSYS_NO_PATHCONV=1` **挡不住**这个（它是管路径转换的，不是管花括号展开的）。

**绕法**：把程序写进文件，用 `awk -f prog.awk` 传，程序就不经过 argv。本轮的差分脚本就是这么改的。

**对本项目的影响**：本项目是原生 Windows 程序（`python.exe`），argv 不经 MSYS 运行时，`{print}` 原样到达——第 2 步的 `{print}` 能正常打整行就是这个原因。

**对用户的影响**：从 **cmd.exe** 里直接调 GNU awk，`awk "{print}" file` 会被 MSYS 运行时把花括号吃掉，awk 报语法错误；同一个命令在 Git Bash 里正常。从 Git Bash 调本项目的 `awk-lite` 不受影响。

## 常见疑问

**Q：`awk-lite` 和 `awk` 到底差在哪？一句话说清。**

`awk-lite` 是 GNU awk 的字段投影子集：能按分隔符切列、取列、正则筛行、打印内建变量。算术、拼接、`printf`、`BEGIN`/`END`、数组、函数一律报用法错误。

**Q：为什么没有把完整 awk 装进来？**

完整 awk 是一个语言，字段投影是一个工具。这个项目的定位是「Windows 上补齐常用命令」，不是「在 Windows 上实现 awk」。需要完整 awk 时，Git Bash 自带 GNU awk 5.3.2，直接用那个。

**Q：`{print $1, $2}` 里的空格是分隔符还是逗号决定的？**

两个都影响。逗号决定「分成几个参数」，OFS（默认一个空格）决定「参数之间用什么连」。`-v OFS=';'` 改的是后者。

**Q：为什么空行的 `NF` 是 0 而不是 1？**

默认分隔符按「空白串」切，空行里没有内容，所以切出 0 个字段。GNU awk 一样。

**Q：为什么 `-F';'` 要加引号？**

不加引号时 bash 把 `;` 当命令分隔符，后面的 `{print ...}` 就成了另一条命令。加引号（`-F';'` 或 `-F ";"`）是 bash 的语法要求，不是本项目的。

**Q：`$0` 和裸 `print` 有什么区别？**

没有区别，`{print}` 就是 `{print $0}`。

**Q：为什么读 GBK 文件输出的是 UTF-8？**

因为本实现把文件解码成 Unicode 再输出（编码靠「文本可信度打分」选），GNU 是字节透传。项目里 `cat`、`tail`、`grep` 都是这个口径，跨指令保持一致。

**Q：文件读不到时，本实现为什么还能继续处理后面的文件？**

GNU awk 把「打不开文件」当致命错误，直接停；本实现当成「跳过一个文件」，继续处理后面的，最后统一返回 2。这是项目一贯的取舍（`grep`、`sed` 也是这样）。

**Q：`{print foo}` 报「变量没有赋值」，但 GNU awk 能打空行，为什么本实现这么严？**

因为在字段投影这个场景里，「变量没赋值」几乎总是写错了而不是想打印空串。GNU 的宽容会让笔误静默通过——这正是本实现要避免的。

## 相关教程

- `teach/27-w2l-commands-sed.py-地址语义与正则翻译.md` — 同属「按行处理」这一类，正则方言与地址语义在那篇；本篇的 `-v` 变量、`-F` 分隔符与它互补
- `teach/21-w2l-commands-cat.py-编码判定与显示记号.md` — 编码打分那套思路的出处（`_detect_encoding` 与它同源）
- `teach/07-w2l-commands-grep.py-检索实现.md` — 同一套「先筛行再取内容」的思路里，`grep` 负责筛，本篇负责取列
- `teach/22-w2l-commands-wc.py-列宽模型与词数判定.md` — 同样是「口径先定好再实现」的指令，可以对照看
- `teach/13-新增一个指令的完整过程.md` — 新指令怎么加（`build_parser` + `@command` + 测试）
- `teach/17-AGENTS.md-项目守则.md` — 退出码约定（0 成功 / 1 无结果 / 2 用法或运行错误）的出处
