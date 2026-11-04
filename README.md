# Windows-to-Linux

在 Windows 上用 Python 复刻常用 Linux 命令行能力，统一入口：

```
python main.py <指令> [参数]
```

当前实现：`grep`（GNU grep 风格子集）、`ls`（GNU ls 风格子集）、`cat`（GNU cat 风格子集）、`head`（GNU head 风格子集）、`tail`（GNU tail 风格子集）。后续指令按同一模式接入，主干代码不需要改动。

纯标准库实现，零第三方依赖，`git clone` 后直接可跑。

## 快速开始

```bash
python main.py                          # 列出可用指令
python main.py grep --help              # 查看 grep 用法
python main.py grep -rn "TODO" src      # 递归搜索并显示行号
python main.py grep -ril "error" .      # 递归列出含匹配的文件名
python main.py grep -cE "ERROR|FATAL" app.log
python main.py grep -oE "https?://\S+" notes.txt
python main.py ls                       # 列出当前目录
python main.py ls -l w2l                # 长格式：权限、大小、时间、名称
python main.py ls -R w2l/commands       # 递归列出目录树
python main.py cat w2l/cli.py           # 打印文件内容
python main.py cat -n w2l/registry.py   # 带行号打印
python main.py cat README.md AGENTS.md  # 连接多个文件
python main.py head w2l/cli.py          # 打印文件开头 10 行
python main.py head -n 20 w2l/registry.py  # 打印开头 20 行
python main.py head -c 512 w2l/context.py   # 打印开头 512 字节
python main.py tail w2l/cli.py          # 打印文件末尾 10 行
python main.py tail -n 20 w2l/registry.py  # 打印末尾 20 行
python main.py tail -n +20 w2l/cli.py   # 从第 20 行开始到最后
python main.py tail -f app.log          # 持续跟踪日志新增内容
```

## 全局命令 `dmlinux`

不想每次都 `cd` 回项目目录再敲 `python main.py`？把 `bin/` 目录加进 PATH 之后，任意目录下直接敲 `dmlinux`：

```bash
dmlinux grep -rn "TODO" src
dmlinux grep --help
```

`bin/` 里放了两份启动器，覆盖三类终端：

| 文件 | 适用终端 | 命中方式 |
| --- | --- | --- |
| `bin/dmlinux.cmd` | cmd.exe、PowerShell | `PATHEXT` 自动补 `.CMD` |
| `bin/dmlinux` | git-bash、WSL、任意 POSIX shell | PATH 精确同名命中（无扩展名） |

两份启动器都从**脚本自身所在目录**反推项目根目录（`bin/` 的上一级），不写死绝对路径，因此整个 `bin/` 目录可以随便挪位置、换机器、重新 clone，行为不变。启动器只做三件事：定位项目根 → 找可用的 Python 解释器（`python` → `python3` → `py -3`）→ 原样透传参数与退出码。编码统一仍由 `w2l/cli.py` 负责，启动器不插手，所以中文输出和管道行为跟 `python main.py` 完全一致。

启动器还会设置 `DMLINUX=1` 环境变量，帮助文案据此跟着入口名走：`dmlinux --help` 显示 `用法: dmlinux <指令> [参数]`，而直接跑 `python main.py --help` 仍显示 `python main.py`。

### 把 `bin` 加进 PATH（一次性）

推荐用图形界面，避开 `setx` 的坑：

1. `Win` 键搜索「环境变量」→ 打开「编辑系统环境变量」
2. 点「环境变量」按钮
3. 在上半部分「用户变量」里找到 `Path` → 双击编辑
4. 点「新建」，填 `bin` 的**绝对路径**，例如 `E:\1\NULL\Windows-to-Linux\bin`
5. 一路确定，然后**重开一个终端**（已开的终端不会刷新 PATH）

用 `setx` 也行，但有三个坑：

- `setx` 会把 `PATH` 截断到 1024 字符，老机器上可能把后面的路径截掉
- `setx` 不展开 `%USERPROFILE%` 之类的变量，必须写绝对路径
- 不加 `/M` 只写用户变量；`/M` 改系统变量需要管理员权限

### 验证

```bash
where dmlinux                                  # cmd / PowerShell：应指向 bin\dmlinux.cmd
dmlinux --help                                 # 列出可用指令
dmlinux grep -rn "TODO" E:\1\NULL\Windows-to-Linux
```

### 注意事项

- **两份文件都别删**：cmd/PowerShell 靠 `dmlinux.cmd`，git-bash 靠无扩展名的 `dmlinux`，两边各用各的（同名共存时 cmd 会优先选 `.cmd`，已实测）。
- **`dmlinux.cmd` 保持纯 ASCII**：cmd.exe 按控制台 OEM 代码页读批处理文件，文件里写中文会乱码，所以它的报错信息是英文的；无扩展名那份是 UTF-8，报错信息是中文。
- **Python 必须在 PATH 里**：找不到 `python`、`python3`、`py` 时启动器返回退出码 `2` 并提示。
- **`dmlinux` 不切换当前目录**：相对路径按你所在目录解析，与 GNU grep 一致。

## grep 能力清单

| 选项 | 含义 |
| --- | --- |
| `-i` | 忽略大小写 |
| `-v` | 反向匹配，输出不匹配的行 |
| `-n` | 显示行号 |
| `-r` | 递归搜索目录 |
| `-E` | 使用扩展正则 ERE（默认基本正则 BRE） |
| `-w` | 只匹配构成完整单词的片段 |
| `-c` | 只输出每个文件的匹配行数 |
| `-l` | 只输出含有匹配的文件名 |
| `-o` | 只输出匹配到的部分 |

行为细节对齐 GNU grep：

- **正则默认 BRE**：默认模式下 `+ ? | ( ) { }` 是字面量，`\+ \| \( \)` 才是元字符；加 `-E` 切换为扩展正则。
- **退出码**：`0` 有命中，`1` 无命中，`2` 出错（文件不存在等）。可直接用于 PowerShell/CI 判断。
- **文件编码自动判定**：按解码结果的文本可信度择优，不是「第一个能解码的就算」。GBK 文件在英文 Windows 上也能搜出中文（系统编码 `cp1252` 会把 GBK 字节解成乱码，按顺序取会让中文永远搜不到）。
- **二进制文件**：不输出乱码内容，改为提示 `Binary file xxx matches`。
- **多文件前缀**：搜索多个文件或递归搜索时输出 `文件:行号:内容`。
- **不给路径时的行为**：在终端里直接敲 `python main.py grep "id"`，默认递归搜索当前目录（等价于 `grep -r "id" .`），输出带文件名前缀。标准输入是管道时按 GNU 语义读 stdin（`echo x | python main.py grep "id"`）。

## ls 能力清单

| 选项 | 含义 | 示例命令 |
| --- | --- | --- |
| （无） | 列出当前目录内容，按名字排序，每行一个条目 | `python main.py ls` |
| `-l` | 长格式：权限、大小、修改时间、名称 | `python main.py ls -l w2l` |
| `-a` | 显示全部条目，含 `.` 与 `..` | `python main.py ls -a w2l` |
| `-A` | 显示隐藏条目，但不含 `.` 与 `..` | `python main.py ls -A w2l` |
| `-h` | 大小按 1024 进制缩写（K/M/G），配合 `-l` 使用 | `python main.py ls -lh w2l/commands` |
| `-d` | 列出目录本身而不是它的内容 | `python main.py ls -d w2l/commands` |
| `-t` | 按修改时间排序，最新的在前 | `python main.py ls -t w2l` |
| `-S` | 按大小排序，最大的在前 | `python main.py ls -S w2l/commands` |
| `-r` | 反向输出排序结果 | `python main.py ls -r w2l` |
| `-F` | 名称后追加类型标记（目录 `/`、可执行 `*`、链接 `@`） | `python main.py ls -F w2l/commands` |
| `-R` | 递归列出子目录，每级目录带 `目录:` 标题 | `python main.py ls -R w2l/commands` |
| `-1` | 每行一个条目（默认行为，保留该选项只为兼容习惯用法） | `python main.py ls -1 w2l` |

行为细节对齐 GNU ls：

- **默认按名字排序**：字节序，大写字母在前（`Beta.txt` 排在 `alpha.txt` 前面），与 GNU 的 C 区域一致。
- **`-h` 不是 `--help`**：GNU 的 `-h` 是 `--human-readable`，所以本指令的用法说明只能用 `--help`。
- **每行一个条目**：输出不排成多列。GNU 在输出不是终端时也是这么做的，管道和脚本里行为一致。
- **多个操作数**：普通文件先统一排序输出，目录随后各自成块并带 `目录:` 标题，块之间空一行。
- **文件操作数按原样打印**：`python main.py ls w2l/cli.py` 输出完整路径，跟 GNU 一样不回退成文件名。

Windows 环境下的差异（都是平台本身没有对应概念，不是实现取巧）：

- **长格式只有四列**：没有链接数、属主、属组。Windows 没有 POSIX 的属主/属组语义，硬凑只会填一列假数字。
- **权限位来自 Windows 合成值**：普通文件显示 `-rw-rw-rw-`、只读文件 `-r--r--r--`、目录 `drwxrwxrwx`，是 Python `os.stat` 在 Windows 上合出来的，不等价于 POSIX 权限。
- **没有 `total N` 汇总行**：Windows 的 `stat` 没有 `st_blocks`，拿不到 GNU 的块数口径。
- **空目录返回退出码 1**（GNU 返回 0），遵循本项目统一的「无结果返回 1」约定，脚本里可直接用它判断目录是否为空。

## cat 能力清单

| 选项 | 含义 | 示例命令 |
| --- | --- | --- |
| （无） | 按顺序连接多个文件并输出，不给文件时读标准输入 | `python main.py cat w2l/cli.py` |
| `-n` | 给所有输出行编号，编号右对齐占 6 位后跟制表符 | `python main.py cat -n w2l/registry.py` |
| `-b` | 只给非空行编号（与 `-n` 同开时以 `-b` 为准） | `python main.py cat -b w2l/registry.py` |
| `-E` | 在每行末尾显示 `$` | `python main.py cat -E w2l/registry.py` |
| `-e` | 等价于 `-vE`：既显示 `$` 又显示非打印字符 | `python main.py cat -e w2l/registry.py` |
| `-T` | 把制表符显示成 `^I` | `python main.py cat -T w2l/registry.py` |
| `-t` | 等价于 `-vT`：既显示 `^I` 又显示非打印字符 | `python main.py cat -t w2l/registry.py` |
| `-s` | 把连续空行压成一行 | `python main.py cat -s w2l/registry.py` |
| `-v` | 用 `^` 与 `M-` 记号显示非打印字符 | `python main.py cat -v w2l/registry.py` |
| `-A` | 等价于 `-vET` | `python main.py cat -A w2l/registry.py` |
| `-u` | 立即输出不缓冲（本实现无实际影响，保留只为兼容习惯用法） | `python main.py cat -u w2l/registry.py` |

行为细节对齐 GNU cat：

- **编号格式**：右对齐占 6 位再跟一个制表符，第 10 行是 `    10\t`，与 GNU 完全一致。
- **`-b` 覆盖 `-n`**：两个选项同开时以 `-b` 为准，与给出的先后顺序无关。
- **跨文件延续**：行号在多个文件之间连续累计，不在文件边界重置；`-s` 的空行压紧状态也跨文件延续。
- **`-` 表示标准输入**：不给任何操作数时也读标准输入；操作数 `-` 可以出现在中间，位置即读取顺序。
- **空行的判定**：只有内容完全为空的行才算空行。含空格的行不算，所以 `-s` 不压它、`-b` 照样给它编号。
- **换行只认 `\n`**：`\r` 留在行内容里，所以 CRLF 文件的空行内容是 `\r`，不算空行。
- **末行不补换行**：文件末尾没有换行符时，输出也不加，GNU 行为一致。
- **`-v` 按字节算**：控制字符显示成 `^X`（`^@`、`^G`、`^?`），高位字节显示成 `M-` 加低七位（`M-^@`、`M- `）。

Windows 环境下的差异（都是本项目的取舍，不是实现取巧）：

- **文本按判定出的编码解码，输出统一 UTF-8**：GBK 文件在英文 Windows 上也能正确显示中文。GNU cat 是字节透传，会把 GBK 字节原样写出去。
- **二进制文件逐字节原样转交**：含 NUL 字节、或任何文本编码都解不出来的文件，按原字节输出，不做编码转换，`cat` 后接校验和工具结果与源文件一致。
- **文件打不开返回退出码 2**（GNU cat 返回 1），遵循本项目「用法或运行错误返回 2」的约定；其余文件照常输出，不中断。
- **控制台里换行仍是 CRLF**：管道与重定向时按原样转交文件里的 LF/CRLF，输出与源文件逐字节一致。

## head 能力清单

| 选项 | 含义 | 示例命令 |
| --- | --- | --- |
| （无） | 打印每个文件的开头 10 行，不给文件时读标准输入 | `python main.py head w2l/cli.py` |
| `-n` | 打印前 NUM 行，默认 10；NUM 带负号表示除末 NUM 行之外全要 | `python main.py head -n 20 w2l/registry.py` |
| `-c` | 打印前 NUM 字节；与 `-n` 同时给时后写的生效 | `python main.py head -c 512 w2l/context.py` |
| `-q` | 不打印文件名标题（别名 `--quiet`、`--silent`） | `python main.py head -q w2l/cli.py w2l/context.py` |
| `-v` | 总是打印文件名标题（别名 `--verbose`） | `python main.py head -v w2l/cli.py` |
| `-z` | 行分隔符换成 NUL 而不是换行（用于 NUL 分隔的数据） | `python main.py head -z w2l/registry.py` |

行为细节对齐 GNU head：

- **计数带正负号**：`+NUM` 与 `NUM` 等价，`-NUM` 表示「除末 NUM 行/字节之外全要」。head 没有 tail 那种「从第 N 行开始」的语义。
- **`0` 与 `-0` 含义不同**：`-n 0` 一行不要，`-n -0` 全部都要。
- **`-n` 与 `-c` 后写的生效**：`-c 7 -n 2` 取 2 行，`-n 2 -c 7` 取 7 字节。
- **`-q` 与 `-v` 后写的生效**：`-q -v` 打标题，`-v -q` 不打。
- **乘数后缀**：`b`=512，`k`/`K`=1024，`m`/`M`=1024²，`G`=1024³，`T`=1024⁴，`P`=1024⁵，`E`=1024⁶；字母加 `B` 是 1000 进制（`kB`=1000、`MB`=1000²），字母加 `iB` 是二进制前缀（`KiB`=`K`、`MiB`=`M`）。
- **紧凑写法 `-NUM`**：等价于 `-n NUM`，`python main.py head -20 w2l/cli.py` 就是前 20 行。
- **多文件标题**：格式是 `==> 文件名 <==`，第二个及以后的标题前先空一行。
- **打不开的文件不打标题**：只报错并继续处理后面的文件；目录则先打标题再报「是一个目录」，与 GNU 一致。
- **`-` 表示标准输入**：不给任何操作数时也读标准输入，标题写作 `==> standard input <==`。
- **换行只认 `\n`**：`\r` 留在行内容里，所以 CRLF 文件的内容原样转交。
- **末行不补换行**：文件末尾没有换行符时，输出也不加。

Windows 环境下的差异（都是本项目的取舍，不是实现取巧）：

- **文本按判定出的编码解码，输出统一 UTF-8**：GBK 文件在英文 Windows 上也能正确显示中文。GNU head 是字节透传，会把 GBK 字节原样写出去。
- **二进制文件逐字节原样转交**：含 NUL 字节、或任何文本编码都解不出来的文件，按原字节输出，不做编码转换。
- **`-c` 的字节数按源文件算**：GBK 文本输出成 UTF-8 后字节数会变多，但取的仍是源文件的前 N 个字节。
- **文件打不开返回退出码 2**（GNU head 返回 1），遵循本项目「用法或运行错误返回 2」的约定；其余文件照常输出，不中断。

## tail 能力清单

| 选项 | 含义 | 示例命令 |
| --- | --- | --- |
| （无） | 打印每个文件的末尾 10 行，不给文件时读标准输入 | `python main.py tail w2l/cli.py` |
| `-n` | 打印末 NUM 行，默认 10；NUM 带 `+` 号表示从第 NUM 行开始 | `python main.py tail -n 20 w2l/registry.py` |
| `-c` | 打印末 NUM 字节；NUM 带 `+` 号表示从第 NUM 字节开始；与 `-n` 同时给时后写的生效 | `python main.py tail -c 512 w2l/context.py` |
| `-q` | 不打印文件名标题（别名 `--quiet`、`--silent`） | `python main.py tail -q w2l/cli.py w2l/context.py` |
| `-v` | 总是打印文件名标题（别名 `--verbose`） | `python main.py tail -v w2l/cli.py` |
| `-z` | 行分隔符换成 NUL 而不是换行（用于 NUL 分隔的数据） | `python main.py tail -z w2l/registry.py` |
| `-f` | 跟随文件增长，持续输出新追加的内容（别名 `--follow`） | `python main.py tail -f w2l/cli.py` |
| `-F` | 按文件名跟随，日志轮转后自动跟到新文件 | `python main.py tail -F w2l/cli.py` |
| `-s` | 跟随时两次检查之间的间隔秒数，默认 1（别名 `--sleep-interval`） | `python main.py tail -f -s 0.5 w2l/cli.py` |
| `--pid` | 跟随时，等这个进程退出就结束 | `python main.py tail -f --pid 1234 w2l/cli.py` |
| `--retry` | 文件暂时打不开时继续重试而不是放弃 | `python main.py tail -F --retry w2l/cli.py` |

行为细节对齐 GNU tail：

- **`+NUM` 是起点，不是等价写法**：这是 tail 与 head 最大的不同。`-n 5` 取末 5 行，`-n +5` 从第 5 行开始一直到最后。`-c` 同理，只是单位是字节。
- **负号等价于正号**：`-n -5` 与 `-n 5` 同义，都是取末 5 个。`-n 0` 一个不要，`-n +0` 全部都要。
- **`-n` 与 `-c` 后写的生效**：`-c 7 -n 2` 取 2 行，`-n 2 -c 7` 取 7 字节。
- **`-q` 与 `-v` 后写的生效**：`-q -v` 打标题，`-v -q` 不打。
- **乘数后缀**：`b`=512，`k`/`K`=1024，`m`/`M`=1024²，`G`=1024³，`T`=1024⁴，`P`=1024⁵，`E`=1024⁶；字母加 `B` 是 1000 进制（`kB`=1000、`MB`=1000²），字母加 `iB` 是二进制前缀（`KiB`=`K`、`MiB`=`M`）。`-n` 的后缀乘的是**行数**（`-n 1b` 就是 512 行），`-c` 的后缀乘的是**字节数**。
- **紧凑写法 `-NUM`**：等价于 `-n NUM`，`python main.py tail -20 w2l/cli.py` 就是末 20 行。
- **多文件标题**：格式是 `==> 文件名 <==`，第二个及以后的标题前先空一行。
- **打不开的文件不打标题**：只报错并继续处理后面的文件；目录则先打标题再报「是一个目录」，与 GNU 一致。
- **`-` 表示标准输入**：不给任何操作数时也读标准输入，标题写作 `==> standard input <==`。
- **换行只认 `\n`**：`\r` 留在行内容里，所以 CRLF 文件的内容原样转交。
- **末行不补换行**：文件末尾没有换行符时，输出也不加；末行没有换行符时它**也算一行**。
- **`-z` 只改行分隔符**：`-z` 下 `\n` 不再分行，整个文件算一行。
- **跟随时半行要等换行符**：写日志的程序正在写一半时，那半行先留在缓冲里，等换行符到了再整体输出，不会出现半截行。
- **`-f` 与 `-F` 的区别**：`-f` 按文件描述符跟，文件被改名了也照样跟旧内容；`-F` 按文件名跟，文件被轮转掉（改名后新建同名文件）就自动跟到新文件。

Windows 环境下的差异（都是本项目的取舍，不是实现取巧）：

- **文本按判定出的编码解码，输出统一 UTF-8**：GBK 文件在英文 Windows 上也能正确显示中文。GNU tail 是字节透传，会把 GBK 字节原样写出去。编码判定取的是「将要输出的那一段」而不是文件开头，所以 GBK 日志的末尾照样出中文。
- **二进制文件逐字节原样转交**：含 NUL 字节、或任何文本编码都解不出来的文件，按原字节输出，不做编码转换。
- **`-c` 的字节数按源文件算**：GBK 文本输出成 UTF-8 后字节数会变多，但取的仍是源文件的末 N 个字节。
- **文件打不开返回退出码 2**（GNU tail 返回 1），遵循本项目「用法或运行错误返回 2」的约定；其余文件照常输出，不中断。
- **`-F` 跟随时不长期占着文件句柄**：Windows 上打开着的文件不能改名（没开 `FILE_SHARE_DELETE`），日志轮转第一步就是改名，长期占着句柄会直接失败。按文件名跟随时每轮都重新打开再关掉，避开这个限制。
- **`-f` 按描述符跟随时同样占着句柄**：此时文件被改名会失败，这是 Windows 的限制，不是实现取巧；需要抗轮转就用 `-F`。
- **`--max-unchanged-stats` 没实现**：GNU 用它定期重开文件来发现轮转，本实现直接比较文件标识，行为等价。

## 目录结构

```
Windows-to-Linux/
├── main.py                  # 薄入口，转调 w2l.cli:main
├── bin/                     # 全局启动器，把本目录加进 PATH 即可用 dmlinux
│   ├── dmlinux.cmd          # Windows（cmd/PowerShell）用
│   └── dmlinux              # git-bash / POSIX shell 用
├── w2l/
│   ├── cli.py               # 指令分发、帮助输出、异常与退出码处理
│   ├── registry.py          # 指令注册表 + @command 装饰器
│   ├── context.py           # 运行上下文（cwd / stdout / stderr / stdin）
│   ├── errors.py            # UsageError / CommandError
│   ├── entry.py             # 入口名（python main.py / dmlinux）跟随调用方式
│   └── commands/
│       ├── __init__.py      # 自动导入子模块完成注册
│       ├── grep.py          # grep 实现
│       ├── ls.py            # ls 实现
│       ├── cat.py           # cat 实现
│       ├── head.py          # head 实现
│       └── tail.py          # tail 实现
├── tests/
│   ├── conftest.py
│   ├── test_grep.py
│   ├── test_ls.py
│   ├── test_cat.py
│   ├── test_head.py
│   ├── test_tail.py
│   └── test_launcher.py     # 启动器端到端测试
├── pyproject.toml
└── .github/workflows/ci.yml
```

## 架构设计

四层，每层职责单一：

1. **入口层** `main.py`：只做 `sys.exit(main())`，不写任何逻辑。
2. **分发层** `w2l/cli.py`：查注册表 → 建解析器 → 建上下文 → 调处理器 → 把异常翻译成退出码。
3. **注册层** `w2l/registry.py`：`@command(name, summary, parser_factory)` 把处理函数登记进 `REGISTRY`。
4. **指令层** `w2l/commands/*.py`：每个指令一个模块，自带参数解析与业务逻辑，互不依赖。

关键设计点：

- **指令自动发现**：`commands/__init__.py` 用 `pkgutil.iter_modules` 导入全部子模块，新增指令文件即被注册，无需改分发层。
- **解析器工厂**：`parser_factory` 而不是共享解析器，保证每个指令的 `-h` 只显示自己的参数，不会互相污染短选项。
- **异常到退出码的映射集中在一处**：指令层只抛 `UsageError` / `CommandError`，退出码由 `cli.py` 统一决定。
- **上下文注入**：指令通过 `RunContext` 拿 cwd 与三个标准流，便于测试注入内存流，也方便以后加 `--json` 之类的输出通道。

## 如何新增一个指令

1. 新建 `w2l/commands/<名字>.py`。
2. 写 `build_parser()` 返回 `argparse.ArgumentParser`。
3. 写处理函数并用 `@command` 装饰：

```python
from ..context import RunContext
from ..registry import command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python main.py ls")
    parser.add_argument("path", nargs="?", default=".")
    return parser


@command("ls", "列出目录内容", build_parser)
def ls(args: argparse.Namespace, ctx: RunContext) -> int:
    for entry in sorted(ctx.cwd.joinpath(args.path).iterdir()):
        ctx.stdout.write(f"{entry.name}\n")
    return 0
```

4. 文件放进 `w2l/commands/` 即自动生效，`python main.py ls` 可直接调用。
5. 在 `tests/test_<名字>.py` 补测试。

约定：处理函数返回 `0` 表示成功；命中类指令用 `1` 表示「无结果」；用法错误抛 `UsageError`（退出码 2）。

## 后续演进路线

**阶段一：补齐 grep**

- `--include` / `--exclude` 文件过滤规则
- `-A` / `-B` / `-C` 上下文行
- `-h` / `-H` 显式控制文件名前缀
- `--color=auto|always|never` 彩色高亮
- `--binary-files=without|with` 二进制策略

**阶段二：常用命令族**

`ls`（已完成）、`cat`（已完成）、`head`（已完成）、`tail`（已完成）、`wc`、`find`、`tree`、`du`、`cp`、`mv`、`rm`、`chmod`、`sed`（行内替换）、`awk-lite`（字段投影）。先做「Windows 用户最常抱怨缺失」的那一批。

**阶段三：工程化**

- **并行搜索**：大目录树用 `multiprocessing` 分片并行，串行版本在大仓上是明显瓶颈，这是性能优化的第一优先级。
- **配置化**：`.w2lrc` 放默认选项（如默认递归、默认忽略目录、默认编码）。
- **结构化输出**：`--json` 输出机器可读结果，便于和其他工具串联。
- **Windows 特性适配**：长路径（>260 字符）、UNC 路径、符号链接（`mklink`）、权限位语义。

**阶段四：分发**

- 已有零安装方案：`bin/dmlinux` 启动器，把 `bin/` 加进 PATH 就能全局用（见上文「全局命令 `dmlinux`」）
- `pipx install` / `pip install -e .` 安装为 `w2l` 命令
- PyInstaller 打包成单文件 exe，免 Python 环境
- GitHub Releases 自动附带各平台构建产物

## 性能优化要点（按收益排序）

1. **并行遍历**：目录越大收益越明显，进程池按顶层子目录分片。
2. **二进制快速跳过**：已经做了头部 NUL 探测，避免全文解码。
3. **编码一次判定**：每个文件只探测一次，避免逐行重复判断。
4. **`mmap` + 正则扫描**：超大单文件时避免逐行 Python 循环开销。
5. **结果流式输出**：当前实现是流式的，不在内存里攒全部结果，大结果集不会撑爆内存。

## Git / GitHub 协作约定

- **分支模型**：`main` 保持可用，功能分支 `feat/<名字>`，修复分支 `fix/<名字>`，实验性 `spike/<名字>`。
- **提交信息**：Conventional Commits，例如 `feat(grep): 支持 -A/-B/-C 上下文行`、`fix(grep): 修正 GBK 文件编码判定`。
- **PR 要求**：一个 PR 只做一件事；描述里写清「改了什么 / 为什么 / 怎么验证」；CI 必须绿。
- **CI**（`.github/workflows/ci.yml`）：push 与 PR 触发，Python 3.10–3.14 矩阵跑 `pytest`。
- **版本与发布**：语义化版本，tag `v0.1.0` 对应一次可用的能力集，GitHub Release 附变更说明。

### 远程仓库

- 地址：`https://github.com/dom-one/Linux2Python`
- 本地目录名 `Windows-to-Linux`，仓库名 `Linux2Python`，两者指向同一个项目。
- 远端默认分支 `main`，本地 `main` 跟踪 `origin/main`。
- CI 在 push 与 PR 时触发，跑 Python 3.10–3.14 的 `pytest`。

### 常用命令

```bash
git status
git add -A
git commit -m "feat(ls): 实现 ls 指令"
git push origin main
```
