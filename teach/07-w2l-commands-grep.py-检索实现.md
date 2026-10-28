# w2l/commands/grep.py — 检索实现

`w2l/commands/grep.py` 是目前唯一一个指令实现，299 行，实现了 GNU grep 的一个子集：`-i -v -n -r -E -w -c -l -o` 九个选项，退出码 0 命中 / 1 未命中 / 2 出错。

## 为什么这么创建

**为什么默认用 BRE 而不是 Python 原生正则。** GNU grep 默认是基本正则（BRE）：`+ ? | ( ) { }` 都是字面量，要当元字符用必须反斜杠转义（`\+ \| \( \)`）。Python 的 `re` 默认是「扩展正则」语义：`+ ? | ( )` 直接就是元字符。

如果直接用 `re` 的默认行为，用户从 Linux 迁过来的第一件事就会踩坑：写 `grep 'ERROR\|FATAL'` 匹配不到，写 `grep 'E[a-z]+'` 又匹配得到——同一套肌肉记忆在两个工具里结果相反。项目选择对齐 GNU，所以自己写了一个翻译器 `_translate_bre`，把 BRE 模式翻译成 Python 能编译的正则。

代价是多了一个翻译层，也就多了一批边界情况：`\|` 要还原成 `|`、`\(` 要变成非捕获组、`(` 要变成字面量 `(`。而且 Python 不支持 POSIX 字符类 `[[:alpha:]]`，BRE 的区间 `{m,n}` 也不支持。这些是已知缺口。

**为什么不用 chardet 之类做编码判定。** 项目硬约束是零第三方依赖（`AGENTS.md` 第 3 节）。所以自己实现了一个基于「试解码」的判定：拿文件开头 8192 字节，依次尝试候选编码，第一个能严格解码的就是它。

代价是判定只看前 8 KB，且候选顺序是固定的启发式顺序（详见下文）。

**为什么二进制文件不输出内容。** Windows 上误 grep 一个 exe 或 pyc，乱码会冲满终端。代码检测到文件前 8192 字节里有 `\x00` 就走 `_search_binary()`，只输出一行 `Binary file xxx matches`，不做逐行内容输出。

**为什么用流式处理。** 逐行读、逐行判断、逐行输出，不在内存里攒结果。所以搜一个大目录不会把内存撑爆，输出也能边搜边看。

## 这个文件是做什么

对外只有两个名字：

| 名字 | 作用 |
|---|---|
| `build_parser()` | 返回 `argparse.ArgumentParser`，定义 9 个选项 |
| `grep(args, ctx)` | 处理函数，返回退出码 |

`grep()` 的主流程（`grep.py:65` 起）：

1. `_compile_regex(args)` 编译模式；`UsageError` 在这里抛。
2. 判断是不是 stdin 模式（没给 `paths`）。stdin 模式且 stdin 是终端 → `UsageError`。
3. 算出 `show_prefix`：递归搜索或给了多个文件时，输出行要带文件名前缀。
4. 遍历文件，逐个 `_search_file()`；`OSError`（文件不存在等）写 stderr 并置 `had_error`。
5. 返回值：`had_error` → 2；有命中 → 0；否则 → 1。

内部函数分工：

| 函数 | 职责 |
|---|---|
| `_compile_regex` | 决定用 BRE 还是 ERE，套 `-w` 的词边界，编译 |
| `_translate_bre` | BRE → Python 正则的翻译器 |
| `_iter_files` / `_walk` | 把路径列表展开成文件列表（递归时按目录名、文件名排序） |
| `_search_stdin` | 从 `ctx.stdin` 读并搜索 |
| `_search_file` | 打开文件、嗅探编码/二进制、逐行搜索 |
| `_search_binary` | 二进制文件的匹配计数 |
| `_run_search` | 核心循环：逐行判断、决定输出什么 |
| `_line_prefix` | 拼 `文件:行号:` 前缀 |
| `_matched_pieces` | `-o` 时取出匹配片段（`-v` 时取的是「不匹配的部分」） |
| `_summary_mode` | 判断是否处于 `-c` / `-l` 这种汇总模式 |
| `_decode_lines` | 按判定出的编码逐行解码，去掉行尾 `\n` / `\r` |
| `_detect_encoding` / `_decodes` | 编码嗅探 |

常量：

```python
_SNIFF_SIZE = 8192
_FALLBACK_ENCODINGS = ("utf-8", "gb18030", "latin-1")
_BRE_LITERALS = "+?|(){}"
```

不负责：指令注册（在 `w2l/registry.py`）、分发（在 `w2l/cli.py`）、输出编码（统一在 `w2l/cli.py` 处理）。

## 有什么用

- 在 Windows 上按 GNU grep 的习惯搜索代码库、日志、配置，选项名和退出码都能直接套用现成的 shell 脚本。
- 退出码 0/1/2 可以直接驱动判断：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -q "TODO" . ; echo "退出码=$?"
```

（注意 `-q` 目前没实现，上面的写法会报「unrecognized arguments」，实际可用的是下面这种：）

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep "TODO" . > /dev/null; echo "退出码=$?"
```

- 编码自动判定让搜 GBK 保存的老日志、GBK 保存的 Python 源码不用先转码。
- `-l` 列出含匹配的文件名，可以接到别的工具上做批量处理。

## 怎么用（过程教程）

### 第 1 步：基本用法与退出码

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep "def " w2l/commands/grep.py | head -3; echo "退出码=${PIPESTATUS[0]}"
```

预期：

```
37:def build_parser() -> argparse.ArgumentParser:
65:def grep(args: argparse.Namespace, ctx: RunContext) -> int:
97:def _compile_regex(args: argparse.Namespace) -> re.Pattern:
退出码=0
```

无命中时退出码是 1：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep "绝对不存在的字符串" README.md; echo "退出码=$?"
```

预期：无输出，`退出码=1`。

### 第 2 步：BRE 与 ERE 的差别（最容易踩的坑）

同一个文件，两个模式：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -c "a|b" w2l/registry.py; echo "退出码=$?"
```

预期输出：

```
0
退出码=1
```

BRE 里 `|` 是字面量，所以匹配不到。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -cE "a|b" w2l/registry.py; echo "退出码=$?"
```

预期输出：

```
26
退出码=0
```

`-E` 之后 `|` 才是「或」。

BRE 里想用「或」，必须转义：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -c "a\|b" w2l/registry.py
```

预期：`26`（与 `-E` 结果相同）。

同理，`+` 在 BRE 里是字面量，`\+` 才是「一个或多个」：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -c "E[a-z]+" w2l/commands/grep.py; echo "退出码=$?"
python main.py grep -c "E[a-z]\+" w2l/commands/grep.py
```

第一条预期 `0`（`+` 是字面量，匹配不到）；第二条预期 `6`（匹配到 `ERROR`、`E` 开头的标识符等 6 处）。

对照表：

| 你想写 | BRE（默认） | ERE（`-E`） |
|---|---|---|
| 或 | `\|` | `\|` |
| 一个或多个 | `\+` | `+` |
| 零个或一个 | `\?` | `?` |
| 分组 | `\(...\)` | `(...)` |
| 重复次数 | `\{2\}` | `{2}` |

BRE 里转义形式在 ERE 里也认（`\|` 在 ERE 里同样表示「或」），所以 `-E` 模式下写 `\|` 不会出错。

### 第 3 步：`-w` 词边界

`-w` 的实现是把模式包成 `(?<!\w)(?:模式)(?!\w)`，用 Python 的零宽断言实现「前后不是单词字符」。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -n -w "def" w2l/commands/grep.py | head -3
```

预期：

```
37:def build_parser() -> argparse.ArgumentParser:
65:def grep(args: argparse.Namespace, ctx: RunContext) -> int:
97:def _compile_regex(args: argparse.Namespace) -> re.Pattern:
```

对照不加 `-w` 的情况（用 `w2l/cli.py` 看最直观）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -c "def" w2l/cli.py
python main.py grep -c -w "def" w2l/cli.py
```

预期输出：

```
6
5
```

差的那 1 行是第 18 行：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -n "def" w2l/cli.py
```

预期：

```
14:def _print_help() -> None:
18:    width = max((len(name) for name in REGISTRY), default=4)
25:def _configure_streams() -> None:
45:def _set_console_utf8() -> None:
56:def _silence_broken_pipe() -> None:
61:def main(argv: list[str] | None = None) -> int:
```

第 18 行的 `default=4` 里含有 `def`，不加 `-w` 会被算进去，加了 `-w` 就被排除。

注意 `(?<!\w)` 用的是 `\w`，即 `[a-zA-Z0-9_]` 加 Unicode 字母数字。对中文来说，中文字符属于 `\w`，所以 `-w` 对中文词边界也是生效的。

### 第 4 步：`-o` 只输出匹配片段

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -oE "def [_a-z]+" w2l/commands/grep.py | head -5
```

预期：

```
def build_parser
def grep
def _compile_regex
def _translate_bre
def _iter_files
```

配合 `-n`：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -on "ERROR" README.md
```

预期：

```
20:ERROR
```

（`-o` 只输出匹配到的片段，`-n` 给出行号。）

`-o` 的已知限制（`AI/阅读进度.md` 第 3 节记录了这条）：**多文件模式下 `-o` 不带文件名前缀**。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -oE "def [a-z_]+" w2l/cli.py w2l/errors.py | head -4
```

预期输出（没有 `w2l\cli.py:` 这样的前缀）：

```
def _print_help
def _configure_streams
def _set_console_utf
def _silence_broken_pipe
```

GNU grep 在多文件时也会给 `-o` 加前缀，这里保持与 GNU 一致，暂不改。

### 第 5 步：`-c` 计数

单文件时只输出数字：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -c "def" w2l/cli.py
```

预期：

```
6
```

多文件时输出 `文件:数量`，**没有命中的文件也会输出 0**：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -c "def" w2l/cli.py w2l/errors.py
```

预期：

```
w2l\cli.py:6
w2l\errors.py:0
```

这与 GNU grep 一致：`-c` 是「每个文件都报一行」，不是「只报有命中的文件」。

### 第 6 步：`-l` 只列文件名

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -l "def" w2l/cli.py w2l/errors.py
```

预期：

```
w2l\cli.py
```

`w2l/errors.py` 没有 `def`，所以不出现。这一点与 `-c` 不同：`-c` 会给 0，`-l` 不给。

`-c` 和 `-l` 同时属于 `_summary_mode()`，此时 `_run_search` 的 `emit_lines` 为 `False`，逐行内容不再输出，只在最后汇总。

### 第 7 步：`-v` 反向匹配

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -v "^#" README.md | head -3
```

预期（输出所有不以 `#` 开头的行，注意第一行是空行——README 标题下面本来就有空行）：

```

在 Windows 上用 Python 复刻常用 Linux 命令行能力，统一入口：
```

`-v` 和 `-o` 一起用时，输出的是**不匹配的部分**（`_matched_pieces` 的 invert 分支）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -v -o -E "ERROR|warn" w2l/commands/grep.py | head -3
```

预期：输出的是每行里没被 `ERROR|warn` 命中的片段，比如文档字符串那几行。

### 第 8 步：编码自动判定

判定逻辑在 `_detect_encoding()`：取文件前 8192 字节，逐个候选编码严格解码样本，按解码结果的**文本可信度**打分，后选的编码可信度明显更高时才替换当前选择。

候选顺序：

1. `utf-8`
2. `locale.getpreferredencoding(False)`（中文 Windows 上是 `cp936`，英文 Windows 上是 `cp1252`）
3. `gb18030`
4. `latin-1`

打分规则在 `_text_score()`：ASCII 可打印字符记 1 分，CJK 字符记 3 分，中文标点与全角记 1 分，换行等空白记 0.5 分，其它非 ASCII 字符记 0.2 分，最后除以字符总数。后选的编码要高出当前最优 0.3 分以上才会被选中。

不能「按顺序取第一个能解码的」：英文 Windows 的系统编码是 `cp1252`，它几乎不报错，能把 GBK 字节解成 Latin 乱码。按顺序取的结果是 GBK 文件里的中文永远搜不到，退出码 1 且没有任何输出。这个问题在中文 Windows 上看不出来（系统编码 `cp936` 正好能解 GBK），英文 Windows 与 Linux 的 CI runner 上必现。

自己验证 GBK 文件能被搜出中文：

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q tests/test_grep.py::test_gbk_encoding
python -m pytest -q tests/test_grep.py::test_gbk_encoding_on_non_chinese_locale
```

预期：两条都 passed。第二条用 `monkeypatch` 把 `locale.getpreferredencoding` 换成 `cp1252`，模拟英文 Windows 环境。

两个已知局限：

- **只看前 8 KB**。前 8 KB 是 ASCII、第 8 KB 之后才是 GBK 的文件，会被判定成 `utf-8`，后半段中文变成乱码（`errors="replace"`）。
- **打分不是编码检测的银弹**。没有 BOM、没有声明时，编码本身就不可判定。一个真正的 Latin-1/Western 编码文件，如果字节恰好能凑成合法 GB18030 双字节，会被判成 GB18030 并显示成中文。

### 第 9 步：二进制文件

判定方式很简单：前 8192 字节里出现 `\x00` 就当二进制。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep "grep" .git/index; echo "退出码=$?"
```

预期：

```
Binary file .git\index matches
退出码=0
```

`-l` 对二进制同样只列文件名：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep -l "grep" .git/index
```

预期：

```
.git\index
```

二进制文件**不输出行内容**，也不支持 `-n` / `-o`（代码里 `_search_binary` 只做计数和三种汇总输出）。

### 第 10 步：不给路径时的两种行为

不给文件路径时，行为取决于标准输入是不是管道：

- **终端里直接敲**（stdin 是 tty）：默认递归搜索当前目录，等价于 `grep -r PATTERN .`，输出带文件名前缀。
- **管道输入**（stdin 不是 tty）：按 GNU 语义从标准输入读。

管道读法：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'ok\nwarn here\n' | python main.py grep warn; echo "退出码=$?"
```

预期：

```
warn here
退出码=0
```

`-c` 在 stdin 模式下输出总数：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'ok\nwarn here\n' | python main.py grep -c warn
```

预期：

```
1
```

终端里的默认行为：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py grep "def grep"; echo "退出码=$?"
```

预期：stderr 一行提示，stdout 是搜索结果。

```
未指定路径：递归搜索当前目录（.）。要读标准输入请用管道。
```

实现是 `grep()` 里的这几行：

```python
paths = list(args.paths)
recursive = args.recursive
stdin_mode = not paths

if stdin_mode:
    if ctx.stdin is None:
        raise UsageError("没有指定文件，也没有可读取的标准输入")
    if ctx.stdin.isatty():
        paths = ["."]
        recursive = True
        stdin_mode = False
        ctx.stderr.write("未指定路径：递归搜索当前目录（.）。要读标准输入请用管道。\n")
```

这是本项目有意偏离 GNU 的一处。GNU grep 不给路径时永远读 stdin，在终端里敲 `grep "id"` 会等你输入到 Ctrl+D。本项目在终端下改成直接搜当前目录，少敲一个 `.`；管道场景保持 GNU 行为不变。

验证：

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q tests/test_grep.py::test_no_path_in_terminal_searches_current_directory
```

预期：通过。用例里用 `monkeypatch.chdir(tmp_path)` 把工作目录换到临时目录，不会扫到真实仓库。

### 第 11 步：常见坑清单

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `grep 'a\|b'` 匹配不到 | 默认 BRE，`\|` 才对；但如果用了单引号里的 `\|`，说明模式写成了 `a\|b`（正确）却仍匹配不到，检查是否误写成 `a|b` | 加 `-E` |
| `grep 'a|b'` 匹配不到 | BRE 里 `\|` 是字面量 | 加 `-E`，或写 `a\|b` |
| `grep 'E[a-z]+'` 匹配不到 | BRE 里 `+` 是字面量 | 加 `-E`，或写 `E[a-z]\+` |
| 模式以 `\` 结尾直接报错 | `_translate_bre` 抛 `re.error`，被转成 `UsageError` | 转义反斜杠 |
| 多文件 `-c` 出现 `0` 的行 | `-c` 是「每个文件一行」，不是「只报命中的」 | 用 `-l` 只要有命中的文件 |
| `-o` 多文件没有文件名前缀 | 已知限制，与 GNU 行为一致 | 接受，或给每个文件单独跑 |
| 目录不加 `-r` 报错 | 目录必须配 `-r` | 加 `-r` |
| 中文输出乱码 | 文件编码不在候选列表里，或判定只看前 8 KB | 先转成 UTF-8 再搜 |

### 第 12 步：跑全部测试确认没改坏

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q
```

预期：`36 passed`。其中 `tests/test_grep.py` 覆盖了上面说的每一类行为：BRE/ERE 差异（`test_basic_regexp_treats_pipe_as_literal`、`test_basic_regexp_escaped_alternation`）、`-w`（`test_word_regexp`）、`-c`（`test_count`、`test_count_multiple_files_prefixed`）、`-l`（`test_files_with_matches`）、`-o`（`test_only_matching`、`test_only_matching_with_line_number`）、二进制（`test_binary_file_message`、`test_binary_file_listed_with_l`）、编码（`test_gbk_encoding`、`test_crlf_line_endings`）、退出码（`test_no_match_returns_one`、`test_missing_file_reports_error`）。
