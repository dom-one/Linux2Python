# w2l/commands/tree.py — 树形输出与画线规则

`w2l/commands/tree.py` 有 575 行，是 `w2l/commands/` 下中等体量的指令实现。表面上的活儿只是「把目录画成一棵树」，真正难的是三件事：画线字符怎么拼、目录项按什么序排、通配符怎么筛。

这个文件还有一层背景得先说清楚：**本机没有 GNU tree**。Git Bash 里 `tree` 不是一个可执行命令（只有 Windows 自带的 `C:\Windows\System32\tree.com`，那是另一个工具，输出格式完全不同）。所以 find.py 那一轮做的「61 个场景与 GNU 逐条对拍」在这里做不到。

`tests/test_tree.py` 的文件头把这件事写明了：

> 语义基线来自 GNU tree 2.3.x 上游源码（tree.c / list.c / unix.c / color.c）：本机没有 GNU tree 可做差分对照，所以断言按源码里的规则写死

所以本篇的结论分两类：**「本实现实际输出什么」**全部实跑，预期输出由脚本真跑录入、不手抄；**「与 GNU 差在哪」**拿不到字节级对照就不下断言。

另外，这一轮实测查出**三处本实现与项目自己的文档对不上**（README 与源码注释都写了另一种行为），列在最后一节。这三处的证据是「文档内部自相矛盾」，不依赖 GNU tree。

## 为什么这么创建

### 决定一：语义基线抄上游源码，不抄本机二进制

没有 GNU tree 可对照，唯一的办法是把上游 GNU tree 2.3.x 的源码规则抄下来，写进模块文档字符串和代码注释。tree.py 的模块文档字符串（第 1~19 行）把对齐的条款列成了清单：

- 输出结构：根目录单独一行，下面按深度缩进画树，连接符是「├── 」和「└── 」
- 默认不列隐藏文件（名字以 . 开头），`-a` 才列；`.` 与 `..` 永远不列
- 默认按名字排序，目录与文件混在一起排；`--dirsfirst` 才把目录提到前面
- `-t` 按修改时间排序，旧的在前（与 `ls -t` 相反）
- 末尾统计行：先空一行，再打 "N directories, M files"（数目为 1 时用单数）
- `-L N` 限制根目录往下最多 N 层；`-I`/`-P` 用通配符筛选
- `-F` 给名字追加类型标记，`-s`/`-h` 打大小，`-p` 打权限，`-D` 打修改时间

这七条就是本实现的验收标准，下面每一条都会实跑一遍。

### 决定二：画线字符表做成可切换的 charset，竖线后面跟的是 NBSP

`_CHARSETS`（第 46~59 行）存了两套画线字符：

```python
_CHARSETS = {
    "utf8": {
        "vert": "│\u00a0\u00a0",
        "vert_left": "├──",
        "corner": "└──",
        "space": "   ",
    },
    "ascii": {
        "vert": "|  ",
        "vert_left": "|--",
        "corner": "`--",
        "space": "   ",
    },
}
```

两处细节：

1. **UTF-8 版的竖线是 `│` 加两个 U+00A0（不换行空格），不是两个普通空格。** 注释写明「与 GNU 的字节输出一致」。代价是 NBSP 在多数编辑器眼里不是空白，复制到别处会错位；`grep -x` 或 `$(...)` 做整行比较时也会因为它对不上。
2. **竖线后面那个普通空格由 `_build_prefix` 统一补**，所以表里存的 `vert`（竖线本体）与 `space`（空缩进）都不带它，拼接时每个片段后面加一个空格。ASCII 版因此是 `|   `（竖线 + 三个空格）。

`_CHARSET_ALIASES`（第 61~66 行）把 `utf-8` 也认成 `utf8`。

### 决定三：缩进用「祖先层还有没有兄弟」的布尔列表表示

画树最容易写歪的地方是缩进。要画对一个条目的前缀，得知道它的每一层祖先「后面还有没有兄弟」——有兄弟就画竖线，没有就画空白。

tree.py 用一个 `list[bool]` 表达这件事：`_list_dir` 的 `ancestors` 参数（第 198 行），每个元素表示那一层后面还有没有兄弟。`_build_prefix`（第 247~260 行）负责拼：

```python
def _build_prefix(ancestors, is_last, args, charset):
    if args.no_indent:
        return ""
    glyphs = _CHARSETS[charset]
    parts = []
    for has_more in ancestors:
        parts.append(glyphs["vert"] if has_more else glyphs["space"])
    parts.append(glyphs["corner"] if is_last else glyphs["vert_left"])
    return "".join(part + " " for part in parts)
```

进子目录时传的是 `ancestors + [not is_last]`（第 231 行）：当前条目是最后一个就传 `False`（这一层后面没兄弟了，画竖线就错了），不是最后一个就传 `True`。

这个设计的好处是**状态只有一位**，不用记住「路径深度」「缩进宽度」这类容易算错的东西。

### 决定四：统计行的单复数，以及「根目录为空不计数」

`_format_report`（第 345~354 行）照 GNU 的单复数写法拼统计行：`1 directory` / `2 directories`、`1 file` / `2 files`。`-d` 打开时只打目录数。

有个容易忽略的不对称：**根目录为空时，它自己不计入目录数**。`_emit_tree` 第 185~187 行：

```python
entries = _read_entries(root, args, label, pattern_active, state)
if not entries:
    # GNU：根目录里一个条目都没有时，它本身也不计入目录数
    return
state.dirs += 1
```

而子目录不一样——`_list_dir` 第 214 行是**先 `state.dirs += 1` 再判断要不要展开**，所以一个空的子目录照样计入目录数。根目录和子目录在这条上口径不同。

### 决定五：通配符自己编译成正则，不用 fnmatch

`-I` / `-P` 的通配符是 GNU 的 patmatch 语义，跟 shell 的 glob 也不是一回事：

- `*` 不跨 `/`
- `**` 跨 `/`
- `?` 匹配任意一个字符
- `[...]` 是字符类，`^` 或 `!` 取反
- `|` 分隔多个候选，任一命中即可
- 模式末尾带 `/` 表示「只匹配目录」

`_compile_pattern`（第 504~538 行）把这些规则翻译成正则。**为什么不用 `fnmatch`？** 因为 `fnmatch.fnmatch` 会先过 `os.path.normcase` 把大小写抹平（Windows 上 `fnmatch("B.TXT", "*.txt")` 是 True），而 tree 默认区分大小写，只有 `--ignore-case` 才忽略。这个坑 find.py 那一轮已经踩过一次（`-name` 必须用 `fnmatchcase`）。

候选集也比 glob 宽：`_matches_patterns`（第 467~485 行）对每个条目同时拿**名字、完整路径、路径的任意后缀**去比：

```python
candidates = [name, path]
parts = path.split("/")
for index in range(1, len(parts)):
    candidates.append("/".join(parts[index:]))
```

所以 `-I 'sub/deep.txt'` 能命中路径后缀，`-I 'sub/**'` 能跨斜杠。

### 决定六：`-P` 用一个 `pattern_active` 标志控制要不要继续筛

`-P`（只列匹配的文件）的规则是：目录照旧列出（不然没法往下走），文件要匹配模式才列。**但如果某个目录自己命中了模式，它下面的内容就全部列出**，不再筛。

实现用 `pattern_active` 这个布尔量表达「当前这一层还要不要按模式筛文件」：

- `_emit_tree` 第 183 行：根目录命中 `-P` 就整棵列出（`pattern_active` 为 False）
- `_list_dir` 第 222~224 行：进入的目录命中 `-P`，它下面的内容全部列出

这个标志的**计算时机**有个坑，实测能看出来，见最后一节第 2 条。

### 决定七：权限列复用 w2l/perms.py

2026-11-19 的 chmod 指令落地时新建了 `w2l/perms.py`，把 Windows 合成出来的 `st_mode` 折算成 MSYS 口径（可写文件 0644、只读 0444、目录 0755、可执行 0755、符号链接 0777）。tree.py 的权限列现在直接调它（第 34 行 import、第 293~295 行 `_format_perms`），跟 `ls -l` 是同一套口径。

**副作用：README 第 429 行已经过期。** 那一行还写着「目录是 `drwxrwxrwx`、普通文件是 `-rw-rw-rw-`」，那是 `w2l/perms.py` 落地之前的旧口径，实际输出是 `drwxr-xr-x` 和 `-rw-r--r--`。

类型标记 `-F` 判「可执行」用的也是同一套口径（`_type_marker` 第 340 行 `canonical_mode(mode) & 0o111`）。

### 决定八：目录的大小一律按 0 算

`_format_size` 第 301~303 行：

```python
if stat.S_ISDIR(st.st_mode):
    # Windows 的目录 st_size 会在 0 与 4096 之间跳，统一按 0 算
    size = 0
```

Windows 的目录 `st_size` 不稳定（空目录 0、条目一多变 4096），不统一的话同一条命令的结果会随目录内容变化。

`-h` 的换算是 IEC 进制（`_SIZE_UNITS = "BKMGTPEZY"`，1024 进位），见第 306~316 行。

## 这个文件是做什么

它是 `w2l/commands/` 下的一个指令实现，575 行，职责边界很清楚：**把一棵目录树画成带画线字符的文本树，末尾附一行统计**。

### 数据流

```
tree()                       第 135~169 行   入口：校验选项、逐个处理操作数、打统计行
 └ _emit_tree()              第 177~189 行   打根目录那一行，读根目录的内容
    └ _list_dir()            第 192~235 行   递归：画每个条目，必要时往下走
       ├ _read_entries()     第 362~420 行   读目录 + 过滤 + 排序
       │  └ _sort_entries() 第 423~437 行   名字 / 时间 / 目录优先 / 反向
       ├ _build_prefix()     第 247~260 行   拼缩进前缀
       ├ _format_entry()     第 263~277 行   拼元信息 + 名字
       │  ├ _format_meta()   第 280~290 行   权限 / 大小 / 时间
       │  ├ _format_perms()  第 293~295 行   调 w2l/perms.py
       │  ├ _format_size()   第 298~316 行   字节数 / IEC 单位
       │  ├ _format_time()   第 319~326 行   半年内打时刻，更早打年份
       │  └ _type_marker()   第 329~342 行   -F 的 / * @ |
       └ _can_descend()      第 238~244 行   -L 层数限制、符号链接不跟随
```

通配符是独立的一支：

```
_matches_patterns()    第 467~485 行   名字 / 路径 / 路径后缀，逐个候选比
 └ _match_pattern()    第 488~501 行   '|' 分候选、末尾 '/' 表示只匹配目录
    └ _compile_pattern() 第 504~538 行 通配符 → 正则
```

### 选项清单

| 选项 | 作用 | 备注 |
|---|---|---|
| （无） | 列当前目录 | 操作数默认为 `.`（第 143 行） |
| （操作数） | 要列的目录，可给多个 | 各自成树，末尾只打一行合计统计 |
| `-a` | 显示隐藏文件 | `.` 与 `..` 永远不列 |
| `-d` | 只列目录 | 统计行也只打目录数 |
| `-f` | 打印完整路径 | 路径 = 操作数 + 逐级名字 |
| `-F` | 追加类型标记 | 目录 `/`、可执行 `*`、链接 `@`、FIFO `\|`、socket `=` |
| `-i` | 不画缩进线 | 只打名字 |
| `-l` | 跟随指向目录的符号链接 | Windows 上建不了符号链接，见最后一节第 3 条 |
| `-L N` | 最多往下显示几层 | 必须大于 0，否则 UsageError |
| `-I PATTERN` | 不列匹配的条目 | 可重复 |
| `-P PATTERN` | 只列匹配的文件 | 可重复 |
| `--ignore-case` | 通配符匹配忽略大小写 | 默认区分 |
| `--dirsfirst` | 目录排在文件前面 | |
| `--noreport` | 不打末尾统计行 | |
| `--charset X` | 画线字符集 | `utf8`（默认）/ `ascii` |
| `-p` | 打印权限位 | 与 `ls -l` 同一套口径 |
| `-s` | 打印字节数 | 列宽 12 |
| `-h` | 以 K/M/G 显示大小 | 隐含 `-s` |
| `-D` | 打印最后修改时间 | 半年内打时刻，更早打年份 |
| `-t` | 按修改时间排序 | 旧的在前 |
| `-r` | 反向输出排序结果 | |
| `-U` | 不排序 | 按目录原始顺序 |
| `-x` | 不跨越文件系统 | 见最后一节第 1 条 |

### 退出码

| 码 | 什么时候 |
|---|---|
| 0 | 正常 |
| 2 | 用法错误（`-L 0`、字符集不认识）、路径打不开、操作数不是目录 |

出错时统计行照样打，只是数不对。

## 有什么用

- **看项目结构**。`tree` 是这个项目里唯一一个「一次给出整个目录结构」的命令。`ls` 只列一层，`find` 给的是路径列表不带层次，`tree` 给的是带画线的层次结构——想知道「哪些目录里塞了同一类文件」「这个文件到底在哪一层」的时候用它。
- **照抄排版逻辑**。它是 `w2l/commands/` 里选项最多的指令之一（21 个选项，不含 `--help`），也是画线/缩进这类纯排版逻辑写得最完整的一个：`_build_prefix` 的布尔列表法可以直接搬到别的树形输出上。
- **排查已知问题**。这一轮实测查出三处实现与项目文档不一致，全在最后一节，都有可复现的命令。

## 怎么用（过程教程）

### 第 1 步：准备演示夹具

后面的例子全部用固定夹具，不用项目源码。理由是源码会变：拿 `w2l/registry.py` 当例子，源码一改教程里写死的预期输出就全过期了。

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t800_make_tree_demo.py
```

预期输出：

```
已生成 AI/数据/tree_demo/（8 个文件）与 AI/数据/tree_deep/（4 个文件）
```

夹具清单（`AI/数据/tree_demo/`）：

| 路径 | 内容 | 字节 | mtime |
|---|---|---|---|
| `.hidden` | `hidden\n` | 7 | 2020-09-13 |
| `B.txt` | `upper\n` | 6 | 2022-06-24 |
| `a.txt` | `hello\n` | 6 | 2024-01-01 |
| `big.bin` | 2048 个 `z` | 2048 | 2025-01-01 |
| `notes.md` | `# note\n` | 7 | 2026-11-18 10:30 |
| `empty_dir/` | 空目录 | — | 2026-11-19 01:00 |
| `sub/code.py` | `print(1)\n` | 9 | 2026-11-17 09:15 |
| `sub/deep.txt` | `deep\n` | 5 | 2026-11-19 00:05 |
| `tools/run.txt` | `run\n` | 4 | 2026-11-18 08:00 |

另有一个三层夹具 `AI/数据/tree_deep/`，专门用来看 `-P` 命中目录时的展开范围：

```
plain.txt
hit/direct.txt
hit/mid/leaf.txt
hit/mid/leaf2.txt
```

两个夹具都落在 `AI/数据/` 下，这个目录在 `.gitignore` 里，不进仓库。**mtime 是钉死的**，所以下面所有带时间的预期输出都稳定。

### 第 2 步：先看清这个文件有多大

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat w2l/commands/tree.py | wc -l
```

预期输出：

```
575
```

### 第 3 步：默认输出长什么样

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree AI/数据/tree_demo
```

预期输出：

```
AI/数据/tree_demo
├── B.txt
├── a.txt
├── big.bin
├── empty_dir
├── notes.md
├── sub
│   ├── code.py
│   └── deep.txt
└── tools
    └── run.txt

4 directories, 7 files
```

四件事要记住：

1. **根目录单独一行**，打的是操作数原样（`AI/数据/tree_demo`）。
2. **默认按名字排序，目录与文件混在一起排**。`B.txt` 排在 `a.txt` 前面，因为按的是码位序（`B` 是 0x42，`a` 是 0x61），不是 Windows 的大小写不敏感序。
3. **统计行前面有一个空行**。
4. **目录与文件的数目分开算**：`4 directories, 7 files` 里，4 个目录是根目录加 `empty_dir`、`sub`、`tools`，7 个文件是 `B.txt`、`a.txt`、`big.bin`、`notes.md` 和三个子目录里的文件。

### 第 4 步：看懂画线规则

同一个目录，换成 ASCII 画线字符：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree --charset=ascii AI/数据/tree_demo
```

预期输出：

```
AI/数据/tree_demo
|-- B.txt
|-- a.txt
|-- big.bin
|-- empty_dir
|-- notes.md
|-- sub
|   |-- code.py
|   `-- deep.txt
`-- tools
    `-- run.txt

4 directories, 7 files
```

对照着看，两套字符的**结构完全一样**（`vert` 竖线本体、`vert_left` 非最后一个兄弟、`corner` 最后一个兄弟、`space` 空缩进），只是字形不同。

再看 UTF-8 版里竖线那三个字节是什么。把上面默认输出的两行 repr 出来：

```text
'├── sub'
'│\xa0\xa0 ├── code.py'
```

`│` 后面跟的是**两个不换行空格（U+00A0）再加一个普通空格**，不是三个普通空格。所以：

- 复制到记事本、聊天软件里会错位（那里按普通空格排版）
- `grep -x` 或 `$(...)` 做整行比较时对不上
- 要按字节看，用 `python main.py tree AI/数据/tree_demo | od -c`

### 第 5 步：`-a` 与 `-d`

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -a AI/数据/tree_demo
```

预期输出：

```
AI/数据/tree_demo
├── .hidden
├── B.txt
├── a.txt
├── big.bin
├── empty_dir
├── notes.md
├── sub
│   ├── code.py
│   └── deep.txt
└── tools
    └── run.txt

4 directories, 8 files
```

`-a` 把 `.hidden` 也列出来。注意 `.` 与 `..` **永远不列**，这一点跟 `ls -a` 不同。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -d AI/数据/tree_demo
```

预期输出：

```
AI/数据/tree_demo
├── empty_dir
├── sub
└── tools

4 directories
```

`-d` 只列目录，统计行也跟着只打目录数（`4 directories`，没有 files）。

### 第 6 步：`-L N` 的层数从根目录往下数

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -L 1 AI/数据/tree_demo
```

预期输出：

```
AI/数据/tree_demo
├── B.txt
├── a.txt
├── big.bin
├── empty_dir
├── notes.md
├── sub
└── tools

4 directories, 4 files
```

`-L 1` 只列根目录的直接子项，`sub` 和 `tools` 出现了但不展开。注意统计行变成 `4 directories, 4 files`——目录还是 4 个（没展开也算），文件少了展开出来的那三个。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -L 2 AI/数据/tree_demo
```

预期输出：

```
AI/数据/tree_demo
├── B.txt
├── a.txt
├── big.bin
├── empty_dir
├── notes.md
├── sub
│   ├── code.py
│   └── deep.txt
└── tools
    └── run.txt

4 directories, 7 files
```

`-L 2` 展开一层，`sub` 的子项出来了，`tools` 的子项也出来了。

### 第 7 步：五种排序口径

**默认按名字**（第 3 步已看）。

**`--dirsfirst` 把目录提到前面**：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree --dirsfirst AI/数据/tree_demo
```

预期输出：

```
AI/数据/tree_demo
├── empty_dir
├── sub
│   ├── code.py
│   └── deep.txt
├── tools
│   └── run.txt
├── B.txt
├── a.txt
├── big.bin
└── notes.md

4 directories, 7 files
```

目录之间、文件之间各自的相对顺序没变，只是整块搬到了前面。

**`-t` 按修改时间排，旧的在前**：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -t AI/数据/tree_demo
```

预期输出：

```
AI/数据/tree_demo
├── B.txt
├── a.txt
├── big.bin
├── notes.md
├── empty_dir
├── sub
│   ├── code.py
│   └── deep.txt
└── tools
    └── run.txt

4 directories, 7 files
```

夹具里 `B.txt`（2022）→ `a.txt`（2024）→ `big.bin`（2025）→ `notes.md`（2026-11-18）→ 三个目录（2026-11-19 01:00，同一时间戳，按名字兜底排）。**这与 `ls -t` 相反**，`ls -t` 是新的在前。

**`-r` 把排序结果整体反向**：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -r AI/数据/tree_demo
```

预期输出：

```
AI/数据/tree_demo
├── tools
│   └── run.txt
├── sub
│   ├── deep.txt
│   └── code.py
├── notes.md
├── empty_dir
├── big.bin
├── a.txt
└── B.txt

4 directories, 7 files
```

每一层各自反向，目录连同它的子树一起换到后面。注意 `sub` 里面的 `code.py` 与 `deep.txt` 也反了。

**`-U` 完全不排序**，按文件系统的目录原始顺序输出：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -U AI/数据/tree_demo
```

预期输出：

```
AI/数据/tree_demo
├── a.txt
├── B.txt
├── big.bin
├── empty_dir
├── notes.md
├── sub
│   ├── code.py
│   └── deep.txt
└── tools
    └── run.txt

4 directories, 7 files
```

跟默认排序不一样（`a.txt` 跑到了 `B.txt` 前面），这就是 NTFS 的目录项原始顺序。

### 第 8 步：元信息列

**`-s` 打字节数**：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -s AI/数据/tree_demo
```

预期输出：

```
0AI/数据/tree_demo
├──            6B.txt
├──            6a.txt
├──         2048big.bin
├──            0empty_dir
├──            7notes.md
├──            0sub
│   ├──            9code.py
│   └──            5deep.txt
└──            0tools
    └──            4run.txt

4 directories, 7 files
```

**`-h` 打带单位的大小**（隐含 `-s`）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -h AI/数据/tree_demo
```

预期输出：

```
0AI/数据/tree_demo
├──     6B.txt
├──     6a.txt
├──  2.0Kbig.bin
├──     0empty_dir
├──     7notes.md
├──     0sub
│   ├──     9code.py
│   └──     5deep.txt
└──     0tools
    └──     4run.txt

4 directories, 7 files
```

2048 字节 = 2.0K（IEC 进制，1024 进位）。目录一律显示 0，这是「决定八」说的那个统一口径。

**`-p` 打权限位**：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -p AI/数据/tree_demo
```

预期输出：

```
drwxr-xr-xAI/数据/tree_demo
├──  -rw-r--r--B.txt
├──  -rw-r--r--a.txt
├──  -rw-r--r--big.bin
├──  drwxr-xr-xempty_dir
├──  -rw-r--r--notes.md
├──  drwxr-xr-xsub
│   ├──  -rw-r--r--code.py
│   └──  -rw-r--r--deep.txt
└──  drwxr-xr-xtools
    └──  -rw-r--r--run.txt

4 directories, 7 files
```

这是 `w2l/perms.py` 的 MSYS 口径：目录 `drwxr-xr-x`、普通文件 `-rw-r--r--`。

**`-D` 打最后修改时间**：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -D AI/数据/tree_demo
```

预期输出：

```
Nov 19 01:00AI/数据/tree_demo
├──  Jun 24  2022B.txt
├──  Jan  1  2024a.txt
├──  Jan  1  2025big.bin
├──  Nov 19 01:00empty_dir
├──  Nov 18 10:30notes.md
├──  Nov 19 01:00sub
│   ├──  Nov 17 09:15code.py
│   └──  Nov 19 00:05deep.txt
└──  Nov 19 01:00tools
    └──  Nov 18 08:00run.txt

4 directories, 7 files
```

两种格式，半年以内打时刻、更早打年份：

- `Nov 18 10:30` —— 时刻（`%b %d %H:%M`）
- `Jun 24  2022` —— 年份（`%b %d  %Y`，日期与年份之间是**两个**空格）

半年的门槛是 `_SIX_MONTHS = 6 * 31 * 24 * 60 * 60`（第 39 行），即 186 天。**三个元信息列可以叠加**，顺序固定是权限、大小、时间（`_format_meta` 第 280~290 行）。

⚠️ 这几列的数字与名字之间**没有分隔空格**（`           0AI/数据/tree_demo`），数字直接粘在名字上。这是本实现的样子，见最后一节。

### 第 9 步：`-F` 类型标记、`-i` 与 `-f`

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -F AI/数据/tree_demo
```

预期输出：

```
AI/数据/tree_demo
├── B.txt
├── a.txt
├── big.bin
├── empty_dir/
├── notes.md
├── sub/
│   ├── code.py
│   └── deep.txt
└── tools/
    └── run.txt

4 directories, 7 files
```

目录名后面追加 `/`。可执行文件追加 `*`，符号链接追加 `@`（Windows 上建不了符号链接，这两种标记本机没验到）。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -i AI/数据/tree_demo
```

预期输出：

```
AI/数据/tree_demo
B.txt
a.txt
big.bin
empty_dir
notes.md
sub
code.py
deep.txt
tools
run.txt

4 directories, 7 files
```

`-i` 把缩进线整个去掉，只剩名字，**层次信息就没了**——它是给「我只想看一份文件清单」用的。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -f AI/数据/tree_demo
```

预期输出：

```
AI/数据/tree_demo
├── AI/数据/tree_demo/B.txt
├── AI/数据/tree_demo/a.txt
├── AI/数据/tree_demo/big.bin
├── AI/数据/tree_demo/empty_dir
├── AI/数据/tree_demo/notes.md
├── AI/数据/tree_demo/sub
│   ├── AI/数据/tree_demo/sub/code.py
│   └── AI/数据/tree_demo/sub/deep.txt
└── AI/数据/tree_demo/tools
    └── AI/数据/tree_demo/tools/run.txt

4 directories, 7 files
```

`-f` 给每个条目打完整路径。路径是「操作数 + 逐级名字」拼出来的，所以操作数是 `.` 时会打成 `./sub/code.py`。

### 第 10 步：通配符筛选

**`-I` 不列匹配的条目**：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -I '*.txt' AI/数据/tree_demo
```

预期输出：

```
AI/数据/tree_demo
├── big.bin
├── empty_dir
├── notes.md
├── sub
│   └── code.py
└── tools

4 directories, 3 files
```

`B.txt`、`a.txt`、`sub/deep.txt`、`tools/run.txt` 都没了。**`-I` 命中目录时整个目录连内容一起去掉**：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -I 'sub' AI/数据/tree_demo
```

预期输出：

```
AI/数据/tree_demo
├── B.txt
├── a.txt
├── big.bin
├── empty_dir
├── notes.md
└── tools
    └── run.txt

3 directories, 5 files
```

`sub` 整个没了（它下面的 `code.py`、`deep.txt` 也不列），目录数从 4 降到 3。

**`-P` 只列匹配的文件**：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -P '*.txt' AI/数据/tree_demo
```

预期输出：

```
AI/数据/tree_demo
├── B.txt
├── a.txt
├── empty_dir
├── sub
│   └── deep.txt
└── tools
    └── run.txt

4 directories, 4 files
```

`-P` 与 `-I` 的区别：`-I` 是「命中就整个去掉」，`-P` 是「只留命中的」。**目录在 `-P` 下照旧列出**（不然没法往下走），只有文件受筛选。所以 `empty_dir` 出现在输出里，`big.bin`、`notes.md` 没有。

通配符的其余几条规则实测如下（`-I` / `-P` 都认）：

| 模式 | 含义 | 实测 |
|---|---|---|
| `*.txt` | `*` 不跨 `/` | 只匹同级名字 |
| `**/deep.txt` | `**` 跨 `/` | 能匹到 `sub/deep.txt` |
| `?.txt` | `?` 匹配一个字符 | `B.txt`、`a.txt` 命中，`deep.txt` 不命中 |
| `[!a]*.txt` | `[]` 字符类，`!` 取反 | `a.txt` 被排除，`B.txt`、`deep.txt`、`run.txt` 命中 |
| `*.txt\|*.md` | `\|` 分隔候选 | 任一命中即可 |
| `sub/` | 末尾 `/` 表示只匹配目录 | 只对目录生效 |
| `sub/deep.txt` | 拿路径后缀去比 | 命中 `sub` 里的 `deep.txt` |

默认**区分大小写**，`--ignore-case` 才忽略。

上表这七条是 `AI/脚本/_t804_probe_tree_patterns.py` 逐条实跑出来的，想复现就跑那个脚本（它一次跑 12 个场景并把输出打全）。

### 第 11 步：`--noreport` 与空目录

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree --noreport AI/数据/tree_demo
```

预期输出：

```
AI/数据/tree_demo
├── B.txt
├── a.txt
├── big.bin
├── empty_dir
├── notes.md
├── sub
│   ├── code.py
│   └── deep.txt
└── tools
    └── run.txt
```

末尾的统计行没了。

空目录是个特例——**根目录自己没有条目时，它自己不计入目录数**：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree AI/数据/tree_demo/empty_dir
```

预期输出：

```
AI/数据/tree_demo/empty_dir

0 directories, 0 files
```

`0 directories, 0 files`。而空的**子**目录照样算一个目录（见「决定四」）。

### 第 12 步：出错时的退出码

**路径不存在**：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree nope
```

预期输出：

```
tree: 无法访问 'nope': 系统找不到指定的文件。

0 directories, 0 files
```

**操作数是文件而不是目录**：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree AI/数据/tree_demo/a.txt
```

预期输出：

```
tree: 'AI/数据/tree_demo/a.txt' 不是目录

0 directories, 0 files
```

**用法错误**（`-L 0`）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -L 0 AI/数据/tree_demo
```

预期输出：

```
错误: 选项 '-L' 的层数必须大于 0
```

**用法错误**（字符集不认识）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree --charset=gbk AI/数据/tree_demo
```

预期输出：

```
错误: 未知的字符集 'gbk'（可用：utf8、ascii）
```

四个场景的退出码都是 **2**。注意两点：

1. 用法错误（`-L 0`、`--charset=gbk`）由 `cli.py` 统一捕获 `UsageError` 并打印 `错误: ...`，**stdout 是空的**。
2. 路径打不开、操作数不是目录这两种是 tree 自己打的错误（`tree: ...`），**统计行照样会打**，只是数不对。

错误文案里的 `系统找不到指定的文件。` 是 Windows 的 `OSError.strerror`，在 Linux 上会是 `No such file or directory`。

### 第 13 步：跑相关测试

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest tests/test_tree.py 2>&1 | tail -1
```

预期输出（耗时每次不同，用 `<T>` 占位）：

```
34 passed in <T>s
```

`tests/test_tree.py` 里有 34 个用例，覆盖正常路径、选项组合、错误路径三块。注意命令末尾的 `| tail -1`：本项目的 `pyproject.toml` 里 `addopts = "-q"`，`pytest -q` 的输出被压成一行进度条，看不到用例数；`tail -1` 取的是最后那行汇总。

### 第 14 步：确认整体没坏

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest 2>&1 | tail -1
```

输出最后一行形如 `N passed in <T>s`。`N` 会随开发任务每落地一个新指令而变大，这里不写死——本篇只关心 tree 相关的用例全绿。

### 实测出的三处与项目文档不一致

这一轮实测查出三处**本实现与项目自己的文档对不上**的地方。证据是文档内部自相矛盾，不需要 GNU tree 来佐证。源码属开发任务范围，本轮按只读原则没动。

#### 1. `-x` 在 Windows 上把整棵树都过滤掉了

`-x` 的本意是「不跨越文件系统」。README 第 433 行写的是：

> **`-x` 实际是不跨盘符**：Windows 的 `st_dev` 是卷标识，实测 C 盘与 E 盘的值不同，所以 `-x` 能挡住跨盘的子目录。

但实际跑起来：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -x AI/数据/tree_demo
```

预期输出：

```
AI/数据/tree_demo

0 directories, 0 files
```

**整棵树是空的。** 不是「挡住了跨盘的子目录」，是所有条目都没了。

根因在 `w2l/commands/tree.py` 第 384 行与第 397 行：

```python
st = item.stat(follow_symlinks=False)     # 第 384 行
...
if args.one_file_system and state.root_dev is not None and st.st_dev != state.root_dev:
    continue                              # 第 397 行
```

`state.root_dev` 取的是根目录 `lstat()` 的 `st_dev`（第 164 行），那是**真的卷标识**；而 `item.stat()` 是 `os.scandir()` 出来的 `DirEntry.stat()`，**在 Windows 上 `st_dev` 恒为 0**。两个数永远对不上，于是每个条目都被 `continue` 掉。

实测同一个文件两条 API 的差别：

| 字段 | `DirEntry.stat()` | `os.stat(path)` |
|---|---|---|
| `st_dev` | **0** | 18303321406201763453（E 盘卷标识） |
| `st_ino` | **0** | 18858823439912295 |
| `st_size` | 6 | 6 |
| `st_mtime` | 1704067200.0 | 1704067200.0 |
| `st_mode` | 33206 | 33206 |

**这个坑项目里已经踩过并修好了**：`w2l/commands/du.py` 第 391~396 行明明白白写着注释

> 不能用 item.stat()：Windows 上它给的是目录枚举的缓存结果，st_dev 与 st_ino 全是 0，硬链接去重与 -x 都会失效

du.py 改用 `os.stat(item.path, follow_symlinks=follow)` 就好了。tree.py 没跟着改，所以 `-x` 在 tree 里是坏的。

（顺带：C 盘与 E 盘的 `st_dev` 确实不同，README 那句「实测 C 盘与 E 盘的值不同」本身没错，错的是 tree 用错了 API。）

#### 2. `-P` 命中目录时少展开一层

README 第 418 行写的是：

> `-I` 命中目录时整个目录连内容一起去掉；`-P` 只筛文件，目录照旧列出，**某个目录命中 `-P` 时它下面的内容全部列出**。

源码第 221 行的注释也这么写：

> 进入的目录本身命中 -P 时，它下面的内容全部列出（GNU 的做法）

但实测不是这样。拿三层夹具 `AI/数据/tree_deep/` 试（`hit/` 下面是 `hit/mid/`，`hit/mid/` 下面是两个叶子文件）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -P 'hit' AI/数据/tree_deep
```

预期输出：

```
AI/数据/tree_deep
└── hit
    └── mid
        ├── leaf.txt
        └── leaf2.txt

3 directories, 2 files
```

**`hit` 下面的 `direct.txt` 没列出来**（它不匹配 `hit`，被筛掉了），只有子目录 `mid` 列出来了，而 `mid` 下面的内容全在。

根因是 `_list_dir` 里的顺序（第 218~224 行）：

```python
children = _read_entries(entry.path, args, child_path, pattern_active, state)   # 用的是父层的 pattern_active
if not children:
    continue
child_active = pattern_active and not _matches_patterns(...)   # 读完 children 之后才算
```

`child_active` 是在**读完 children 之后**才算出来的，所以它只对**再下一层**生效。命中目录的**直接子文件**仍然按父层的 `pattern_active` 被筛掉了。

换个更明显的：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py tree -P 'mid' AI/数据/tree_deep
```

预期输出：

```
AI/数据/tree_deep
└── hit
    └── mid

3 directories, 0 files
```

`mid` 命中了模式，但它下面的 `leaf.txt`、`leaf2.txt` 一个都没列出来——`mid` 变成了一个空目录。

正确做法应该是先算出 `child_active`，再用它去读 children。

#### 3. 目录联接不被认成符号链接

tree.py 判断符号链接用的是 `stat.S_ISLNK(st.st_mode)`（第 154、387 行）。Windows 上真正的符号链接要管理员权限才能建（`os.symlink` 报 WinError 1314），但**目录联接（junction）不需要**。

实测（用 `cmd /c mklink /J 建联接`）：

| 检查项 | 结果 |
|---|---|
| `lstat()` 的模式 | `drwxrwxrwx`（是目录，不是链接） |
| `S_ISLNK` | False |
| `S_ISDIR` | True |
| `os.path.islink()` | False |
| `os.readlink()` | **能读到目标**（`\\?\E:\...\target`） |

也就是说：**Python 认不出目录联接是链接，但 `os.readlink()` 认得出。** tree.py 用 `S_ISLNK` 判断，所以联接被当成**普通目录**，无条件展开——`-l` 开关对它不起作用（`-l` 只在 `entry.is_link` 为真时才改变行为）。

两个后果：

1. **同样的内容被列两遍**。目录里同时有 `link_to_sub`（指向 `sub`）和 `sub` 时，两边各列一遍 `inside.txt`。
2. **自引用的联接会一路递归下去**。在目录里建一个指向它自己的联接，跑 `tree`：

```text
├── leaf.txt
└── loop
    ├── leaf.txt
    └── loop
        ├── leaf.txt
        └── loop
            ... 一路往下 ...
```

实测递归到 **64 层**才停——不是被代码里的深度限制挡住的，是 Windows 的路径长度上限挡住了，`os.scandir` 报「系统无法辨识文件名」，tree 打完错误信息、以退出码 2 结束。统计行会报成 `65 directories, 64 files`。

GNU tree 遇到符号链接默认是不展开的，所以这个行为与 GNU 的预期不一样。修法有两个方向：改用 `os.readlink` 试探（能认联接），或者加个「已经访问过的 (st_dev, st_ino) 集合」防环。

#### 另外：元信息列与名字之间没有分隔空格

`-s`、`-h`、`-p`、`-D` 的列宽是固定的（`-s` 是 12 个字符），但**列尾与名字之间没有空格**，数字直接粘在名字上：

```text
           0AI/数据/tree_demo
├──            6B.txt
```

```text
 drwxr-xr-xAI/数据/tree_demo
├──  -rw-r--r--B.txt
```

这一条没有跟项目文档冲突（README 没写列格式），但它是本实现实际的样子，抄预期输出的时候容易抄错。GNU tree 的输出列之间是有空格的，不过本机没有 GNU tree 可对照，这里只记录事实、不下断言。

### 常见疑问

**为什么 `tree -x` 什么都不输出？** 见最后一节第 1 条，是 `DirEntry.stat()` 的 `st_dev` 恒为 0 导致的。

**为什么 `-P 'xxx'` 命中的目录看起来是空的？** 见最后一节第 2 条，`child_active` 算晚了。

**统计行里的目录数为什么和我数的不一样？** 根目录为空时不计入目录数，但空的子目录计入（见「决定四」）。另外 `-L N` 限制层数时，没展开的目录照样计入。

**竖线复制到别处为什么歪了？** UTF-8 竖线后面跟的是两个不换行空格（U+00A0）。

**`tree` 能只看目录名不看文件吗？** `-d`。

**`-i` 和 `-f` 能一起用吗？** 能。`-i` 去掉缩进线，`-f` 给全路径，输出就是一份纯路径清单。

### 相关教程

- `21-w2l-commands-cat.py-编码判定与显示记号.md` —— cat.py 的编码判定
- `23-w2l-commands-tail.py-起点语义与跟随模式.md` —— tail.py 的 `-f` 跟随与轮转识别
- `24-w2l-commands-find.py-表达式语法与遍历语义.md` —— find.py 的表达式树，以及「查出来的实现缺陷怎么写进教程」
- `08-tests-测试怎么写怎么跑.md` —— 测试怎么写怎么跑
- `13-新增一个指令的完整过程.md` —— 加一个新指令的完整流程
