# w2l/commands/cp.py — 目标落点与属性保留

`w2l/commands/cp.py` 有 478 行，注册出来的指令叫 **`cp`**。它做的事只有一件：**把一个或多个源复制到目标上**。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cp AI/数据/cp_demo/hello.txt AI/数据/cp_demo/hello.bak   # 复制成新名字
python main.py cp -r AI/数据/cp_demo/project AI/数据/cp_demo/backup/    # 递归复制目录
python main.py cp -v -p AI/数据/cp_demo/hello.txt AI/数据/cp_demo/h2.txt # 边复制边显示，顺带保住时间戳
```

（`AI/数据/` 是本教程的演示目录，第 1 步会把它准备好；那个目录在 `.gitignore` 里，复制示例不会弄脏仓库。）

GNU cp 的完整能力很大（`-b` 备份模式、`--reflink` 写时复制、`--sparse` 稀疏文件、`--attributes-only` 只拷属性、`-Z` SELinux 上下文、`--io-size` 读块大小……），本实现只做了常用的一小块。**没做的部分不假装能做**——比如 `--preserve=ownership` 能写进命令行、也不报错，但在 Windows 上根本没有属主概念，等于什么都不做。

cp 看起来是最简单的命令，实际上它是**所有文件操作里最容易出错的一个**。因为「复制到哪里去」这个问题有至少五种答案：目标已存在且是目录、目标已存在且是文件、目标不存在、给了多个源、给了 `-t` 或 `-T`……每一种的落点都不一样。本实现的答案是：一个叫 `plan()` 的方法先把这件事一次算清，算不出来就直接报错，绝不猜。

本轮实测查出：**8 处与 GNU coreutils 8.32 的行为差异**（其中 4 处是真实缺陷、1 处是纯显示瑕疵、1 处是「本实现更安全但行为不同」、1 处是 Windows 特有的联接陷阱）。另外还发现 1 处**按源码路径推导、但本机跑不了**的疑点（本机没有创建符号链接的权限）。都写在最后一节。

## 为什么这么创建

### 决定一：复制按字节进行，不做编码转换

模块开头第一句就是这件事：

```python
"""cp：复制文件或目录（GNU cp 风格子集）。

复制按字节进行，不做编码转换：二进制文件原样落地，GBK 文本也不会被改写。
```

这是 `cp.py` 与 `cat.py`、`sed.py`、`wc.py` 最根本的区别。那三个指令要**读**文件，必须先判「这是文本还是二进制」，再判文本是 GBK 还是 UTF-8；`cp` 不读内容，只搬字节，所以整个文件里**没有一行编码判定逻辑**。

代价是：GBK 文件复制过去还是 GBK，用 `cat` 看仍是乱码。这是**对的**——复制不该改写内容。只有需要「读出来给人看」的指令才该碰编码。

### 决定二：落点由 `plan()` 一次算清

`plan()`（第 144~198 行）返回四样东西：源列表、目标路径、目标标签、目标是不是目录。整个 `cp` 的行为分支全在这一个方法里定下来，之后 `copy_source()` 只管「拿这个源去落点」。

```python
def plan(self) -> tuple[list[str], Path, str, bool] | None:
    """拆出源列表与目标。返回 None 表示规划阶段已经报错。"""
```

返回 `None` 是一个刻意的设计：**规划阶段的问题一律在动手之前报出来**。如果一边复制一边发现「目标不是目录」，那前面几个源已经拷进去了，调用方看到的是一个半成品状态。`cp` 入口（第 73~87 行）拿到 `None` 就直接退 2，一个字节都不写。

三条互斥的分支：

| 条件 | 走哪条 | 目标怎么定 |
|---|---|---|
| 给了 `-T` | 第 149~161 行 | 最后一个操作数就是目标，**永远不当目录** |
| 给了 `-t` | 第 163~174 行 | `-t` 给的目录，所有操作数都是源 |
| 都没给 | 第 176~198 行 | 最后一个操作数是目标，前面全是源 |

第三种里还有两个细分：给了 `--parents` 时目标必须是已存在的目录（第 187~191 行）；多个源时目标也必须是已存在的目录（第 194~196 行）。

### 决定三：多个源时，目标必须是已存在的目录，这条检查排在源的存在性检查前面

源码里有一行注释专门说明这件事：

```python
        # 多个源时目标必须是已存在的目录，这条先于逐个源的存在性检查。
        if len(sources) > 1 and not dest.is_dir():
            self.error(f"目标 '{dest_text}' 不是目录")
            return None
```

为什么要这么排：`cp a.txt nosuch.txt out.txt` 里有两个问题——`nosuch.txt` 不存在、`out.txt` 不是目录。GNU cp 只报后者（本实现也一样），因为「目标不是目录」意味着**整条命令的形状就不对**，而「某个源不存在」只影响其中一个源。

先报形状问题，用户改完命令形状，下一轮才会看到哪个源真的不在。反过来先报源的问题，用户改完源，下一轮又撞上形状问题——来回两轮。

### 决定四：`-r` 与 `-a` 分开，`-a` 多一条「不解引用符号链接」

```python
        self.recursive = args.recursive or args.archive
        self.no_dereference = args.archive
```

`-a`（归档）= 递归 + 保留属性 + 不解引用符号链接。对应到代码里是两个独立的开关。

「不解引用符号链接」的意思是：源是个符号链接时，**复制那个链接本身**，而不是链接指向的内容。这条只在 `copy_file` 里生效（第 293~295 行）：

```python
        if os.path.islink(src) and self.no_dereference:
            if not self._copy_link(src, dst, src_label, dst_label):
                return
```

**这里有一处按源码路径推导、本机跑不了的疑点**：`copy_source()` 用的是 `os.stat(src)`（第 205 行，**跟随**符号链接）来判定「源是不是目录」。所以一个指向目录的符号链接会被判成目录，直接走 `copy_dir()`，而 `copy_dir()` 里是 `os.listdir(src)`（第 344 行，同样跟随）——**内容被复制了，链接本身没被复制**。`_copy_link()` 只在 `copy_file()` 里被调用，而 `copy_file()` 只处理非目录源。

也就是说：`-a` 拷「指向文件的符号链接」是对的，拷「指向目录的符号链接」不对（会变成拷目录内容）。本机 Windows 没有创建符号链接的权限（`os.symlink` 报 `WinError 1314`），这一条**没能实跑验证**，只是读代码推出来的，记账在此。

### 决定五：属性保留是一个集合，四个选项做并集与差集

`_resolve_preserve()`（第 114~124 行）：

```python
    def _resolve_preserve(self) -> set[str]:
        modes: set[str] = set()
        if self.args.p:
            modes |= {"mode", "timestamps"}
        if self.archive:
            modes |= {"mode", "timestamps", "links"}
        if self.args.preserve is not None:
            modes |= self._parse_modes(self.args.preserve, "--preserve")
        for item in self.args.no_preserve or []:
            modes -= self._parse_modes(item, "--no-preserve")
        return modes
```

四个选项合成一个集合：`-p` 加两项、`-a` 加三项、`--preserve` 加若干、`--no-preserve` 减若干。**顺序无关**，`--no-preserve` 无论写在前面还是后面都生效（因为减法在最后统一做）。

可选的取值固定七个：`_PRESERVE_MODES = ("mode", "timestamps", "ownership", "links", "context", "xattr", "all")`。写了 `all` 就展开成全部七项（第 138~139 行）。写了不认识的直接报 `UsageError`，退出码 2。

其中只有 `timestamps` 和 `mode` 真的有实现：

- `timestamps` → `os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))`（第 311~314 行）
- `mode` → `_apply_mode()`（第 465~471 行），Windows 上落成只读属性
- `ownership` / `context` / `xattr` / `links` → **接受但不执行**。Windows 上没有属主和 SELinux 上下文；`links` 指硬链接，Windows 上要靠 `CreateHardLink`，本实现没做。

### 决定六：Windows 没有 POSIX 权限位，`mode` 落成只读属性

```python
def _apply_mode(dst: Path, src_stat: os.stat_result) -> None:
    """Windows 没有 POSIX 权限位，mode 落成只读属性。"""
    writable = bool(src_stat.st_mode & stat.S_IWRITE)
    try:
        os.chmod(dst, stat.S_IREAD | (stat.S_IWRITE if writable else 0))
    except OSError:
        pass
```

Linux 上 `-p` 能保住 `rwxr-xr-x`；Windows 上能保住的只有「只读 / 可写」这一个位。所以 `cp -p` 之后 `ls -l` 显示的权限位，和源是一样的**只读性**，但和 POSIX 权限没有对应关系。

`except OSError: pass` 是刻意的：权限设置失败**不该让整个复制失败**。内容已经拷过去了，因为改不动只读位就让整条命令退 2 不划算。

### 决定七：目录的 mtime 必须等子文件写完再设

`copy_dir()` 的最后（第 364~371 行）：

```python
        # 目录的 mtime 要在内容写完之后再设，否则会被子文件的写入顶掉。
        if "timestamps" in self.preserve:
            try:
                os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))
            except OSError:
                pass
```

目录的 mtime 记录的是「这个目录的内容最后一次变动的时间」。往目录里写文件会**顶掉**它的 mtime。所以顺序必须是：先递归写完所有子文件，再把目录的 mtime 设成源的 mtime。反过来做的话，`cp -p` 拷出来的目录时间戳会是复制那一刻，不是源的时间。

同一个道理，`copy_dir()` 里给每个子目录建好之后要立刻设它的 mtime——但子目录自己也会在递归中被改，所以这一句必须在它的递归调用**返回之后**。源码的结构正是这样：先 `copy_dir(child, ...)`，整个子树处理完，再统一设 mtime。

### 决定八：覆盖策略的判定顺序是固定的

`copy_file()`（第 254 行起）里，「要不要覆盖目标」这件事按固定顺序问一遍：

| 顺序 | 判定 | 代码位置 |
|---|---|---|
| 1 | `-n` 不覆盖 → 直接返回 | 第 263~264 行 |
| 2 | `-u` 且源不比目标新 → 返回 | 第 265~266 行 |
| 3 | `-i` 且用户回答不是 yes → 返回 | 第 267~268 行 |
| 4 | `-S` 有后缀 → 先把旧目标改名 | 第 270~277 行 |
| 5 | `--remove-destination` → 先删掉目标 | 第 279~285 行 |
| 6 | `-f` → 去掉目标的只读属性 | 第 287~291 行 |
| 7 | 真正写文件 | 第 304~309 行 |

顺序不是随意的：`-n` 排第一是「不覆盖」最优先；`-S` 在 `--remove-destination` 前面，是因为改名已经把旧目标挪走了，后面的删除就没东西可删；`-f` 必须排在写文件前面，因为 Windows 上只读文件用 `open(dst, "wb")` 会直接抛 `PermissionError`。

`-i` 的提示走 stderr 且不换行（第 386~391 行）：

```python
    def _confirm(self, dst_label: str) -> bool:
        self.ctx.stderr.write(f"cp: 覆盖 '{dst_label}'? ")
        self.ctx.stderr.flush()
        line = self.ctx.stdin.readline() if self.ctx.stdin is not None else ""
        answer = line.strip().lower()
        return answer in ("y", "yes")
```

只认 `y` 和 `yes`（不分大小写）。读到 EOF（`readline()` 返回空串）时 `answer` 是空串，**不等于 yes，所以不覆盖**。这正是 GNU 的行为：管道里没有输入时，`cp -i` 不覆盖。

## 这个文件是做什么

### 数据流

```
main.py
  └─ w2l/cli.py  →  w2l/registry.py 找到 cp 的处理函数
        └─ cp(args, ctx)                        第 73~87 行
             ├─ _State(args, ctx)              第 93~110 行：归并选项
             │    └─ _resolve_preserve()        第 114~124 行：属性集合
             ├─ state.plan()                   第 144~198 行：算落点，报错就返回 None
             └─ 逐个源：
                  copy_source()                第 202~237 行
                    ├─ _destination_for()       第 239~250 行：这个源落在哪
                    ├─ _same_file()             第 431~440 行：源和目标是同一个文件？
                    ├─ _is_inside()             第 443~453 行：目录拷进自己？
                    ├─ copy_file()              第 254~320 行
                    └─ copy_dir()               第 322~371 行
```

`copy_file()` 与 `copy_dir()` 的分工：**文件是「打开读、打开写、灌进去」**，目录是「建目录、列子项、挨个递归」。目录里的每个子项再走一遍 `copy_file()` / `copy_dir()`，所以目录拷贝的每一层都复用同一套覆盖策略。

复制内容用的是 `shutil.copyfileobj(reader, writer, _CHUNK)`，`_CHUNK = 1024 * 1024`（1 MB）。两个文件句柄都用 `"rb"` / `"wb"` 打开——**二进制模式，不做换行翻译**。这是决定一的落点。

### 选项清单

| 选项 | argparse 定义 | 作用 |
|---|---|---|
| `-r` `-R` `--recursive` | `action="store_true"` | 递归复制目录 |
| `-a` `--archive` | `action="store_true"` | 递归 + 保留属性 + 不解引用符号链接 |
| `-p` | `action="store_true"` | 保留权限与时间戳（= mode + timestamps） |
| `--preserve [MODE_LIST]` | `nargs="?"` `const="all"` | 保留指定属性，裸写等于 all |
| `--no-preserve MODE_LIST` | `action="append"` | 不保留指定属性，可重复给 |
| `-i` `--interactive` | `action="store_true"` | 覆盖前询问 |
| `-f` `--force` | `action="store_true"` | 强制覆盖（去掉目标的只读属性） |
| `-n` `--no-clobber` | `action="store_true"` | 不覆盖已存在的文件 |
| `-u` `--update` | `action="store_true"` | 仅当源比目标新时才复制 |
| `-v` `--verbose` | `action="store_true"` | 显示每个被复制的条目 |
| `-t` `--target-directory DIR` | 取一个值 | 把目标目录写死 |
| `-T` `--no-target-directory` | `action="store_true"` | 把目标当普通文件 |
| `-S` `--suffix SUFFIX` | 取一个值 | 覆盖前把旧目标改名加该后缀 |
| `--parents` | `action="store_true"` | 在目标下保留源的路径层级 |
| `--remove-destination` | `action="store_true"` | 复制前先删除目标 |

`--preserve` 的 `nargs="?"` + `const="all"` 是**唯一**能接受「裸写」和「带值」两种形态的选项。代价见最后一节的差异一：argparse 会把裸写后面紧跟的第一个操作数当成它的取值吃掉。

### 退出码

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 无结果（命中类指令用，`cp` 不涉及） |
| 2 | 用法或运行错误 |

`cp` 的所有错误都走 2——参数用错、源不存在、目标是目录、目标是同一个文件……统统是 2。GNU cp 用的是 1，这是项目统一约定（`AGENTS.md` 第 3 节），不是本文件的特例。

多个源时其中一个失败，`cp` 会**继续处理后面的源**（第 85~86 行的循环不 break），最后统一退 2（`return 2 if state.had_error else 0`）。所以「退出码是 2」不代表「一个文件都没拷」。

### 关键函数速查

| 函数 | 行号 | 干什么 |
|---|---|---|
| `build_parser()` | 26 | 建 argparse 解析器 |
| `cp()` | 73 | 入口：规划 → 逐个源复制 → 汇总退出码 |
| `_State._resolve_preserve()` | 114 | 四个选项合成属性集合 |
| `_State._parse_modes()` | 126 | 拆分并校验属性名 |
| `_State.plan()` | 144 | 算落点；返回 None 表示规划阶段已报错 |
| `_State.copy_source()` | 202 | 单个源的完整判定与分发 |
| `_State._destination_for()` | 239 | 这个源具体落在哪 |
| `_State.copy_file()` | 254 | 复制一个文件（含全部覆盖策略） |
| `_State.copy_dir()` | 322 | 复制一个目录（递归） |
| `_State._copy_link()` | 373 | 复制符号链接本身 |
| `_State._confirm()` | 386 | `-i` 的提问与判定 |
| `_resolve()` | 401 | 相对路径按 `ctx.cwd` 解析 |
| `_trim()` | 409 | 路径末尾的分隔符去掉，只留一层标签用 |
| `_basename()` | 415 | 取源的名字（尾部斜杠不算） |
| `_parents_relative()` | 423 | `--parents` 用的相对路径 |
| `_same_file()` | 431 | 两个路径是不是同一个文件 |
| `_is_inside()` | 443 | child 是不是落在 parent 里面 |
| `_source_is_newer()` | 456 | 源比目标新吗 |
| `_apply_mode()` | 465 | 把权限落成只读属性 |
| `_remove_path()` | 474 | 删文件或目录树 |

## 有什么用

- **备份一个文件再改它**：`cp -p config.ini config.ini.bak`，时间戳一起保住，改坏了能原样还原。
- **把一份目录树搬走**：`cp -r src dst`，`-v` 可以看着它一条条拷。
- **批量归档**：`cp -a dist/ release/`，`-a` 顺带递归 + 保住时间戳 + 不解引用链接。
- **只在新版本才更新**：`cp -u new.zip old.zip`，源不比目标新就跳过。
- **覆盖前留一手**：`cp -S .bak a.txt b.txt`，旧目标自动变成 `b.txt.bak`。

对写脚本的人来说，本实现的价值是**行为可预测**：落点由 `plan()` 一次定死、错误一律退 2、复制永远按字节。想要 GNU 的完整语义，得用 Git Bash 自带的 `/usr/bin/cp`。

## 怎么用（过程教程）

### 第 1 步：准备演示夹具

后面的例子全部用固定夹具，不用项目源码。理由是源码会变：拿 `w2l/commands/cp.py` 当例子，源码一改教程里写死的预期输出就全过期了。

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1403_make_cp_demo.py
```

预期输出：

```
已生成 AI/数据/cp_demo/（7 个文件）
  hello.txt                    23 字节
  legacy.txt                   18 字节
  payload.bin                 256 字节
  project/src/main.py          15 字节
  project/src/util.py          27 字节
  project/docs/readme.md       10 字节
  project/backup/old.txt       10 字节
```

夹具在 `AI/数据/cp_demo/`，这个目录在 `.gitignore` 里，不进仓库。

三种文件各代表一类：

- `hello.txt` 两行 CRLF 文本——能看出「按字节复制，CRLF 不被改成 LF」
- `legacy.txt` GBK 编码的中文——能看出「复制不做编码转换」
- `payload.bin` 0~255 全字节——能看出「二进制逐字节保真」

后面每一步还会用 `AI/脚本/_t1405_prep_cp_case.py` 另建一个现场，目录是 `AI/数据/cp_demo/case/<名字>/`，分两半：

```
case/<名字>/
├── src/          源：hello.txt、legacy.txt、payload.bin、project/
└── dst/          目标：old.txt（2019 年）、future.txt（2030 年）
```

源和目标**必须分开放在两个目录**：把源拷进它自己所在的目录，落点就是源本身，会撞上「是同一个文件」的检查（见第 22 步）。

`old.txt` 的时间戳钉在 2019-01-01、`future.txt` 钉在 2030-01-01、源钉在 2020-01-01，都是 UTC。`-u` 的两种走向（第 12、13 步）就靠这个。

### 第 2 步：最基础的一拷

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s2
python main.py cp AI/数据/cp_demo/case/s2/src/hello.txt AI/数据/cp_demo/case/s2/dst/hello.new.txt
python main.py ls AI/数据/cp_demo/case/s2/dst
```

预期输出：

```
future.txt
hello.new.txt
old.txt
```

`cp` 成功时**什么都不打印**——这是 Unix 的老规矩。没输出就是成功，有输出通常是在 `-v` 模式或者出错了。

### 第 3 步：目标是已存在的目录时，落点是「目录/源名」

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s3
python main.py cp -v AI/数据/cp_demo/case/s3/src/hello.txt AI/数据/cp_demo/case/s3/dst
python main.py ls AI/数据/cp_demo/case/s3/dst
```

预期输出：

```
'AI/数据/cp_demo/case/s3/src/hello.txt' -> 'AI/数据/cp_demo/case/s3/dst/hello.txt'
future.txt
hello.txt
old.txt
```

`-v` 打印的格式是 `'源' -> '目标'`，**两边都带引号**，和 GNU 8.32 一致。

目标已经是目录时，落点是「目录 + 源的名字」，不是「目录本身」。这是 cp 最容易被误解的一条：同样的 `cp a.txt dst`，`dst` 存不存在，落到的地方完全不同。

### 第 4 步：目标不存在时，目标就是那个新文件

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s4
python main.py cp -v AI/数据/cp_demo/case/s4/src/hello.txt AI/数据/cp_demo/case/s4/dst/newname
python main.py ls AI/数据/cp_demo/case/s4/dst
```

预期输出：

```
'AI/数据/cp_demo/case/s4/src/hello.txt' -> 'AI/数据/cp_demo/case/s4/dst/newname'
future.txt
newname
old.txt
```

落点是 `newname` 本身，不是 `newname/hello.txt`。**判断依据是「目标这个路径现在是不是一个已存在的目录」**，不是「目标看起来像不像目录」。

### 第 5 步：拷目录必须给 `-r`

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s5
python main.py cp AI/数据/cp_demo/case/s5/src/project AI/数据/cp_demo/case/s5/dst
```

预期输出：

```
cp: 未指定 -r，跳过目录 'AI/数据/cp_demo/case/s5/src/project'
```

不给 `-r` 时**不复制，也不递归**，只是跳过并报错，退出码 2。

### 第 6 步：`-r` 拷到已存在的目录

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s6
python main.py cp -r -v AI/数据/cp_demo/case/s6/src/project AI/数据/cp_demo/case/s6/dst
python main.py find AI/数据/cp_demo/case/s6/dst -type f
```

预期输出：

```
'AI/数据/cp_demo/case/s6/src/project' -> 'AI/数据/cp_demo/case/s6/dst/project'
'AI/数据/cp_demo/case/s6/src/project/backup' -> 'AI/数据/cp_demo/case/s6/dst/project/backup'
'AI/数据/cp_demo/case/s6/src/project/backup/old.txt' -> 'AI/数据/cp_demo/case/s6/dst/project/backup/old.txt'
'AI/数据/cp_demo/case/s6/src/project/docs' -> 'AI/数据/cp_demo/case/s6/dst/project/docs'
'AI/数据/cp_demo/case/s6/src/project/docs/readme.md' -> 'AI/数据/cp_demo/case/s6/dst/project/docs/readme.md'
'AI/数据/cp_demo/case/s6/src/project/src' -> 'AI/数据/cp_demo/case/s6/dst/project/src'
'AI/数据/cp_demo/case/s6/src/project/src/main.py' -> 'AI/数据/cp_demo/case/s6/dst/project/src/main.py'
'AI/数据/cp_demo/case/s6/src/project/src/util.py' -> 'AI/数据/cp_demo/case/s6/dst/project/src/util.py'
AI/数据/cp_demo/case/s6/dst/future.txt
AI/数据/cp_demo/case/s6/dst/old.txt
AI/数据/cp_demo/case/s6/dst/project/backup/old.txt
AI/数据/cp_demo/case/s6/dst/project/docs/readme.md
AI/数据/cp_demo/case/s6/dst/project/src/main.py
AI/数据/cp_demo/case/s6/dst/project/src/util.py
```

两点要注意：

1. **目录自己也会打印一行**。GNU cp 也是这样：新建出来的目录要报一行，它下面的每个文件各报一行。
2. **落点是 `dst/project`**，多了一层目录名——因为目标是已存在的目录。

目标里原有的 `future.txt`、`old.txt` 还在，源里没有的文件不会被删掉。**目录复制是「合并」不是「替换」**。

### 第 7 步：`-r` 拷到不存在的目标

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s7
python main.py cp -r -v AI/数据/cp_demo/case/s7/src/project AI/数据/cp_demo/case/s7/dst/clone
python main.py find AI/数据/cp_demo/case/s7/dst/clone -type f
```

预期输出：

```
'AI/数据/cp_demo/case/s7/src/project' -> 'AI/数据/cp_demo/case/s7/dst/clone'
'AI/数据/cp_demo/case/s7/src/project/backup' -> 'AI/数据/cp_demo/case/s7/dst/clone/backup'
'AI/数据/cp_demo/case/s7/src/project/backup/old.txt' -> 'AI/数据/cp_demo/case/s7/dst/clone/backup/old.txt'
'AI/数据/cp_demo/case/s7/src/project/docs' -> 'AI/数据/cp_demo/case/s7/dst/clone/docs'
'AI/数据/cp_demo/case/s7/src/project/docs/readme.md' -> 'AI/数据/cp_demo/case/s7/dst/clone/docs/readme.md'
'AI/数据/cp_demo/case/s7/src/project/src' -> 'AI/数据/cp_demo/case/s7/dst/clone/src'
'AI/数据/cp_demo/case/s7/src/project/src/main.py' -> 'AI/数据/cp_demo/case/s7/dst/clone/src/main.py'
'AI/数据/cp_demo/case/s7/src/project/src/util.py' -> 'AI/数据/cp_demo/case/s7/dst/clone/src/util.py'
AI/数据/cp_demo/case/s7/dst/clone/backup/old.txt
AI/数据/cp_demo/case/s7/dst/clone/docs/readme.md
AI/数据/cp_demo/case/s7/dst/clone/src/main.py
AI/数据/cp_demo/case/s7/dst/clone/src/util.py
```

目标不存在时，**目标目录本身就是那份目录的副本**，不再套一层同名目录。所以是 `dst/clone/backup/old.txt`，不是 `dst/clone/project/backup/old.txt`。

这一条最容易记反：**目标已存在 → 多一层；目标不存在 → 少一层**。

### 第 8 步：源尾部的斜杠不影响落点

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s8
python main.py cp -r -v AI/数据/cp_demo/case/s8/src/project/ AI/数据/cp_demo/case/s8/dst
```

预期输出：

```
'AI/数据/cp_demo/case/s8/src/project/' -> 'AI/数据/cp_demo/case/s8/dst/project'
'AI/数据/cp_demo/case/s8/src/project//backup' -> 'AI/数据/cp_demo/case/s8/dst/project/backup'
'AI/数据/cp_demo/case/s8/src/project//backup/old.txt' -> 'AI/数据/cp_demo/case/s8/dst/project/backup/old.txt'
'AI/数据/cp_demo/case/s8/src/project//docs' -> 'AI/数据/cp_demo/case/s8/dst/project/docs'
'AI/数据/cp_demo/case/s8/src/project//docs/readme.md' -> 'AI/数据/cp_demo/case/s8/dst/project/docs/readme.md'
'AI/数据/cp_demo/case/s8/src/project//src' -> 'AI/数据/cp_demo/case/s8/dst/project/src'
'AI/数据/cp_demo/case/s8/src/project//src/main.py' -> 'AI/数据/cp_demo/case/s8/dst/project/src/main.py'
'AI/数据/cp_demo/case/s8/src/project//src/util.py' -> 'AI/数据/cp_demo/case/s8/dst/project/src/util.py'
```

**落点是对的**（`dst/project/backup/old.txt`），GNU 8.32 实测也是这样。但打印出来的标签里多了一个斜杠：`project//backup`。

原因在 `copy_dir()` 的第 351 行：子项标签是 `f"{src_label}/{name}"` 拼出来的，而 `src_label` 用的是原始操作数文本（带着尾部的斜杠），拼的时候又加了一个斜杠。

GNU 那边是 `'dir1/inner.txt'`（单斜杠）。本实现是 `'dir1//inner.txt'`。**纯显示瑕疵，不影响落地路径**，但脚本如果拿 `-v` 的输出做解析就会被坑到。详见最后一节的差异八。

### 第 9 步：多个源时，目标必须是已存在的目录

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s9
python main.py cp AI/数据/cp_demo/case/s9/src/hello.txt AI/数据/cp_demo/case/s9/src/nosuch.txt AI/数据/cp_demo/case/s9/dst/out.txt
```

预期输出：

```
cp: 目标 'AI/数据/cp_demo/case/s9/dst/out.txt' 不是目录
```

两个错误摆在一起：第二个源 `nosuch.txt` 不存在，目标 `out.txt` 又不是目录。报的是**后者**。

这正是源码第 193 行注释说的：「这条先于逐个源的存在性检查」。

### 第 10 步：多个源进已存在的目录

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s10
python main.py cp -v AI/数据/cp_demo/case/s10/src/hello.txt AI/数据/cp_demo/case/s10/src/legacy.txt AI/数据/cp_demo/case/s10/dst
python main.py ls AI/数据/cp_demo/case/s10/dst
```

预期输出：

```
'AI/数据/cp_demo/case/s10/src/hello.txt' -> 'AI/数据/cp_demo/case/s10/dst/hello.txt'
'AI/数据/cp_demo/case/s10/src/legacy.txt' -> 'AI/数据/cp_demo/case/s10/dst/legacy.txt'
future.txt
hello.txt
legacy.txt
old.txt
```

多个源时每个源各走一遍 `_destination_for()`，都落到同一个目录下、各自的名字。

### 第 11 步：`-n` 不覆盖已存在的文件

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s11
python main.py cp -n -v AI/数据/cp_demo/case/s11/src/hello.txt AI/数据/cp_demo/case/s11/dst/old.txt
python main.py cat AI/数据/cp_demo/case/s11/dst/old.txt
```

预期输出：

```
old content
```

`-n` 挡住了复制：`-v` **一行都没打印**（跳过的条目不报），目标里的内容还是原来的 `old content`。

`-n` 只挡「已存在的文件」。目标不存在时照常复制。

### 第 12 步：`-u` 遇到「目标更新」就跳过

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s12
python main.py cp -u -v AI/数据/cp_demo/case/s12/src/hello.txt AI/数据/cp_demo/case/s12/dst/future.txt
python main.py cat AI/数据/cp_demo/case/s12/dst/future.txt
```

预期输出：

```
future content
```

目标的 mtime 是 2030 年，比源（2020 年）新，所以跳过。`-v` 同样一行没打印。

### 第 13 步：`-u` 遇到「源更新」就复制

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s13
python main.py cp -u -v AI/数据/cp_demo/case/s13/src/hello.txt AI/数据/cp_demo/case/s13/dst/old.txt
python main.py cat AI/数据/cp_demo/case/s13/dst/old.txt
```

预期输出：

```
'AI/数据/cp_demo/case/s13/src/hello.txt' -> 'AI/数据/cp_demo/case/s13/dst/old.txt'
hello cp
second line
```

目标的 mtime 是 2019 年，比源旧，所以复制。内容换成了源的内容。

`-u` 比的是 **mtime**，且是**严格大于**才算「源更新」（第 462 行 `src_stat.st_mtime_ns > dst_stat.st_mtime_ns`）。时间戳完全相等时按「不更新」处理。

### 第 14 步：`-i` 覆盖前问一句

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s14
python main.py cp -i AI/数据/cp_demo/case/s14/src/hello.txt AI/数据/cp_demo/case/s14/dst/old.txt
python main.py cat AI/数据/cp_demo/case/s14/dst/old.txt
```

预期输出：

```
cp: 覆盖 'AI/数据/cp_demo/case/s14/dst/old.txt'? old content
```

提示打在 stderr 且**不换行**，所以后面 `cat` 的输出接在同一行——这不是排版错误，是提示符本来就没有换行。

这条命令没喂 stdin，`readline()` 读到 EOF 返回空串，不算 `yes`，所以**没有覆盖**，目标还是 `old content`。

交互时直接敲 `y` 或 `yes` 回车就覆盖，敲别的（含直接回车）就跳过。

### 第 15 步：`-p` 保住时间戳

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s15
python main.py cp -p AI/数据/cp_demo/case/s15/src/hello.txt AI/数据/cp_demo/case/s15/dst/hello.new.txt
python AI/脚本/_t1406_show_mtime.py --cmp AI/数据/cp_demo/case/s15/src/hello.txt AI/数据/cp_demo/case/s15/dst/hello.new.txt
```

预期输出：

```
相同
```

`--cmp` 只比「两个时间戳是不是同一个」，不打印具体值——因为不加 `-p` 时复制时刻是「现在」，把具体时间写进预期输出会让每次核对都失败。

### 第 16 步：不加 `-p`，时间戳就是复制那一刻

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s16
python main.py cp AI/数据/cp_demo/case/s16/src/hello.txt AI/数据/cp_demo/case/s16/dst/hello.new.txt
python AI/脚本/_t1406_show_mtime.py --cmp AI/数据/cp_demo/case/s16/src/hello.txt AI/数据/cp_demo/case/s16/dst/hello.new.txt
```

预期输出：

```
不同
```

源的时间戳是 2020-01-01，副本的时间戳是复制的那一刻。

### 第 17 步：`-S` 覆盖前把旧目标改名加后缀

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s17
python main.py cp -v -S .bak AI/数据/cp_demo/case/s17/src/hello.txt AI/数据/cp_demo/case/s17/dst/old.txt
python main.py ls AI/数据/cp_demo/case/s17/dst
```

预期输出：

```
'AI/数据/cp_demo/case/s17/src/hello.txt' -> 'AI/数据/cp_demo/case/s17/dst/old.txt'
future.txt
old.txt
old.txt.bak
```

旧目标没有直接被冲掉，而是先改名成 `old.txt.bak` 留在原地。这是 `os.replace(dst, backup)` 做的（第 273 行），**不是复制**——改名是原子的，旧内容的 inode 直接挪过去，不会先复制一份再删。

目标不存在时 `-S` 不起作用（没有旧目标可改名）。

### 第 18 步：`--parents` 在目标下保留源的路径层级

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s18
python main.py cp -v --parents AI/数据/cp_demo/case/s18/src/project/src/main.py AI/数据/cp_demo/case/s18/dst
python main.py find AI/数据/cp_demo/case/s18/dst -type f
```

预期输出：

```
'AI/数据/cp_demo/case/s18/src/project/src/main.py' -> 'AI/数据/cp_demo/case/s18/dst/AI/数据/cp_demo/case/s18/src/project/src/main.py'
AI/数据/cp_demo/case/s18/dst/AI/数据/cp_demo/case/s18/src/project/src/main.py
AI/数据/cp_demo/case/s18/dst/future.txt
AI/数据/cp_demo/case/s18/dst/old.txt
```

`--parents` 保留的是**源路径相对于当前目录的整条路径**（第 423~428 行：去掉盘符和开头的分隔符，其余全留）。所以源是 `AI/数据/.../src/project/src/main.py`，落点就是 `dst/AI/数据/.../src/project/src/main.py`。

这条看着长，是因为本教程的源路径本来就长。在一个短的相对路径下，比如 `cd 到某个目录后 cp --parents project/src/main.py dst`，落点就是 `dst/project/src/main.py`。

`--parents` 还会**顺手把父目录建出来**（第 297~303 行），这是它和普通 `-r` 的另一个区别。

### 第 19 步：`-t` 把目标目录写死

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s19
python main.py cp -v -t AI/数据/cp_demo/case/s19/dst AI/数据/cp_demo/case/s19/src/hello.txt AI/数据/cp_demo/case/s19/src/legacy.txt
python main.py ls AI/数据/cp_demo/case/s19/dst
```

预期输出：

```
'AI/数据/cp_demo/case/s19/src/hello.txt' -> 'AI/数据/cp_demo/case/s19/dst/hello.txt'
'AI/数据/cp_demo/case/s19/src/legacy.txt' -> 'AI/数据/cp_demo/case/s19/dst/legacy.txt'
future.txt
hello.txt
legacy.txt
old.txt
```

`-t` 给了以后，**所有操作数都是源**，没有「最后一个是目标」这回事。`-t` 指向的目录必须已经存在（第 168~170 行），否则报「没有那个文件或目录」。

### 第 20 步：`-T` 把目标当普通文件

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s20
python main.py cp -v -T -r AI/数据/cp_demo/case/s20/src/project AI/数据/cp_demo/case/s20/dst/flat
python main.py find AI/数据/cp_demo/case/s20/dst/flat -type f
```

预期输出：

```
'AI/数据/cp_demo/case/s20/src/project' -> 'AI/数据/cp_demo/case/s20/dst/flat'
'AI/数据/cp_demo/case/s20/src/project/backup' -> 'AI/数据/cp_demo/case/s20/dst/flat/backup'
'AI/数据/cp_demo/case/s20/src/project/backup/old.txt' -> 'AI/数据/cp_demo/case/s20/dst/flat/backup/old.txt'
'AI/数据/cp_demo/case/s20/src/project/docs' -> 'AI/数据/cp_demo/case/s20/dst/flat/docs'
'AI/数据/cp_demo/case/s20/src/project/docs/readme.md' -> 'AI/数据/cp_demo/case/s20/dst/flat/docs/readme.md'
'AI/数据/cp_demo/case/s20/src/project/src' -> 'AI/数据/cp_demo/case/s20/dst/flat/src'
'AI/数据/cp_demo/case/s20/src/project/src/main.py' -> 'AI/数据/cp_demo/case/s20/dst/flat/src/main.py'
'AI/数据/cp_demo/case/s20/src/project/src/util.py' -> 'AI/数据/cp_demo/case/s20/dst/flat/src/util.py'
AI/数据/cp_demo/case/s20/dst/flat/backup/old.txt
AI/数据/cp_demo/case/s20/dst/flat/docs/readme.md
AI/数据/cp_demo/case/s20/dst/flat/src/main.py
AI/数据/cp_demo/case/s20/dst/flat/src/util.py
```

`-T` 说「别把目标当目录」。于是 `dst/flat` 就是那份目录的副本，**不套 `project` 这一层**。

`-T` 和 `-t` 是两个方向：`--parents` 要的是「目标必须是目录」，`-T` 说的是「目标不是目录」，两者同时给是矛盾的（GNU 直接报错，本实现不报，见差异四）。

### 第 21 步：`--remove-destination` 复制前先删掉目标

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s21
python main.py cp -v --remove-destination AI/数据/cp_demo/case/s21/src/hello.txt AI/数据/cp_demo/case/s21/dst/old.txt
python main.py cat AI/数据/cp_demo/case/s21/dst/old.txt
```

预期输出：

```
'AI/数据/cp_demo/case/s21/src/hello.txt' -> 'AI/数据/cp_demo/case/s21/dst/old.txt'
hello cp
second line
```

先删目标再复制。和 `-S` 的区别：`-S` 把旧目标**改名留下**，`--remove-destination` 直接**删掉**。

两个一起给时，源码先做改名（第 270~277 行），改名后 `exists` 置 False，所以删除那一步不会再触发——**旧目标以 `.bak` 的形式保住了，不会被删**。

### 第 22 步：源和目标是同一个文件

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s22
python main.py cp AI/数据/cp_demo/case/s22/src/hello.txt AI/数据/cp_demo/case/s22/src/hello.txt
```

预期输出：

```
cp: 'AI/数据/cp_demo/case/s22/src/hello.txt' 和 'AI/数据/cp_demo/case/s22/src/hello.txt' 是同一个文件
```

`_same_file()`（第 431~440 行）先用 `os.path.samefile()` 比（Windows 上比的是卷号 + 文件索引号，比路径可靠），失败再退回「规范化后的路径字符串相等」。

这一条也是为什么演示夹具要把源和目标分开放：把源拷进它自己所在的目录，落点就是源本身。

### 第 23 步：目标的父目录不存在

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s23
python main.py cp AI/数据/cp_demo/case/s23/src/hello.txt AI/数据/cp_demo/case/s23/dst/nodir/out.txt
```

预期输出：

```
cp: 无法创建普通文件 'AI/数据/cp_demo/case/s23/dst/nodir/out.txt': No such file or directory
```

`cp` **不会替你建父目录**（只有 `--parents` 会）。GNU 也是这样。

### 第 24 步：二进制文件逐字节保真

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s24
python main.py cp AI/数据/cp_demo/case/s24/src/payload.bin AI/数据/cp_demo/case/s24/dst/payload.new.bin
python main.py wc -c AI/数据/cp_demo/case/s24/src/payload.bin AI/数据/cp_demo/case/s24/dst/payload.new.bin
```

预期输出：

```
256 AI/数据/cp_demo/case/s24/src/payload.bin
256 AI/数据/cp_demo/case/s24/dst/payload.new.bin
512 total
```

0~255 全部 256 个字节，源和副本一样多。

### 第 25 步：GBK 文件不被改写

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s25
python main.py cp AI/数据/cp_demo/case/s25/src/legacy.txt AI/数据/cp_demo/case/s25/dst/legacy.new.txt
python main.py wc -c AI/数据/cp_demo/case/s25/src/legacy.txt AI/数据/cp_demo/case/s25/dst/legacy.new.txt
```

预期输出：

```
18 AI/数据/cp_demo/case/s25/src/legacy.txt
18 AI/数据/cp_demo/case/s25/dst/legacy.new.txt
36 total
```

`legacy.txt` 是 GBK 编码的中文，18 字节。副本也是 18 字节——**没有被转成 UTF-8**（转成 UTF-8 的话「旧内容\n中文第二行\n」是 6 + 15 = 21 字节）。

这是决定一的直接结果：`cp` 只搬字节，不解码、不重编码。

### 第 26 步：`--preserve` 裸写会把下一个操作数吃掉

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s26
python main.py cp --preserve AI/数据/cp_demo/case/s26/src/hello.txt AI/数据/cp_demo/case/s26/dst/hello.new.txt
```

预期输出：

```
cp: --preserve 的无效取值 'AI/数据/cp_demo/case/s26/src/hello.txt'，可选：mode, timestamps, ownership, links, context, xattr, all
```

GNU cp 下这条命令是**正常执行**的（`--preserve` 不带值 = 保留全部属性）。本实现报错了。

原因在 `build_parser()` 第 45~52 行：`--preserve` 用了 `nargs="?"`，argparse 会把紧跟其后的第一个操作数当成它的取值吃掉，然后 `_parse_modes()` 校验时发现「a.txt」不是合法的属性名，报错退出 2。

**绕法**：写成 `--preserve=all`，或者把 `--preserve` 放到命令行的**最后**（后面没有操作数可吃，此时 argparse 用 `const="all"`）。详见差异一。

### 第 27 步：`-n` 与 `-i` 同时给

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s27
python main.py cp -n -i AI/数据/cp_demo/case/s27/src/hello.txt AI/数据/cp_demo/case/s27/dst/old.txt
python main.py cat AI/数据/cp_demo/case/s27/dst/old.txt
```

预期输出：

```
old content
```

本实现里 `-n` 压过 `-i`：**不提示、不覆盖**（源码第 108~109 行的注释就是这么写的）。

但 GNU cp 的实际规则是「**后写的那个赢**」：`cp -n -i` 会提示并（回答 y 后）覆盖，`cp -i -n` 才是不提示不覆盖。本实现两种顺序都是「`-n` 赢」。详见差异二。

### 第 28 步：目标带尾部斜杠

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1405_prep_cp_case.py s28
python main.py cp -v AI/数据/cp_demo/case/s28/src/hello.txt AI/数据/cp_demo/case/s28/dst/newname/
python main.py ls AI/数据/cp_demo/case/s28/dst
```

预期输出：

```
'AI/数据/cp_demo/case/s28/src/hello.txt' -> 'AI/数据/cp_demo/case/s28/dst/newname'
future.txt
newname
old.txt
```

GNU cp 下这条命令是**报错**的：`cannot create regular file 'newname/': Not a directory`。GNU 把目标末尾的斜杠理解成「这个目标必须是目录」，而目标不存在 ⇒ 报错。

本实现把斜杠归一化掉了，落成了一个**普通文件** `newname`。详见差异三。

### 第 29 步：跑相关测试

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest tests/test_cp.py 2>&1 | tail -1
```

预期输出（耗时每次不同，用 `<T>` 占位）：

```
44 passed in <T>s
```

`tests/test_cp.py` 有 44 个用例，分三块：正常路径（12 个）、选项组合（20 个）、错误路径（12 个）。用例覆盖的行为基线来自 GNU coreutils 8.32 的实跑对照。

注意命令末尾的 `| tail -1`：本项目的 `pyproject.toml` 里 `addopts = "-q"`，`pytest -q` 的输出被压成一行进度条，看不到用例数；`tail -1` 取的是最后那行汇总。

跑完整测试集：

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest -q
```

### 第 30 步：与 GNU cp 8.32 对拍

开发任务落地 cp 时留了 `AI/脚本/_t410_diff_cp.py`，57 组用例全绿。本轮补了 `AI/脚本/_t1401_probe_cp_diff2.py`，37 组新用例专打前者没覆盖的角落，查出 8 处差异。

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1401_probe_cp_diff2.py
```

每组用例在两个一模一样的沙箱里各跑一次（沙箱 A 跑 `/usr/bin/cp`，沙箱 B 跑 `python main.py cp`），比四样：成功与否、有无报错、落地后的目录树（路径 + 内容摘要）、`-v` 打印的「源 → 目标」对序列。

### 实测出的与 GNU coreutils 8.32 的八处差异

以下每一条都是实测的：两边在同一个沙箱里跑同一条命令，比对结果。源码范围属开发任务，本轮按只读原则**没有改动 `w2l/`**。

#### 差异一（缺陷）：`--preserve` 裸写会吃掉下一个操作数

| | 命令 | 结果 |
|---|---|---|
| GNU 8.32 | `cp --preserve a.txt copy.txt` | 退出 0，正常复制 |
| 本实现 | 同上 | 退出 2，`--preserve 的无效取值 'a.txt'` |

根因：`build_parser()` 第 45~52 行的 `--preserve` 用了 `nargs="?"`。argparse 遇到 `nargs="?"` 的选项时，会把后面紧跟的第一个非选项参数当成它的值，于是「源文件名」被当成了属性名。

GNU 那边 `--preserve` 的属性值必须用 `=` 写（`--preserve=mode`），裸写表示「全部」。本实现虽然也支持 `=` 形式（`--preserve=all` 正常），但裸写形态被 argparse 破坏了。

源码第 38 行的示例里写的是 `python main.py cp -n --parents w2l/cli.py backup/`，没有用到裸 `--preserve`，所以这个坑在帮助文本里看不出来。

**绕法**：`--preserve=all`，或把 `--preserve` 放在命令行最后。

#### 差异二（缺陷）：`-n` 与 `-i` 的优先级被写死，GNU 是「后写的赢」

| 命令 | GNU 8.32 | 本实现 |
|---|---|---|
| `cp -n -i a.txt b.txt` | 提示 `overwrite 'b.txt'?`，回答 y 后**覆盖** | 不提示、**不覆盖** |
| `cp -i -n a.txt b.txt` | 不提示、不覆盖 | 不提示、不覆盖 |

GNU 的 `cp` 在解析选项时，`-i` 会清掉 no-clobber 标志、`-n` 会清掉 interactive 标志——所以是**最后一个生效**。本实现第 108~109 行把它写成了固定的「`-n` 压过 `-i`」：

```python
        # GNU 里 -n 压过 -i：给了 -n 就不问了。
        self.interactive = args.interactive and not args.no_clobber
```

**这行注释对 GNU 的描述是错的**——GNU 不是「`-n` 压过 `-i`」，是「后写的压过先写的」。实测两边的差异只在 `-n` 写在 `-i` 前面时体现出来。

#### 差异三（缺陷）：目标末尾的斜杠被归一化掉了

| | 命令 | 结果 |
|---|---|---|
| GNU 8.32 | `cp a.txt newdir/` | 退出 1，`cannot create regular file 'newdir/': Not a directory`，**什么也没创建** |
| 本实现 | 同上 | 退出 0，创建了一个**普通文件** `newdir` |

GNU 把目标末尾的斜杠理解成「目标必须是目录」，目标不存在就报错。本实现的 `_resolve()`（第 401~406 行）用 `Path(operand)` 构造路径，pathlib 会把末尾的分隔符直接吃掉，于是斜杠这个信号就丢了。

影响面：想让「目标必须是目录」时，用 `-t`（第 19 步）比用尾斜杠可靠。

#### 差异四（缺陷）：`-T` 绕过了 `--parents` 的「目标必须是目录」检查

| | 命令 | 结果 |
|---|---|---|
| GNU 8.32 | `cp -T --parents a.txt destdir` | 退出 1，`with --parents, the destination must be a directory` |
| 本实现 | 同上 | 退出 0，复制到了 `destdir/a.txt` |

根因：`plan()` 第 149~161 行的 `-T` 分支**直接 return**，而 `--parents` 的检查在第 187~191 行，够不着。

这条其实是「两个矛盾选项同时给」的场景，GNU 拒绝，本实现照做。危害不大，但属于「矛盾选项没被识别」。

#### 差异五（行为不同，本实现更安全）：把目录拷进它自己里面

| | 命令 | 结果 |
|---|---|---|
| GNU 8.32 | `cp -r dir1 dir1` | 退出 1，报 `cannot copy a directory, 'dir1', into itself, 'dir1/dir1'`——**但已经建出了 `dir1/dir1/` 并拷完了内容** |
| 本实现 | 同上 | 退出 2，**什么都没建** |

两边都拒绝，区别在**副作用**：GNU 先动手、发现递归后报错，留下一份半成品；本实现在 `copy_source()` 第 230~232 行就挡住了，一个字节都不写。

`cp -r dir1 dir1/sub` 同理。

这条本实现更安全，但它确实与 GNU 的可观测行为不同：GNU 的命令失败后目录里多了东西，本实现没有。**如果你的脚本依赖「GNU 失败后现场是脏的」这个行为**（极少见），会有差别。

#### 差异六（缺陷，Windows 特有）：目录联接被当成普通目录钻进去

Windows 的**目录联接**（junction，`mklink /J` 建的）和符号链接不是一回事：`os.path.islink()` 对它返回 `False`，`os.stat()` 把它当普通目录。

| | 命令 | 结果 |
|---|---|---|
| GNU 8.32 | `cp -r src destdir`（`src/loop` 是指回 `src` 的联接） | 退出 0，**联接被原样保留**（落地后仍是联接） |
| 本实现 | 同上 | 退出 2，一路钻到 Windows 路径长度上限，报 `无法打开目录 'src/loop/loop/loop/...': 系统无法辨识文件名` |

本实现的 `copy_dir()` 第 344 行用 `os.listdir(src)` 遍历，Windows 上它会**跟着联接走**；子项判定用 `os.stat(child, follow_symlinks=False)`（第 355 行），联接被判成目录，于是递归进去，一层套一层。

实测数据：两边落地后都是 160 个条目、最深 41 层——都是撞在同一条路径长度墙上。但 GNU 是把联接**保留成联接**（不增长），本实现是把它**实体化成目录**（每层都长），所以本实现先撞墙、先失败。

这跟 `w2l/commands/tree.py` 的联接缺陷是同一类问题（开发任务 tick #16 记录过 tree 的自引用联接递归到 64 层）。

**普通联接（不指回祖先）两边一致**：都把联接的内容复制过去，落地成普通目录。

#### 差异七（显示瑕疵）：源尾部的斜杠让 `-v` 的标签多一个斜杠

| | 命令 | `-v` 打印 |
|---|---|---|
| GNU 8.32 | `cp -v -r dir1/ destdir` | `'dir1/inner.txt' -> 'destdir/dir1/inner.txt'` |
| 本实现 | 同上 | `'dir1//inner.txt' -> 'destdir/dir1/inner.txt'` |

**落地路径两边完全一样**，只有左边显示的标签多一个斜杠。根因在 `copy_dir()` 第 351 行：子项标签用 `f"{src_label}/{name}"` 拼，而 `src_label` 带着原始操作数的尾斜杠。

影响：**脚本不要拿 `-v` 的输出做路径解析**，它只适合给人看。

#### 差异八（有意取舍）：报错文案是中文，退出码是 2

GNU cp 的报错是英文、退出码 1；本实现是中文、退出码 2。这不是缺陷，是项目统一约定（`AGENTS.md` 第 3 节：退出码 `0` 成功、`1` 无结果、`2` 用法或运行错误）。

差分脚本对这一条不做逐字比对，只比「有没有报错」。

### 一处没能实跑的疑点

**`-a` 拷「指向目录的符号链接」时，链接本身没被复制。**

按源码路径推导：`copy_source()` 用 `os.stat(src)`（跟随符号链接）判定源是不是目录，所以指向目录的符号链接被判成目录 → 走 `copy_dir()` → `os.listdir(src)`（跟随）→ **内容被复制了**。`_copy_link()` 只在 `copy_file()` 里被调用，而 `copy_file()` 只处理非目录源。

本机 Windows 创建符号链接要管理员或开发者模式权限，`os.symlink` 报 `WinError 1314`（客户端没有所需的特权），**所以这一条没能实跑验证**。修起来不难：`copy_source()` 里改成用 `os.lstat()` 判目录，判出是符号链接时统一走 `_copy_link()`。但源码属开发任务范围，本轮没动。

### 常见疑问

**Q：为什么拷目录要 `-r`，不给我就跳过？**

GNU cp 不给 `-r` 拷目录也会报错退出。本实现报的是「未指定 -r，跳过目录 'X'」，措辞像「跳过」但退出码是 2、命令整体算失败。措辞是本项目的中文风格，实际行为是拒绝。

**Q：`-p` 之后 `ls -l` 显示的权限和源一样吗？**

只读性一样，POSIX 权限位不一样。Windows 上没有 POSIX 权限位，`mode` 落成只读属性（`chmod` 的 `S_IREAD` / `S_IWRITE`）。所以「源是只读 → 副本也是只读」成立，「源是 `rwxr-xr-x` → 副本也是 `rwxr-xr-x`」不成立。

**Q：`-u` 比的是修改时间还是访问时间？**

修改时间（mtime）。`_source_is_newer()` 第 462 行比的是 `st_mtime_ns`。

**Q：`--preserve=ownership` 为什么不报错？**

它在合法的取值表里，所以命令行解析过关。但 Windows 没有属主概念，`_apply_mode()` 之外没有任何代码消费 `ownership` 这个标记，所以等于什么都不做。

**Q：为什么 `-v` 跳过的条目不打印？**

`-n`、`-u` 判定为跳过时直接 `return`，还没走到第 319~320 行的打印。所以 `-v` 打印的**全部是真正复制了的东西**，这是 GNU 的行为。

**Q：`cp` 会覆盖目标目录里的同名文件吗？**

会，但只覆盖**同名文件**，目标里多出来的文件保留（合并语义）。想完全替换用 `--remove-destination`。

**Q：为什么 `-i` 的提示没有换行？**

提示符后面要接用户的输入，标准做法就是不换行（`cp` 的提示符通常带 `?` 结尾）。本实现的提示是 `cp: 覆盖 'X'? `，注意 `?` 后面还有一个空格。

### 相关教程

| 篇目 | 为什么一起读 |
|---|---|
| `teach/13-新增一个指令的完整过程.md` | cp 是「一个指令 = 一个文件 + 一个测试文件」的样板 |
| `teach/21-w2l-commands-cat.py-编码判定与显示记号.md` | 对照着看：cat 要判编码，cp 不判 |
| `teach/26-w2l-commands-du.py-统计口径与去重规则.md` | du 要认硬链接，cp 的 `--preserve=links` 是同一个话题 |
| `teach/25-w2l-commands-tree.py-树形输出与画线规则.md` | tree 也有 Windows 联接的同一个坑（差异六） |
| `teach/27-w2l-commands-sed.py-地址语义与正则翻译.md` | sed 的原地修改是「临时文件 + 原子替换」，和 cp 的 `-S` 改名同源 |
| `teach/00-项目总览与阅读顺序.md` | 全部 29 篇的索引 |

本篇用到的脚本：

| 脚本 | 干什么 |
|---|---|
| `AI/脚本/_t1401_probe_cp_diff2.py` | 37 组用例与 GNU cp 8.32 的对拍，结果落在 `AI/数据/cp_probe2/diff_cp2.json` |
| `AI/脚本/_t1402_show_cp_diff2.py` | 把对拍结果里关键用例的两侧原文打出来 |
| `AI/脚本/_t1403_make_cp_demo.py` | 生成本篇的演示夹具 `AI/数据/cp_demo/` |
| `AI/脚本/_t1404_probe_cp_junction.py` | 查目录联接在两边的处理细节与递归深度 |
| `AI/脚本/_t1405_prep_cp_case.py` | 给每一步重建现场（源与目标分目录、时间戳钉死） |
| `AI/脚本/_t1406_show_mtime.py` | 打印或比较两个文件的修改时间 |
| `AI/脚本/_t1407_capture_cp_tut.py` | 把本篇 28 个命令块逐条真跑一遍，产出预期输出 |
