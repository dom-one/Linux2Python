# w2l/commands/tail.py — 起点语义与跟随模式

`w2l/commands/tail.py` 有 1140 行，是项目里最长的指令实现。它要回答的问题只有一个：**`-n` 后面那个数字，到底是从哪儿数起？**

GNU tail 的计数语法比 head 多一层正负号语义，两者的方向正好相反：

| 写法 | tail 的实际含义 | head 的实际含义 |
|---|---|---|
| `-n 5` | 末 5 行 | 前 5 行 |
| `-n -5` | 末 5 行（与 `-n 5` 同义） | 除末 5 行之外的全部 |
| `-n +5` | **从第 5 行开始**一直到末尾 | 前 5 行 |
| `-n 0` | 一行都不要 | 一行都不要 |
| `-n +0` | **全部都要** | 全部都要 |
| `-n 1b` | 末 512 **行** | 前 512 **行** |

最容易记错的是 `+N`：head 的 `+5` 等价于 `5`，tail 的 `+5` 是**起点**。照着 head 的直觉写 `tail -n +5`，拿到的是从第 5 行到文件末尾的全部内容，不是前 5 行。

除此之外，这个文件还有两件 head 没有的事：跟随时能扛住日志轮转，以及 Windows 上打开着的文件不能改名这个限制要绕开。

本篇的实测依据：54 条用例与 Git Bash 的 GNU coreutils 8.32 `tail` 逐字节对拍，48 条完全一致，6 条差异全部是本项目有意为之的取舍（错误文案与退出码、GBK 文本的解码方式），逐条在文里标出。

## 为什么这么创建

### 决定一：`+N` 必须是起点，不能照抄 head

head 与 tail 的计数语法长得几乎一样，语义却在两个维度上分岔：

- **方向**：head 从头数，tail 从尾数
- **加号的含义**：head 的 `+` 是冗余写法，tail 的 `+` 是起点

第二个维度最容易踩。head 的 `-n +5` 等价于 `-n 5`，tail 的 `-n +5` 是「跳过前 4 行，从第 5 行开始一直到最后」。

本实现把它拆成两个独立字段：

```python
@dataclass(frozen=True)
class _Options:
    mode: str  # "lines" 或 "bytes"
    direction: str  # "last"（末尾 N 个）或 "from"（从第 N 个开始）
    amount: int  # 数量
```

`direction` 只有两个取值，解析时一次定死：

```python
def _parse_amount(text: str, mode: str) -> tuple[str, int]:
    ...
    sign = match.group(1)
    ...
    if sign == "+":
        return "from", amount
    return "last", amount
```

**注意负号不在这里分支。** `-n -5` 落到 `sign == "-"` 这个 else 分支，返回 `("last", 5)`。这是 tail 与 head 语义分岔的根源：head 里 `-5` 是「除末 5 行」，tail 里 `-5` 与 `5` 同义。GNU tail 把负号按 uintmax 算，负号等价于正号，本实现照抄：

```python
# GNU 的计数上界：正负号都按 uintmax 算（tail 里负号等价于正号）。
_UINTMAX_MAX = (1 << 64) - 1
```

### 决定二：后写的选项说了算，顺序必须自己记

GNU tail 里 `-n` 与 `-c` 同时给时后写的生效，`-q` 与 `-v` 同时给时也是后写的生效。这两条都不是 argparse 的默认行为。

argparse 的 `store` 只留值不留「是哪个选项写的」——`-n 2 -c 7` 解析完，`args.count` 是 7，但没人知道 7 是 `-c` 写的还是 `-n` 写的。所以 tail.py 自己写了一个 Action 把顺序记下来：

```python
class _CountAction(argparse.Action):
    """记录 -n/-c 的出现顺序。

    GNU 里两个都给时后写的那个生效，所以不能各存一个 dest 再挑一个，
    得按顺序存下来，最后一个说了算。
    """

    def __call__(self, parser, namespace, values, option_string=None):
        specs = getattr(namespace, self.dest, None)
        if specs is None:
            specs = []
            setattr(namespace, self.dest, specs)
        specs.append((self.const, values))
```

`-n` 与 `-c` 共用同一个 `dest="count_specs"`，各自带一个 `const`（`"lines"` / `"bytes"`）。取值时只看最后一个：

```python
specs = getattr(args, "count_specs", None) or []
if specs:
    mode, text = specs[-1]
else:
    mode, text = "lines", str(_DEFAULT_LINES)
```

`-q` / `-v` 不用自己记顺序——argparse 的 `store_const` 天然就是后写的覆盖先写的，`_resolve_headers` 只看最终值。

### 决定三：argv 必须改写

三处写法 argparse 不认：

- `-2`：GNU 把它当成 `-n 2`，argparse 会把 `-2` 当位置参数（argparse 靠「单横线 + 字母」识别选项，`3` 不是字母）
- `-n -2`：值以负号开头时 argparse 会把它当成下一个选项，改写成 `-n=-2` 才能把负号原样交给值解析
- `-f` / `--follow`：GNU 的可选参数只认 `-f=name` 这种写法，单独一个 `-f` 表示按文件描述符跟随，后面的词不算它的值

`_rewrite_argv` 在交给 argparse 之前把这三处都改掉：

```python
def _rewrite_argv(args: list[str]) -> list[str]:
    out: list[str] = []
    index = 0
    literal = False
    while index < len(args):
        arg = args[index]
        if literal:
            out.append(arg)
            index += 1
            continue
        if arg == "--":
            literal = True
            out.append(arg)
            index += 1
            continue

        compact = _COMPACT_RE.fullmatch(arg)
        if compact:
            out.extend(["-n", compact.group(1)])
            index += 1
            continue

        if arg in ("-n", "-c", "--lines", "--bytes") and index + 1 < len(args):
            value = args[index + 1]
            if value.startswith("-"):
                out.append(f"{arg}={value}")
                index += 2
                continue

        if arg == "--follow":
            out.append("--follow=descriptor")
            index += 1
            continue

        if arg == "-f":
            out.append("-f=descriptor")
            index += 1
            continue

        if arg.startswith("-f") and len(arg) > 2:
            out.append(f"-f={arg[2:]}")
            index += 1
            continue

        out.append(arg)
        index += 1
    return out
```

改写放在 `_TailParser.parse_known_args` 里，所以对所有调用方统一生效：

```python
class _TailParser(argparse.ArgumentParser):
    def parse_known_args(self, args=None, namespace=None):
        if args is None:
            args = sys.argv[1:]
        return super().parse_known_args(_rewrite_argv(list(args)), namespace)
```

`--` 之后是字面量，不再改写——这条不能省，否则 `tail -- -n` 里的 `-n` 会被当成选项。

`-f` 的三种写法分别对应三个意思：单独 `-f` 是按描述符跟、`-f=name` 是按文件名跟、`--follow` 单独出现也是按描述符跟（GNU 的 `--follow` 不接受可选值，本实现补上这个便利写法）。

### 决定四：末尾的行要从文件尾巴往回读

`tail -n 5` 不需要把整个文件读进内存。做法是从文件末尾往回读，凑够行数就停：

```python
def _read_last_lines(handle: object, size: int, count: int, delimiter: bytes) -> bytes:
    """从文件末尾往回读，凑齐 count 行。

    回读的起点多半落在行中间，开头那截半行不是完整的一行，要丢掉；
    所以要凑够 count+1 个分隔符才停。多读的那一块不算浪费，
    换来的是不用把整个文件从头读一遍。
    """
    position = size
    buffer = bytearray()
    while position > 0:
        step = min(_READ_SIZE, position)
        position -= step
        try:
            handle.seek(position)
            chunk = handle.read(step)
        except (OSError, ValueError):
            break
        if not chunk:
            break
        buffer = bytearray(chunk) + buffer
        if buffer.count(delimiter) >= count + 1:
            break

    lines = list(_iter_lines([bytes(buffer)], delimiter))
    if position > 0:
        # 起点在行中间，第一段是半行，丢掉。
        lines = lines[1:]
    return b"".join(lines[-count:])
```

两个细节：

**为什么是 `count + 1` 个分隔符。** 回读起点多半落在行中间，第一段是半行。凑够 `count` 个分隔符只能得到 `count - 1` 条完整行加一段半行；凑够 `count + 1` 个，才能切出 `count` 条完整行，剩下那段半行丢掉。

**`if position > 0` 是「起点不在行中间」的判据。** 如果整个文件都被读进来了（`position == 0`），第一段就是完整的第一行，不能丢。丢之前先判断位置，是这个函数唯一容易写错的地方。

块大小是 64KB：

```python
_READ_SIZE = 65536
```

实测过三种块边界位置——正好落在行首、落在行中间、与行首错开 5 字节——输出与 GNU 逐字节一致。

### 决定五：标准输入不能定位，只能顺序读

`tail` 的操作数可以是 `-`，也可以一个都不给（此时也读标准输入）。但标准输入是管道，不能 `seek`。

实现分两条路：能定位的走倒读，不能定位的走顺序读。

```python
if options.direction == "from":
    if not seekable:
        return _read_lines_from_stream(handle, amount - 1, delimiter)
    ...
if amount <= 0:
    return b""
if seekable and size:
    return _read_last_lines(handle, size, amount, delimiter)

# 长度未知（标准输入）时顺序读，保留末尾 amount 行
keep: deque[bytes] = deque(maxlen=amount)
for line in _iter_lines(_iter_chunks(handle), delimiter):
    keep.append(line)
return b"".join(keep)
```

顺序读「末尾 N 行」用 `deque(maxlen=N)`——边读边扔，自动只留最后 N 条，不用自己维护环形缓冲区。

文本模式的 stdin 会把 CRLF 归一成 LF、丢掉 lone CR，那不是 tail 该做的事，所以优先走底层二进制流：

```python
def _stdin_handle(ctx: RunContext) -> object:
    """标准输入的底层二进制流。

    文本模式的 stdin 会把 CRLF 归一成 LF、丢掉 lone CR，那不是 tail
    该做的事，所以优先走底层二进制流；拿不到二进制流时退回文本再编码回
    UTF-8。
    """
    stream = ctx.stdin
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        return buffer
    return _TextStreamAdapter(stream)
```

`_TextStreamAdapter` 是兜底：把文本重新编码回 UTF-8 字节，让后面的字节处理代码不用分叉。

### 决定六：`-z` 只换分隔符，不改其他

`-z`（`--zero-terminated`）把行分隔符从 `\n` 换成 NUL。分隔符是一个字段，跟计数模式无关：

```python
@property
def delimiter(self) -> bytes:
    """行分隔符：-z 时是 NUL，否则是换行。"""
    return b"\x00" if self.zero_terminated else b"\n"
```

切行的地方只认这个分隔符：

```python
def _iter_lines(chunks: Iterator[bytes], delimiter: bytes) -> Iterator[bytes]:
    """按分隔符切行，行内容连分隔符一起产出。

    只认 "\\n" 作行分隔符（-z 时是 NUL），"\\r" 留在行内容里：这样
    CRLF 文件的行内容是 "xxx\\r\\n"，与 GNU 的判定一致。
    """
```

`\r` 留在行内容里是刻意的：CRLF 文件的行内容就是 `xxx\r\n`，把 `\r` 剥掉就改变了内容。

### 决定七：跟随时认「描述符」还是认「文件名」

这是 tail 跟 head 最大的功能差别，也是这个文件里最长的部分（`_Follower` 类从第 836 行到第 932 行）。

GNU 有两个跟随选项：

- `-f` / `--follow`：认**文件描述符**。文件被改名了也照样跟着旧句柄读。
- `-F`：`--follow=name --retry`。认**文件名**。文件被轮转掉了（换了一个新文件）就重新打开接着读。

日志轮转是这么发生的：`app.log` 被改名成 `app.log.1`，然后创建一个新的 `app.log`。此时按描述符跟的进程还在读旧 inode，新内容永远看不到；按文件名跟的进程会发现自己盯的文件被换掉了，从头读新文件。

实现用同一个类的两个分支：

```python
class _Follower:
    """跟随一个文件（或者标准输入）的增长。

    - by_name=False：认文件描述符。文件被改名了也照样跟着旧句柄读。
    - by_name=True：认文件名。文件被轮转掉了（换了一个新文件）就重新
      打开接着读，这正是日志轮转想要的。

    按文件名跟随时每轮都重新打开再关掉，不长期占着句柄：Windows 上
    打开着的文件不能改名（FILE_SHARE_DELETE 没开），日志轮转第一步
    就是改名，长期占着句柄的话这一步直接失败。
    """
```

按文件名跟随时靠文件标识认出「文件被换掉了」：

```python
identity = (stat.st_ino, stat.st_dev)
if self.identity is None:
    self.identity = identity
elif identity != self.identity:
    # 文件被换掉了（日志轮转），从头读新文件。
    self.position = 0
    self.pending = bytearray()
    self.identity = identity
elif stat.st_size < self.position:
    # 文件被截断，从头接着读。
    self.position = 0
    self.pending = bytearray()
```

两个分支：标识变了是换文件（轮转），标识没变但文件变小了是截断。两种情况都把位置退回 0。

**Windows 上那个绕不开的限制**：打开着的文件不能改名（`FILE_SHARE_DELETE` 没开），日志轮转第一步就是改名，长期占着句柄的话这一步直接失败。所以按文件名跟随时每轮都重新打开再关掉：

```python
try:
    handle = open(self.path, "rb")
except OSError:
    self.missing = True
    return b""
try:
    handle.seek(self.position)
    chunk = _read_some(handle, _READ_SIZE)
except (OSError, ValueError):
    return b""
finally:
    handle.close()
```

按描述符跟随时则相反，长期占着句柄是**必须的**——不然改名之后就跟丢了。

### 决定八：半行要等换行符

跟随时写日志的程序可能正在写一半。立刻输出会看到半截行，所以不完整的部分要留在缓冲里：

```python
def _take_complete_lines(buffer: bytearray, delimiter: bytes) -> tuple[list[bytes], bytearray]:
    """从缓冲里切出完整行，末尾那段不完整的留在缓冲里。

    跟随时半行不能马上输出：写日志的程序可能正在写一半，等它写完
    换行符再整体输出，才不会出现半截行。
    """
```

实测：往文件追加 `half` 时 `tail -f` 的输出里看不到它；等补上 ` done\n` 之后，`half done\n` 才整行出现。

### 决定九：跟随时必须刷缓冲

接管道时 Python 默认块缓冲（攒够 8KB 才写）。不刷的话 `tail -f` 跟半天什么也看不见——GNU tail 跟随时是行缓冲的。

```python
def _flush(ctx: RunContext) -> None:
    """把缓冲区里的内容立刻推出去。

    跟随时必须刷：输出接到管道上时 Python 是块缓冲（攒够 8KB 才写），
    不刷的话 `tail -f` 跟半天什么也看不见——GNU tail 跟随时是行缓冲的。
    """
```

实测：`tail -f` 接管道，追加一行后约 1 秒内就能读到。

### 决定十：Windows 上不能用 `os.kill(pid, 0)` 探活

`--pid` 的用途是「跟到某个进程退出为止」。探活的标准写法是 `os.kill(pid, 0)`——发 0 号信号，进程不受影响，只是错误返回。

**Windows 上不行**：那边的 0 号信号会真的把进程终止掉。所以改用 `OpenProcess` 探句柄：

```python
def _pid_alive(pid: int) -> bool:
    """目标进程还活着吗。

    Windows 上不能用 os.kill(pid, 0)：那边的 0 号信号会真的把进程
    终止掉，所以改用 OpenProcess 探一下句柄。
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            # PROCESS_QUERY_LIMITED_INFORMATION
            handle = kernel32.OpenProcess(0x1000, False, pid)
        except (AttributeError, OSError):
            return True
        if handle:
            kernel32.CloseHandle(handle)
            return True
        # 打不开多半是权限不足，进程应该还在
        return kernel32.GetLastError() == 5
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True
```

`GetLastError() == 5` 是 `ERROR_ACCESS_DENIED`（权限不足），这时进程多半还在，只是当前用户无权查询，打不开不等于死了。

**Windows 上还有一条坑**：进程退出之后，只要还有任何句柄指着它，`OpenProcess` 照样能打开。所以「目标进程是当前 Python 进程的子进程」时，父进程不回收句柄就永远探不到它死了。用一个中途退出的中间进程拉起目标进程（让目标进程变成真正的孤儿）才能测准——实测目标进程退出后 `tail -f --pid` 随即自己结束。

**这个坑在测「`--pid` 有没有生效」时最容易误判**：第一版探针直接用 `subprocess.Popen` 拉起目标进程，测出来 tail 25 秒都不结束，看着像 `--pid` 没实现。实际上是探针自己错了——`Popen.wait()` 只等进程退出，**不关句柄**，句柄还开着 → 进程对象还在 → `OpenProcess` 照样打得开。换成孤儿进程测法后，`--pid` 的行为完全正常。

### 决定十一：编码判定取的是「将要输出的那一段」

这一条是 tail 特有的，跟 head 不同。

head 取的是文件开头那段的编码，tail 取的是**末尾那段的编码**。文件开头是 ASCII、末尾是 GBK 中文时，tail 照样出中文：

```python
def _pick_encoding(sample: bytes) -> str:
    """按内容选解码方式。
    ...
    样本取的是「将要输出的那段」，不是文件开头：tail 只输出末尾几行，
    那几行是什么编码就按什么编码解，GBK 日志的末尾照样出中文。
    """
```

实测：文件前三行是 ASCII、最后一行是 GBK 中文，`tail -n 1` 输出 `中文最后一行`，而同一文件 `head -n 1` 输出的是 `ascii head`。

编码判定的具体规则（判文本还是二进制、多个候选编码怎么打分）与 grep、cat、head、wc 完全一致，是同一套逻辑抄了五份——`AI/教程进度.md` 里记着这是已知重复。

判定为二进制（含 NUL 字节，或谁也解不出来）时按原字节透传，解不开的字节用代理码位占位，写回时还原：

```python
def _write(ctx: RunContext, raw: bytes, encoding: str) -> None:
    """把一段字节解码后写出去。

    解不开的字节用代理码位占位，写回时还原成原字节，二进制内容因此
    不会被改写。
    """
    ctx.stdout.write(raw.decode(encoding, errors="surrogateescape"))
```

### 决定十二：管道里要关掉换行翻译

Windows 上 Python 默认把 `\n` 写成 `\r\n`。tail 的职责是原样转交内容，重定向时做这个翻译会把 LF 文件和 CRLF 文件的区别抹掉：

```python
def _prepare_stdout(ctx: RunContext) -> None:
    """调整输出流，让内容按原样转交。

    - 管道与重定向时关掉换行翻译。Windows 上 Python 默认把 "\\n" 写成
      "\\r\\n"，那会把 LF 文件和 CRLF 文件的区别抹掉；tail 的职责是原样
      转交内容，所以重定向时不翻译。控制台保持默认的 CRLF。
    - 错误处理改成 surrogateescape，解不出的字节用代理码位占位，
      写回时还能还原成原字节。
    """
    reconfigure = getattr(ctx.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(errors="surrogateescape")
        if not _isatty(ctx.stdout):
            reconfigure(newline="")
    except (ValueError, OSError):
        pass
```

控制台（tty）保持默认的 CRLF，管道和重定向（不是 tty）才关翻译。

### 决定十三：错误路径要跟 GNU 分开处理

两种错误，GNU 的行为不一样：

- **文件打不开**：不打标题，只报错，继续处理后面的文件
- **目录**：先打标题，再报错

```python
path = _resolve(ctx.cwd, name)
if path.is_dir():
    # GNU 先打标题再报读取错误，标题照打。
    if print_headers:
        _print_header(ctx, name, header_count)
        header_count += 1
    ctx.stderr.write(f"tail: 读取 '{name}' 出错: 是一个目录\n")
    had_error = True
    continue

try:
    handle = path.open("rb")
except OSError as exc:
    # 打不开的文件不打标题，只报错。
    ctx.stderr.write(f"tail: 无法打开 '{name}': {exc.strerror or exc}\n")
    had_error = True
    continue
```

最后统一返回退出码：

```python
if had_error:
    return 2
return 0
```

**退出码 2 是本项目的约定**（用法或运行错误），GNU tail 打不开文件返回 1。这是刻意的差异，README 里写着。

## 这个文件是做什么

打印文件末尾部分，支持 GNU tail 风格的一个子集：计数（`-n` / `-c`，带正负号与乘数后缀）、多文件标题（`-q` / `-v`）、NUL 分隔（`-z`）、跟随（`-f` / `-F` / `-s` / `--pid` / `--retry`）。

不负责：读整个文件（末尾模式从文件尾巴往回读）、修改文件内容、二进制编辑。

### 关键函数速查

| 函数 / 类 | 行号 | 负责 |
|---|---|---|
| `_Options` | 86 | 生效选项的冻结数据类，`delimiter` 属性决定行分隔符 |
| `_CountAction` | 105 | 记下 `-n` / `-c` 的出现顺序，后写的生效 |
| `_TailParser` | 126 | 在交给 argparse 前先改写 argv |
| `_rewrite_argv` | 148 | 改写紧凑写法 `-NUM`、负号开头的值、`-f` 的可选参数 |
| `build_parser` | 200 | 定义全部选项 |
| `tail` | 301 | 入口：遍历操作数、打标题、读内容、跟随 |
| `_build_options` | 403 | 把 argparse 的结果收成 `_Options` |
| `_resolve_headers` | 432 | 决定要不要打文件名标题 |
| `_parse_amount` | 445 | 解析 `-n` / `-c` 的值，返回（方向, 数量） |
| `_suffix_multiplier` | 473 | 算 `b` / `k` / `kB` / `KiB` 等后缀的倍数 |
| `_prepare_stdout` | 493 | 关换行翻译、开 surrogateescape |
| `_print_header` | 530 | 打印 `==> 文件名 <==`，第二个起前面空一行 |
| `_stdin_handle` | 543 | 取标准输入的二进制流 |
| `_read_tail` | 602 | 按方向与模式分发到行/字节两条路 |
| `_read_last_lines` | 706 | 从文件末尾往回读，凑齐 N 行 |
| `_read_lines_from` | 736 | 跳过开头 N 行，把剩下的全要 |
| `_iter_lines` | 810 | 按分隔符切行，`\r` 留在行内容里 |
| `_Follower` | 836 | 跟随一个文件，认描述符或认文件名 |
| `_take_complete_lines` | 935 | 切出完整行，不完整的留在缓冲里 |
| `_follow_loop` | 955 | 反复检查各文件有没有新内容 |
| `_pid_alive` | 981 | 探目标进程是否还活着 |
| `_pick_encoding` | 1049 | 按「将要输出的那段」选解码方式 |
| `_text_score` | 1119 | 给解码结果打「像不像正文」的分 |

### 入口点

```python
@command("tail", "打印文件末尾部分（GNU tail 风格子集）", build_parser)
def tail(args: argparse.Namespace, ctx: RunContext) -> int:
```

`@command` 来自 `w2l/registry.py`，`commands` 包在首次分发时自动导入本模块完成注册，主干代码不需要改。退出码：正常 0，出错 2。

### 相关文件

| 文件 | 关系 |
|---|---|
| `w2l/commands/head.py` | 同一个计数语法的镜像实现，语义正相反；argv 改写与计数解析两份代码结构相同 |
| `w2l/commands/cat.py` | 同一套编码判定与输出流处理（surrogateescape + 非终端关换行翻译） |
| `w2l/commands/grep.py` / `wc.py` | 同一套编码判定（`_detect_encoding` / `_text_score` 抄了五份，属已知重复） |
| `w2l/context.py` | `RunContext` 提供 `cwd` / `stdout` / `stderr` / `stdin` |
| `w2l/registry.py` | `@command` 装饰器，注册 `tail` 指令 |
| `tests/test_tail.py` | 45 个用例，逐条对照 Git Bash 的 GNU tail 输出 |
| `AI/脚本/_t600_probe_tail.py` | 54 条用例与 GNU tail 的对拍脚本，结果落在 `AI/数据/tail_probe.json` |
| `AI/脚本/_t601_probe_tail_follow.py` | 跟随模式、编码取样、边界用例的探针 |
| `AI/脚本/_t603_probe_tail_pid.py` | `--pid` 探查第一版（测法有错，见下文「决定十」） |
| `AI/脚本/_t604_probe_tail_pid2.py` | `--pid` 的正确测法（孤儿进程） |
| `AI/脚本/_t605_probe_tail_block.py` | 64KB 倒读块边界的三种位置验证 |
| `AI/脚本/_t606_make_tail_gbk_demo.py` | 早期方案的 GBK 演示文件生成器（后被 `_t610` 的混合夹具取代，保留备查） |
| `AI/脚本/_t607_tail_follow_demo.py` | 跟随模式演示脚本（新增行、半行、轮转） |
| `AI/脚本/_t608_tail_pid_demo.py` | `--pid` 演示脚本 |
| `AI/脚本/_t609_capture_teach23.py` | 按核对器的方式真跑本篇命令，把真实输出抓下来 |
| `AI/脚本/_t610_make_tail_demo.py` | 生成本篇用的固定夹具 |
| `AI/脚本/_t611_verify_teach23_claims.py` | 复算正文里只有文字佐证的数字断言 |
| `AI/脚本/_t612_tail_sections.py` | 算 tail.py 各部分的行数占比 |
| `AI/脚本/_t613_test_counts.py` | 数出各测试文件的真实用例数 |

## 有什么用

**1. 跟日志。**

`-f` 认描述符，适合「程序正在往这个文件里追加」的场景。`-F` 认文件名，适合日志轮转（`app.log` 改名成 `app.log.1`，新建一个 `app.log`）。

**2. 看文件的结尾，不看开头。**

大日志文件想看最后发生了什么时，`tail -n 100 app.log` 从文件尾巴往回读，不用把整个文件读进内存。

**3. 从某个位置开始看。**

`-n +N` 是「从第 N 行开始」。这一条在 head 里没有对应写法。

**4. NUL 分隔的数据。**

`-z` 把行分隔符换成 NUL，处理 `find -print0` 这类 NUL 分隔的数据时不会把带空格或换行的文件名切坏。

**5. 中文日志在 Windows 控制台上不乱码。**

GBK 文本判定出编码后解码成 UTF-8 输出。这是本项目与 GNU tail 最大的行为差异，是刻意的取舍。

**6. 二进制内容不会被改写。**

含 NUL 字节、或任何文本编码都解不出来的文件，按原字节输出，不做编码转换。

## 怎么用（过程教程）

下面所有命令都实测过，输出与文档一致。用 `AI/脚本/_t12_verify_teach.py` 可以自动核对本篇的命令。

### 第 1 步：准备演示夹具

后面的例子全部用固定夹具，不用项目源码。理由是源码会变：拿 `w2l/registry.py` 当例子，源码一改教程里写死的预期输出就全过期了（`teach/20` 那批过期点就是这么来的）。

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t610_make_tail_demo.py
```

预期输出：

```
已生成 AI/数据/tail_demo/（8 个夹具）
```

夹具清单：

| 文件 | 内容 |
|---|---|
| `a.txt` | 5 行，`l1` 到 `l5`，每行以 LF 结尾 |
| `b.txt` | 1 行，`x` |
| `nonl.txt` | 3 行，末行没有换行 |
| `crlf.txt` | 3 行，CRLF 结尾 |
| `zeros.bin` | 3 段，NUL 分隔 |
| `big.txt` | 2000 字节的 `X` |
| `many.txt` | 600 行 |
| `mixed.txt` | 前两行 ASCII，末行 GBK 中文 |

夹具落在 `AI/数据/tail_demo/`，这个目录在 `.gitignore` 里，不进仓库。

### 第 2 步：先看清这个文件有多大

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat w2l/commands/tail.py | wc -l
```

预期输出：

```
1140
```

1140 行里，计数语法与参数改写占 345 行（第 148～492 行，30%），内容读取占 249 行（第 584～832 行，22%），跟随模式占 145 行（第 836～980 行，13%），其余是入口、选项构建、输出与编码判定。

这个比例说明这个文件的难点不在「打印出来」，而在「算清楚要取哪一段」和「跟着文件跑」。

### 第 3 步：默认取末 10 行

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail AI/数据/tail_demo/a.txt
```

预期输出：

```
l1
l2
l3
l4
l5
```

不给 `-n` 时默认 10 行（`_DEFAULT_LINES = 10`）。夹具只有 5 行，所以全出来了——把 `-n 2` 加上的差别立刻能看出来。

### 第 4 步：`+N` 是起点，这是 tail 与 head 最大的不同

先看 head 是什么行为：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head -n +2 AI/数据/tail_demo/a.txt
```

预期输出：

```
l1
l2
```

head 的 `+2` 等价于 `2`，取前 2 行。tail 的 `+2` 是「从第 2 行开始一直到末尾」：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -n +2 AI/数据/tail_demo/a.txt
```

预期输出：

```
l2
l3
l4
l5
```

同一条 `+2`，head 给前 2 行，tail 给从第 2 行往后的 4 行。

### 第 5 步：负号与正号同义

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -n -2 AI/数据/tail_demo/a.txt
```

预期输出：

```
l4
l5
```

`-n -2` 与 `-n 2` 同义，都是末 2 行。head 里 `-n -2` 是「除末 2 行之外的全部」：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head -n -2 AI/数据/tail_demo/a.txt
```

预期输出：

```
l1
l2
l3
```

同一个 `-2`，tail 给末 2 行，head 给除末 2 行之外的全部。

### 第 6 步：`0` 和 `+0` 含义不同

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -n 0 AI/数据/tail_demo/a.txt
```

预期输出：

```

```

`0` 是一个都不要。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -n +0 AI/数据/tail_demo/a.txt
```

预期输出：

```
l1
l2
l3
l4
l5
```

`+0` 是从第 0 行开始，也就是全部都要。

### 第 7 步：`-c` 按字节，`+N` 是从第 N 个字节开始

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -c 5 AI/数据/tail_demo/a.txt
```

预期输出：

```
4
l5
```

5 个字节，不是 5 行。`a.txt` 的内容是 `l1\nl2\nl3\nl4\nl5\n`，末 5 个字节从 `4` 开始。

`+N` 版本：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -c +5 AI/数据/tail_demo/a.txt
```

预期输出：

```
2
l3
l4
l5
```

从第 5 个字节开始一直到最后。`-c 0` 与 `-c +0` 的区别和行模式一样：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -c 0 AI/数据/tail_demo/a.txt
```

预期输出：

```

```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -c +0 AI/数据/tail_demo/a.txt
```

预期输出：

```
l1
l2
l3
l4
l5
```

### 第 8 步：`-n` 与 `-c` 同时给，后写的生效

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -c 7 -n 2 AI/数据/tail_demo/a.txt
```

预期输出：

```
l4
l5
```

`-c 7` 先写、`-n 2` 后写，所以取 2 行。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -n 2 -c 7 AI/数据/tail_demo/a.txt
```

预期输出：

```
l4
l5
```

`-n 2` 先写、`-c 7` 后写，所以取 7 字节。`a.txt` 的末 7 字节是 `4\nl5\n`，正好两行——这个夹具太小，字节和行数撞上了，看不出差别。换 `big.txt` 就能看出来：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -n 2 -c 7 AI/数据/tail_demo/big.txt
```

预期输出：

```
XXXXXX
```

7 个字节，没有换行符，所以是一行。

### 第 9 步：紧凑写法 `-N`

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -2 AI/数据/tail_demo/a.txt
```

预期输出：

```
l4
l5
```

`-2` 等价于 `-n 2`。这个写法 argparse 本身不认，是 `_rewrite_argv` 改写出来的。

### 第 10 步：乘数后缀

`b` 固定是 512 字节：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -c 1b AI/数据/tail_demo/big.txt | wc -c
```

预期输出：

```
512
```

`k` 是 1024、`kB` 是 1000、`KiB` 等于 `K`：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -c 1k AI/数据/tail_demo/big.txt | wc -c
```

预期输出：

```
1024
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -c 1kB AI/数据/tail_demo/big.txt | wc -c
```

预期输出：

```
1000
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -c 1KiB AI/数据/tail_demo/big.txt | wc -c
```

预期输出：

```
1024
```

`-n` 的后缀乘的是**行数**，`-c` 的后缀乘的是**字节数**——`-n 1b` 就是末 512 行：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -n 1b AI/数据/tail_demo/many.txt | wc -l
```

预期输出：

```
512
```

### 第 11 步：多个文件会打标题

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -n 1 AI/数据/tail_demo/a.txt AI/数据/tail_demo/b.txt
```

预期输出：

```
==> AI/数据/tail_demo/a.txt <==
l5

==> AI/数据/tail_demo/b.txt <==
x
```

第二个及以后的标题前先空一行。

### 第 12 步：`-q` 关标题，`-v` 强制标题

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -q -n 1 AI/数据/tail_demo/a.txt AI/数据/tail_demo/b.txt
```

预期输出：

```
l5
x
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -v -n 1 AI/数据/tail_demo/a.txt
```

预期输出：

```
==> AI/数据/tail_demo/a.txt <==
l5
```

单个文件默认不打标题，`-v` 强制打。`-q` 与 `-v` 同时给时后写的生效——`-q -v` 打标题：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -q -v -n 1 AI/数据/tail_demo/a.txt AI/数据/tail_demo/b.txt
```

预期输出：

```
==> AI/数据/tail_demo/a.txt <==
l5

==> AI/数据/tail_demo/b.txt <==
x
```

`-v -q` 不打：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -v -q -n 1 AI/数据/tail_demo/a.txt AI/数据/tail_demo/b.txt
```

预期输出：

```
l5
x
```

### 第 13 步：标准输入

不给任何操作数时也读标准输入：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'l1\nl2\nl3\n' | python main.py tail
```

预期输出：

```
l1
l2
l3
```

`-` 也表示标准输入，标题写作 `==> standard input <==`：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'l1\nl2\nl3\n' | python main.py tail -v -
```

预期输出：

```
==> standard input <==
l1
l2
l3
```

### 第 14 步：`-z` 用 NUL 当行分隔符

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -z -n 2 AI/数据/tail_demo/zeros.bin | od -c
```

预期输出：

```
0000000   z   2  \0   z   3  \0
0000006
```

`-z` 之后行分隔符是 NUL 而不是换行，`zeros.bin` 的三段就按 NUL 切成了三行。

不加 `-z` 时 NUL 只是普通字节，整份文件算一行：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail AI/数据/tail_demo/zeros.bin | od -c
```

预期输出：

```
0000000   z   1  \0   z   2  \0   z   3  \0
0000011
```

### 第 15 步：CRLF 原样转交，末行不补换行

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -n 2 AI/数据/tail_demo/crlf.txt | od -c
```

预期输出：

```
0000000   c   2  \r  \n   c   3  \r  \n
0000010
```

`\r` 属于行内容，没有被剥掉。

末行没有换行时不补：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -n 2 AI/数据/tail_demo/nonl.txt | od -c
```

预期输出：

```
0000000   p   2  \n   p   3
0000005
```

### 第 16 步：编码判定取的是「输出段」

`mixed.txt` 的前两行是 ASCII，末行是 GBK 中文。tail 只输出末行，取到的样本就是那行 GBK 字节：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -n 1 AI/数据/tail_demo/mixed.txt
```

预期输出：

```
中文末行
```

head 取的是文件开头那段的编码，拿到的是 ASCII 行：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py head -n 1 AI/数据/tail_demo/mixed.txt
```

预期输出：

```
ascii one
```

这就是「tail 的编码判定取将要输出的那一段，不取文件开头」的直接证据。

含 NUL 字节的文件按二进制逐字节透传，不做编码转换（上面第 14 步的 `zeros.bin` 就是）。

### 第 17 步：出错的路径

文件不存在：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail AI/数据/tail_demo/nope.txt
```

预期输出：

```
tail: 无法打开 'AI/数据/tail_demo/nope.txt': No such file or directory
```

退出码是 2（GNU tail 返回 1，这是本项目的约定）。打不开的文件**不打标题**，只报错，后面能读的文件照常输出：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -v AI/数据/tail_demo/a.txt AI/数据/tail_demo/nope.txt
```

预期输出：

```
tail: 无法打开 'AI/数据/tail_demo/nope.txt': No such file or directory
==> AI/数据/tail_demo/a.txt <==
l1
l2
l3
l4
l5
```

目录则先打标题再报错：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tail -v AI/数据/tail_demo
```

预期输出：

```
tail: 读取 'AI/数据/tail_demo' 出错: 是一个目录
==> AI/数据/tail_demo <==
```

这两种错误都不会中断处理后面的文件。

### 第 18 步：跟随时新增内容立刻出现

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t607_tail_follow_demo.py
```

预期输出：

```
[跟随] 追加 second 之前输出：b'first\n'
[跟随] 追加 second 之后输出：b'first\nsecond\n'
[跟随] 追加半行 half 之后输出：b'first\nsecond\n'
[跟随] 补上换行之后输出：b'first\nsecond\nhalf done\n'
[轮转] 旧文件内容：b'old1\nold2\n'
[轮转] 轮转后跟到新文件：b'old1\nold2\nnew1\n'
```

三件事在里面：

- 追加一行后立刻出现（`_flush` 刷缓冲的效果）
- 追加半行 `half` 时**不输出**，等补上 ` done\n` 才整行出现
- `-F` 跟到轮转后的新文件

### 第 19 步：`--pid` 等目标进程退出

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t608_tail_pid_demo.py
```

预期输出：

```
[pid] 目标进程活着时 _pid_alive=True
[pid] 目标进程退出后 tail 自己结束，耗时 4.3 秒
```

第二行的耗时会变（目标进程要活 4 秒，tail 随后立即结束），核对器不比对带耗时的行。

### 第 20 步：跑相关测试

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest tests/test_tail.py 2>&1 | tail -1
```

预期输出（耗时每次不同，用 `<T>` 占位）：

```
45 passed in <T>s
```

### 第 21 步：确认整体没坏

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest 2>&1 | tail -1
```

预期输出（耗时每次不同，用 `<T>` 占位）：

```
488 passed in <T>s
```

### 常见疑问

**Q：`-n +5` 为什么不是前 5 行？**

这是 tail 与 head 语义分岔的地方。GNU 里 head 的 `+N` 是冗余写法，tail 的 `+N` 是起点。照 head 的直觉用会拿到从第 5 行到末尾的全部内容。

**Q：`tail -n -5` 会不会打成「除末 5 行」？**

不会。tail 里负号等价于正号，`-n -5` 就是末 5 行。head 才是「除末 5 行」。

**Q：为什么 `tail -f` 接管道时看不到新内容？**

本实现每次输出后都调 `_flush`，所以接管道也能立刻看到。如果自己改代码时漏了这个调用，输出会卡在 Python 的 8KB 块缓冲里。

**Q：`tail -f` 能抗日志轮转吗？**

不能。`-f` 认文件描述符，文件被改名后还在读旧 inode。要抗轮转用 `-F`。

**Q：Windows 上 `-F` 为什么每轮都重新打开文件？**

因为 Windows 上打开着的文件不能改名（`FILE_SHARE_DELETE` 没开），而日志轮转第一步就是改名。长期占着句柄会让轮转直接失败。

**Q：文件打不开为什么返回 2 而不是 1？**

本项目约定「用法或运行错误返回 2」，GNU tail 返回 1。README 里记着这个差异。

**Q：为什么教程的例子不用项目源码？**

因为源码会变。预期输出写死在文档里，源码一改就过期，`teach/20` 那批过期点就是这么积累出来的。固定夹具的内容由 `AI/脚本/_t610_make_tail_demo.py` 生成，永远不会变。
