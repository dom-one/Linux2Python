# Windows-to-Linux

在 Windows 上用 Python 复刻常用 Linux 命令行能力，统一入口：

```
python main.py <指令> [参数]
```

当前实现：`grep`（GNU grep 风格子集）、`ls`（GNU ls 风格子集）、`cat`（GNU cat 风格子集）、`head`（GNU head 风格子集）、`tail`（GNU tail 风格子集）、`wc`（GNU wc 风格子集）、`find`（GNU find 风格子集）、`tree`（GNU tree 风格子集）、`du`（GNU du 风格子集）。后续指令按同一模式接入，主干代码不需要改动。

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
python main.py wc w2l/cli.py            # 统计行数、词数、字节数
python main.py wc -l README.md          # 只统计行数
python main.py wc -L README.md          # 最长行的显示宽度
python main.py find w2l -name '*.py'    # 按文件名找文件
python main.py find . -type f -size +1k # 按类型和大小找文件
python main.py find . -name '*.log' -mtime +7   # 找 7 天前改过的日志
python main.py find . -type d -name __pycache__ -prune -o -print  # 跳过目录
python main.py tree w2l                 # 树形列出目录
python main.py tree -L 2 w2l            # 只往下看两层
python main.py tree -d w2l              # 只看目录
python main.py tree -I '__pycache__' w2l  # 跳过匹配的名字
python main.py du w2l                # 统计目录占用
python main.py du -sh w2l tests      # 每个目录一行，人类可读
python main.py du -sb w2l            # 按字节精确统计
python main.py du -a -d 1 w2l        # 连文件一起列，只看第一层
python main.py du -t 1M w2l          # 略过 1MB 以下的小目录
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

## wc 能力清单

| 选项 | 含义 | 示例命令 |
| --- | --- | --- |
| （无） | 打印「行 词 字节」三列 | `python main.py wc w2l/cli.py` |
| `-l` | 打印行数 | `python main.py wc -l w2l/registry.py` |
| `-w` | 打印词数 | `python main.py wc -w README.md` |
| `-m` | 打印字符数 | `python main.py wc -m README.md` |
| `-c` | 打印字节数 | `python main.py wc -c README.md` |
| `-L` | 打印最长行的显示宽度 | `python main.py wc -L README.md` |

行为细节对齐 GNU wc：

- **默认三列**：不给任何选项时打印 行/词/字节；给了选项就只打印打开的那几列。
- **列的顺序固定**：行 → 词 → 字符 → 字节 → 最长行，与选项书写的顺序无关，`-clw` 和 `-lwc` 的输出一样。
- **行只按 `\n` 计**：文件末尾没有换行的那一行不算一行，但它的词照样算。
- **词的判定**：按空白分隔，空白包含空格、制表符、换行、回车、竖制表、换页；片段里夹着控制字符不算断开（`a\x01b` 算一个词），整个片段里一个可打印字符都没有时不算词（纯二进制内容词数是 0）。
- **`-m` 数字符不是数字节**：一个汉字算一个字符，字节数是 `-c` 的事。
- **`-L` 给的是显示列宽不是字符数**：全角字符算 2 列，制表符展开到 8 的倍数，`\r` 把列号清零；取这一行出现过的最大列数，`\r` 之后的宽度再大也不算数。
- **多文件打 total**：行/词/字符/字节求和，最长行取最大值（不是求和）。
- **`-` 表示标准输入**：不给任何操作数时也读标准输入，但那一行不写文件名；操作数 `-` 写在文件名列里。
- **重复的 `-` 只读一次标准输入**：第二个 `-` 读到的是空的，total 也只算一次。
- **列宽逐列算**：每列先按自己出现过的最大计数定下限；只打印一列、且不打 total 行时不做对齐，否则每列再按「普通文件字节数之和」撑开。标准输入与目录的大小事先数不出来，GNU 为它们预留 7 列。计数比预留宽度长时直接写长，不截断，所以 total 行的字节数可以比前面的行更宽。
- **打不开的文件不输出计数行**：只报错并继续处理后面的文件；目录则打一行全 0 再报错。

Windows 环境下的差异（都是本项目的取舍，不是实现取巧）：

- **文本按判定出的编码解码后统计**：GBK 里的汉字按 1 个字算（`-m`）、按 2 列算（`-L`），中文也算词字符。GNU 在 C 区域设置下解不出 GBK，会把字符数整个记成 0，中文文件的词数也是 0；换到匹配的区域设置（zh_CN.UTF-8）跑 GNU，数字与本实现一致。
- **解不出的字节既不算字符也不算词**，显示宽度算 0，与 GNU 一致。
- **文件打不开返回退出码 2**（GNU wc 返回 1），遵循本项目「用法或运行错误返回 2」的约定；其余文件照常统计，不中断。

## find 能力清单

| 选项 | 含义 | 示例命令 |
| --- | --- | --- |
| （无） | 打印所有找到的路径 | `python main.py find w2l` |
| `-name PATTERN` | 文件名匹配通配符（区分大小写） | `python main.py find w2l -name '*.py'` |
| `-iname PATTERN` | 同上，忽略大小写 | `python main.py find w2l -iname '*.PY'` |
| `-path PATTERN` | 整个路径匹配通配符 | `python main.py find . -path '*commands*'` |
| `-ipath PATTERN` | 同上，忽略大小写 | `python main.py find . -ipath '*COMMANDS*'` |
| `-regex PATTERN` | 整个路径匹配正则 | `python main.py find . -regex '.*\.py$'` |
| `-iregex PATTERN` | 同上，忽略大小写 | `python main.py find . -iregex '.*\.PY$'` |
| `-type [fd]` | 按类型筛选：`f` 普通文件、`d` 目录 | `python main.py find w2l -type d` |
| `-size N[cwkMG]` | 按大小筛选，默认 512 字节块，可带 `+`/`-` | `python main.py find . -size +10k` |
| `-mtime N` | N 天前修改过，可带 `+`/`-` | `python main.py find . -mtime +7` |
| `-mmin N` | N 分钟前修改过，可带 `+`/`-` | `python main.py find . -mmin -30` |
| `-newer FILE` | 比 FILE 的修改时间更新的文件 | `python main.py find . -newer w2l/cli.py` |
| `-empty` | 空文件或空目录 | `python main.py find . -empty` |
| `-true` / `-false` | 恒真 / 恒假 | `python main.py find . -true` |
| `-prune` | 命中后不再进入该目录 | `python main.py find . -type d -name __pycache__ -prune -o -print` |
| `-print` / `-print0` | 打印路径，用 NUL 分隔 | `python main.py find . -print0` |
| `-printf FORMAT` | 按格式打印 | `python main.py find . -printf '%f %s\n'` |
| `-exec CMD ;` | 对每个匹配执行一次命令 | `python main.py find . -name '*.py' -exec echo {} \;` |
| `-exec CMD +` | 把所有匹配攒成一批执行一次 | `python main.py find . -name '*.py' -exec echo {} +` |
| `-delete` | 删除匹配的文件（隐含 `-depth`） | `python main.py find . -name '*.tmp' -delete` |
| `-maxdepth N` | 最多往下走 N 层（操作数本身是第 0 层） | `python main.py find . -maxdepth 1` |
| `-mindepth N` | 不判定比 N 层浅的文件 | `python main.py find . -mindepth 2` |
| `-depth` | 后序遍历（先子项后父项） | `python main.py find . -depth` |
| `-H` / `-L` / `-P` | 符号链接处理方式（接受但不改行为，见下方说明） | `python main.py find . -P -name '*.py'` |
| `-a` / `-and` | 与 | `python main.py find . -name '*.py' -a -type f` |
| `-o` / `-or` | 或 | `python main.py find . -name '*.py' -o -name '*.md'` |
| `!` / `-not` | 非 | `python main.py find . ! -name '*.py'` |
| `( )` | 分组 | `python main.py find . \( -name '*.py' -o -name '*.md' \) -print` |

行为细节对齐 GNU findutils 4.10：

- **表达式是语言，不是选项**：路径写在前面（连续的、不以 `-` 开头的参数），从第一个像选项的参数开始算表达式。路径写在表达式后面会报错。
- **运算符优先级**：`!` 最高，`-a` 次之，`-o` 最低；两个谓词挨着写默认是 `-a`。
- **隐式 `-print`**：表达式里除了 `-prune` 之外没有别的动作时，自动在整条表达式后面接一个 `-print`；`-prune` 本身不算动作，所以 `find . -type d -prune` 仍会打印命中的目录。
- **动作会截断与运算**：`-print` 这类动作恒为真，且一旦执行就不再算同一层 `and` 链的右半边——所以 `-name '*.txt' -print -o -name '*.md' -print` 只会各打印一次。
- **遍历顺序**：按目录项的原始顺序（和 GNU 的 readdir 顺序一致），默认先序；`-depth` 改成后序。
- **`-size` 向上取整**：不带单位时按 512 字节块算，`-size 1` 命中 1~512 字节的文件；带 `c` 是精确字节数，`k`/`M`/`G` 分别是 1024/1024²/1024³ 字节，也都向上取整。
- **`-exec` 两种终止符**：`;` 每个文件跑一次，`+` 攒成一批跑一次；命令里没有 `{}` 时路径自动追加到末尾。
- **`-prune` 只挡下降**：命中后不再进入该目录，但这个目录本身仍会被打印和判定。
- **`-mindepth` 只挡判定**：比 N 层浅的文件不参与表达式求值，但仍然会被遍历下去。
- **`-printf` 支持的指令**：`%p` 路径、`%f` 文件名、`%h` 所在目录、`%s` 字节数、`%y` 类型（`f`/`d`）、`%T@` 纪元秒数、`%t` 修改时间、`%%` 字面量，以及 `\n`、`\t`、`\\` 等转义；不认识的指令按字面量原样输出（与 GNU 一致）。

Windows 环境下的差异（都是本项目的取舍，不是实现取巧）：

- **`-type` 只认 `f` 和 `d`**：符号链接、块设备、字符设备、FIFO 在 Windows 上不存在。
- **`-H` / `-L` / `-P` 接受但不改变行为**：Windows 上创建符号链接需要管理员权限（`os.symlink` 直接报 WinError 1314），符号链接目录遍历的收益远小于引入环路风险，所以这三个选项只做兼容接收。
- **目录的大小按 0 算**：Windows 的目录 `st_size` 不稳定（空目录是 0，条目一多就变成 4096），GNU 侧看到的目录大小恒为 0；这里统一按 0 处理，避免同一条命令的结果随目录内容变化。
- **`-mmin` 的整分钟计数把当前这一分钟算作第 1 分钟**：GNU findutils 4.10 实测，90 秒大的文件落在 `-mmin 2` 而不是 `-mmin 1`（而 `-mtime` 的天数计数没有这个偏移）；本实现按实测口径来，`-mmin +N` / `-mmin -N` 仍按 GNU 的自然语义（大于 N 分钟 / 小于 N 分钟）。
- **`-exec` 在 Windows 上退回 `cmd /c`**：GNU 直接 fork/exec 目标程序不走 shell，但 Windows 上 `echo`、`dir`、`type` 是内建命令，没有对应的可执行文件；找不到可执行文件时这里改用 `cmd /c` 执行，整条命令作为一个参数传过去，中文路径才不会变成 GBK 字节。
- **打印路径用正斜杠**：Windows 的路径分隔符是反斜杠，这里统一按 GNU 的样子输出正斜杠。
- **什么都不匹配时返回退出码 1**（GNU 返回 0），遵循本项目「无结果返回 1」的约定；`-delete` 这类只做动作不打印的用法按「命中了就算有结果」算，返回 0。
- **操作数不存在时报错并返回退出码 2**（GNU 返回 1），沿用本项目「用法或运行错误返回 2」的约定。
- **`-printf` 只支持 `%T@` 不支持 `%T`**：GNU findutils 4.10 的 MSYS 构建遇到单独的 `%T` 会直接报 `memory exhausted` 崩掉，纪元秒数要用 `%T@`。

## tree 能力清单

| 选项 | 含义 | 示例命令 |
| --- | --- | --- |
| （无） | 以树形列出当前目录 | `python main.py tree` |
| （操作数） | 要列出的目录，可给多个 | `python main.py tree w2l` |
| `-a` | 显示隐藏文件（名字以 . 开头） | `python main.py tree -a w2l` |
| `-d` | 只列目录 | `python main.py tree -d w2l` |
| `-f` | 打印完整路径 | `python main.py tree -f w2l` |
| `-F` | 给名字追加类型标记（`/` `*` `@`） | `python main.py tree -F w2l/commands` |
| `-i` | 不画缩进线 | `python main.py tree -i w2l` |
| `-l` | 跟随指向目录的符号链接 | `python main.py tree -l w2l` |
| `-L N` | 根目录往下最多显示 N 层 | `python main.py tree -L 1 w2l` |
| `-I PATTERN` | 不列匹配通配符的条目，可重复 | `python main.py tree -I '__pycache__' w2l` |
| `-P PATTERN` | 只列匹配通配符的文件，可重复 | `python main.py tree -P '*.py' w2l` |
| `--ignore-case` | 通配符匹配忽略大小写 | `python main.py tree -I '*.PY' --ignore-case w2l` |
| `--dirsfirst` | 目录排在文件前面 | `python main.py tree --dirsfirst w2l` |
| `--noreport` | 不打末尾的统计行 | `python main.py tree --noreport w2l` |
| `--charset=ascii` | 用 ASCII 画线字符（默认 utf8） | `python main.py tree --charset=ascii w2l` |
| `-p` | 打印权限位 | `python main.py tree -p w2l` |
| `-s` | 打印文件大小（字节） | `python main.py tree -s w2l/commands` |
| `-h` | 以 K/M/G 显示大小（隐含 `-s`） | `python main.py tree -h w2l/commands` |
| `-D` | 打印最后修改时间 | `python main.py tree -D w2l` |
| `-t` | 按修改时间排序，旧的在前 | `python main.py tree -t w2l` |
| `-r` | 反向输出排序结果 | `python main.py tree -r w2l` |
| `-U` | 不排序，按目录顺序输出 | `python main.py tree -U w2l` |
| `-x` | 不跨越文件系统 | `python main.py tree -x w2l` |

行为细节对齐 GNU tree 2.3.x：

- **根目录单独一行**：第一行是操作数原样（`tree w2l` 的第一行就是 `w2l`），下面才是各层条目。
- **连接符**：同一层里非最后一个条目用「├── 」，最后一个用「└── 」；祖先层后面还有兄弟时才画竖线，否则留空。
- **隐藏文件默认不列**：名字以 . 开头的要 `-a` 才列；`.` 与 `..` 永远不列（这一点与 `ls -a` 不同）。
- **默认按名字排序**：目录与文件混在一起排，`--dirsfirst` 才把目录提到前面。
- **`-t` 是旧的在前**：与 `ls -t`（新的在前）相反，这是 GNU tree 的口径。
- **`-r` 反向的是整个排序结果**：目录连同它的子树一起换到后面。
- **`-L N` 的层数从根目录往下数**：`tree -L 1` 只列根目录的直接子项，且不展开子目录。
- **`-I` 命中目录时整个目录连内容一起去掉**；`-P` 只筛文件，目录照旧列出，某个目录命中 `-P` 时它下面的内容全部列出。
- **通配符**：`*` 不跨 `/`，`**` 跨 `/`，`?` 匹配任意一个字符，`[...]` 是字符类（`^` 取反），`|` 分隔多个候选；模式里也可以带路径。
- **末尾统计行**：先空一行，再打 `N directories, M files`（数目为 1 时用单数）；`-d` 只打目录数。
- **根目录为空时不计入目录数**：空目录的统计行是 `0 directories, 0 files`。
- **多个操作数**：各自成树，末尾只有一行合计统计。

Windows 环境下的差异（都是本项目的取舍，不是实现取巧）：

- **画线字符默认 UTF-8**：GNU 在 C 区域设置下默认用 ASCII（`|--` 和 `` `-- ``），本项目输出统一 UTF-8，所以默认用「├── 」；要 ASCII 用 `--charset=ascii`。
- **UTF-8 竖线后面跟的是不换行空格**：与 GNU 的字节输出一致，复制到别处可能对不齐。
- **目录的大小按 0 算**：Windows 的目录 `st_size` 不稳定（空目录 0、条目一多就 4096），不统一的话同一条命令的结果会随目录内容变化。
- **权限位取自 Windows 合成出来的 `st_mode`**：目录是 `drwxrwxrwx`、普通文件是 `-rw-rw-rw-`，不等价于 POSIX 权限。
- **没有属主/属组列**：Windows 没有 POSIX 的属主/属组语义。
- **操作数是文件时报错**：GNU 会打出 `名字  [error opening dir]` 再照常统计，本实现直接报「不是目录」并返回退出码 2。
- **排序按码位序**：GNU 用 `strcoll`（区域设置相关，UTF-8 区域设置下大小写不敏感），本实现按码位序排，与本项目的 `ls` 一致。
- **`-x` 实际是不跨盘符**：Windows 的 `st_dev` 是卷标识，实测 C 盘与 E 盘的值不同，所以 `-x` 能挡住跨盘的子目录。
- **符号链接没法完整验证**：Windows 上创建符号链接要管理员权限（本机实测报 WinError 1314），所以 `-l` 的行为没法在本机验证。
- **出错返回退出码 2**（GNU tree 也是 2），沿用本项目「用法或运行错误返回 2」的约定。

## du 能力清单

| 选项 | 含义 | 示例命令 |
| --- | --- | --- |
| （无） | 统计当前目录的占用 | `python main.py du` |
| （操作数） | 要统计的路径，可给多个 | `python main.py du w2l tests` |
| `-a` | 连普通文件一起列出 | `python main.py du -a w2l` |
| `-c` | 末尾多打一行总计（`total`） | `python main.py du -c w2l` |
| `-s` | 每个操作数只打一行总数 | `python main.py du -s w2l` |
| `-d N` | 最多打印到第 N 层（操作数本身是第 0 层） | `python main.py du -d 1 w2l` |
| `-h` | 以 K/M/G 显示大小（1024 进制） | `python main.py du -sh w2l` |
| `--si` | 同 `-h`，但用 1000 进制（单位是小写 `k`） | `python main.py du --si w2l` |
| `-b` | 以字节为单位显示 | `python main.py du -sb w2l` |
| `-k` | 以 1K 为单位显示（默认） | `python main.py du -sk w2l` |
| `-m` | 以 1M 为单位显示 | `python main.py du -sm w2l` |
| `-B SIZE` | 以指定块大小为单位显示 | `python main.py du -B 100 w2l` |
| `-t SIZE` | 小于阈值的条目不显示；给负数则只显示不大于它的条目 | `python main.py du -t 1M w2l` |
| `-x` | 不跨越文件系统 | `python main.py du -x w2l` |
| `-S` | 目录大小不含子目录 | `python main.py du -S w2l` |
| `-l` | 硬链接的文件重复计入 | `python main.py du -l w2l` |
| `-L` / `-H` / `-P` | 符号链接的处理方式（见下方说明） | `python main.py du -L w2l` |
| `--time` | 多打一列最后修改时间 | `python main.py du --time w2l` |
| `-0` | 用 NUL 而不是换行分隔输出 | `python main.py du -0 w2l` |
| `--apparent-size` | 按文件字节数统计（本实现默认口径，写上也不改变行为） | `python main.py du --apparent-size w2l` |

行为细节对齐 GNU coreutils 8.32 的 du（全部经 Git Bash 的 `/usr/bin/du` 实跑对照，82 组用例输出逐条一致）：

- **输出结构**：每行是「大小<TAB>路径」，目录排在它自己的内容后面（后序遍历）。
- **统计口径是表观大小**：文件按字节数算，目录自身按 0 算，等价于 GNU 的 `--apparent-size`。
- **默认块大小 1K**：显示时把字节数向上取整到块；`-b` 按字节、`-k`/`-m`/`-B` 自定。
- **`-a` 连文件一起列**，`-s` 每个操作数只给一行总数，`-c` 在所有操作数之后追加一行 `total`。
- **`-d N` 只限制打印**：统计照样算到底，所以 `-d 1` 里 `w2l/commands` 显示的仍是它自己的总数。
- **`-t` 的阈值跟字节数比**，不是跟块数比：`-t 1K` 会留下块数 1、字节数 10 的小文件（GNU 实测如此）。
- **负阈值只留不大于它的条目**：`-t -1K` 只显示 1K 以内的条目。
- **`-h` 的尾数向上取整到一位小数**，取整后达到 10 就改成整数：`10239` 字节是 `10K` 而不是 `9.9K`；`--si` 用 1000 进制且单位是小写 `k`。
- **`-h` 与 `--si` 谁靠后听谁的**：GNU 里这两个选项都设置「人类可读」，命令行上更靠后的那个决定进制。
- **`-S` 让目录大小不含子目录**：目录只算自己这一层的文件。
- **同一个文件只算一次**：多个操作数覆盖同一棵树时，后来的那份既不重复统计也不输出；`-l` 打开后每次都算。
- **`--time` 给目录的是子树里最新的修改时间**（含目录自身的 mtime），不是目录自己的 mtime。
- **`-s` 与 `-d N` 冲突**：`-s` 等于 `--max-depth=0`，跟 `-d 1` 以上矛盾，本实现按用法错误处理。

Windows 环境下的差异（都是本项目的取舍，不是实现取巧）：

- **默认报的是文件字节数，不是磁盘占用**：GNU 默认报的是「文件占了几个块」（按文件系统块大小向上取整），Windows 的 Python 拿不到这个数——`os.stat_result` 没有 `st_blocks`，MSYS 那个 `st_blocks` 是 MSYS 模拟层的产物、跟 NTFS 的真实分配对不上。所以本实现默认就按文件字节数统计，等价于 GNU 的 `--apparent-size`；要精确字节数用 `-b`。
- **目录的大小按 0 算**：与本项目的 `find`、`tree` 一致。
- **同层条目按名字排序**：GNU 用的是目录原始顺序（NTFS 上是哈希序，基本随机），本实现按名字排，输出才稳定。
- **退出码**：操作数不存在报「用法或运行错误」返回 2（GNU 返回 1）；所有条目都被 `-t` 滤掉时按本项目「无结果返回 1」的约定返回 1（GNU 返回 0）。
- **`-L` / `-H` / `-P` 没法完整验证**：Windows 上创建符号链接要管理员权限（`os.symlink` 报 WinError 1314），所以符号链接相关的行为在本机没法验证。
- **`-x` 实际是不跨盘符**：Windows 的 `st_dev` 是卷标识，实测 C 盘与 E 盘的值不同，所以 `-x` 能挡住跨盘的子目录。

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
│       ├── tail.py          # tail 实现
│       ├── wc.py            # wc 实现
│       ├── find.py          # find 实现
│       ├── tree.py          # tree 实现
│       └── du.py            # du 实现
├── tests/
│   ├── conftest.py
│   ├── test_grep.py
│   ├── test_ls.py
│   ├── test_cat.py
│   ├── test_head.py
│   ├── test_tail.py
│   ├── test_wc.py
│   ├── test_find.py
│   ├── test_tree.py
│   ├── test_du.py
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

`ls`（已完成）、`cat`（已完成）、`head`（已完成）、`tail`（已完成）、`wc`（已完成）、`find`（已完成）、`tree`（已完成）、`du`（已完成）、`cp`、`mv`、`rm`、`chmod`、`sed`（行内替换）、`awk-lite`（字段投影）。先做「Windows 用户最常抱怨缺失」的那一批。

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
