"""生成 teach/27-w2l-commands-sed.py-地址语义与正则翻译.md。

预期输出不是手抄的：用 AI/脚本/_t12_verify_teach.py 的 run_in_shell 真跑一遍
拿到——同一条命令、同一种合并方式（stdout/stderr 用 2>&1 合流），所以文档里写的
预期输出与核对器看到的完全一致。

用法:
    python AI/脚本/_t1016_make_teach27.py
"""

from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = Path(os.path.dirname(os.path.dirname(HERE)))
TARGET = ROOT / "teach" / "27-w2l-commands-sed.py-地址语义与正则翻译.md"

# 复用核对器的执行路径（stdout 与 stderr 用 2>&1 合流，与核对器一致）
_spec = importlib.util.spec_from_file_location(
    "t12", os.path.join(HERE, "_t12_verify_teach.py")
)
t12 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(t12)

F = "AI/数据/sed_demo"

# 教程里要跑的 bash 命令。键是 @@占位符@@，值是命令行。
# 顺序即文档里的顺序：有些命令会改夹具（原地修改），必须按顺序跑。
CMDS: dict[str, str] = {
    "FIXTURE": "python AI/脚本/_t1010_make_sed_fixture.py",
    # 第 2 步：三种替换
    "S1": f"python main.py sed 's/a/b/' {F}/a.txt",
    "S2": f"python main.py sed 's/a/b/g' {F}/a.txt",
    "S3": f"python main.py sed 's/a/A/2' {F}/a.txt",
    "S4": f"python main.py sed 's/a/A/I' {F}/a.txt",
    # 第 3 步：-n 与地址
    "S5": f"python main.py sed -n '\\|bravo|p' {F}/a.txt",
    "S6": f"python main.py sed -n '2p' {F}/a.txt",
    # 第 4 步：范围地址
    "S7": f"python main.py sed -n '2,3p' {F}/a.txt",
    "S8": f"python main.py sed -n '2,+2p' {F}/a.txt",
    "S9": f"python main.py sed -n '\\|bravo|,/echo/p' {F}/a.txt",
    "S9B": f"python main.py sed -n '\\|bravo|,\\|echo|p' {F}/a.txt",
    "S10": f"python main.py sed -n '0,/echo/p' {F}/a.txt",
    "RANGE_SAME": "printf 'a\\na\\nb\\n' | python main.py sed -n '\\|a|,\\|a|p'",
    # 第 5 步：BRE 与 ERE
    "BRE_GRP": f"python main.py sed 's/\\(a\\)\\(l\\)/\\2\\1/' {F}/a.txt",
    "ERE_GRP": f"python main.py sed -r 's/(a)(l)/\\2\\1/' {F}/a.txt",
    "BRE_PAREN": f"python main.py sed 's/(a)/X/' {F}/a.txt",
    "BRE_OR": f"python main.py sed 's/a|o/X/' {F}/a.txt",
    # 第 6 步：& 与修饰符
    "AMP": f"python main.py sed 's/a/&b/' {F}/a.txt",
    "MOD": f"python main.py sed 's/a/\\Uab/' {F}/a.txt",
    # 第 7 步：a / i / c
    "APPEND": f"python main.py sed '1a\\inserted' {F}/a.txt",
    "INSERT": f"python main.py sed '1i\\prepended' {F}/a.txt",
    "CHANGE": f"python main.py sed '1c\\changed' {F}/a.txt",
    "AN": f"python main.py sed -n '1a\\APPENDED' {F}/a.txt",
    # 第 8 步：跳转与多行
    "JUMP": f"python main.py sed -n -f {F}/jump.sed {F}/a.txt",
    "NCMD": f"python main.py sed -n 'N;s/\\n/-/;p' {F}/a.txt",
    # 第 9 步：y
    "Y": f"python main.py sed 'y/abc/xyz/' {F}/a.txt",
    # 第 10 步：多文件与 -s
    "MULTI": f"python main.py sed -n '=' {F}/m1.txt {F}/m2.txt",
    "SEP": f"python main.py sed -n -s '=' {F}/m1.txt {F}/m2.txt",
    # 第 11 步：多条 -e、标准输入、末行无换行
    "EE": f"python main.py sed -e 's/a/b/' -e 's/b/c/' {F}/a.txt",
    "STDIN": "printf 'alpha\\nbravo\\n' | python main.py sed 's/a/b/'",
    "NONL": f"python main.py sed 's/no/NOT/' {F}/nonl.txt",
    # 第 12 步：MSYS 路径改写
    "SLASH": f"python main.py sed -n '/bravo/p' {F}/a.txt",
    "SLASH_OK": f"python main.py sed -n '\\|bravo|p' {F}/a.txt",
    "SLASH_OK2": f"MSYS_NO_PATHCONV=1 python main.py sed -n '/bravo/p' {F}/a.txt",
    "DELIM_BAD": f"python main.py sed -n '\\|bravo\\|p' {F}/a.txt",
    "PCT_BAD": f"python main.py sed -n '%bravo%p' {F}/a.txt",
    # 第 13 步：编码、CRLF、-z
    "GBK": f"python main.py sed 's/一/ONE/' {F}/gbk.txt",
    "GNU_GBK": f"sed 's/一/ONE/' {F}/gbk.txt | cat -v",
    "CRLF": f"python main.py sed 's/one/1/' {F}/crlf.txt",
    "BIN": f"python main.py sed -b 's/one/1/' {F}/crlf.txt",
    "Z": f"python main.py sed -z 's/^b/X/' {F}/nul.txt | python main.py cat -v",
    "NOZ": f"python main.py sed 's/^b/X/' {F}/nul.txt | python main.py cat -v",
    # 第 14 步：原地修改
    "INPLACE": f"python main.py sed --in-place 's/a/A/g' {F}/ip.txt",
    "INPLACE_SHOW": f"python main.py cat {F}/ip.txt",
    "INPLACE_BAK": f"python main.py sed --in-place-suffix=.bak 's/a/A/g' {F}/ip2.txt",
    "INPLACE_BAK_SHOW": f"python main.py cat {F}/ip2.txt.bak",
    "I_SHORT": f"python main.py sed -i 's/a/A/g' {F}/ip2.txt",
    # 第 15 步：错误路径
    "ERR1": f"python main.py sed 'nosuchcmd' {F}/a.txt",
    "ERR2": f"python main.py sed 'h' {F}/a.txt",
    "ERR3": f"python main.py sed 's/a/b' {F}/a.txt",
    "ERR4": f"python main.py sed 's/a/b/0' {F}/a.txt",
    "ERR5": f"python main.py sed 'y/abc/xy/' {F}/a.txt",
    "ERR6": f"python main.py sed 's/a/b/' {F}/nosuch.txt",
    "ERR7": f"python main.py sed 's/a/b/' {F}",
    "ERR8": "python main.py sed",
    "Q": f"python main.py sed 'q3' {F}/a.txt",
    # 第 16 步：测试
    "TEST_SED": "python -m pytest tests/test_sed.py 2>&1 | tail -1",
    # 第 17 步：与 GNU 对拍
    "STAR_OURS": f"python main.py sed 's/^*/X/' {F}/star.txt",
    "STAR_GNU": f"sed 's/^*/X/' {F}/star.txt",
    "TILDE_OURS": f"python main.py sed -n '2,~3p' {F}/u.txt",
    "TILDE_GNU": f"sed -n '2,~3p' {F}/u.txt",
    "STEP_OURS": f"python main.py sed -n '1~0p' {F}/u.txt",
    "STEP_GNU": f"sed -n '1~0p' {F}/u.txt",
}

OUT: dict[str, str] = {}


def capture_all() -> None:
    for key, cmd in CMDS.items():
        code, out = t12.run_in_shell(cmd, timeout=120)
        # pytest 的耗时每次跑都不一样，文档里统一写成 <T>
        out = re.sub(r"\bin \d+\.\d+s\b", "in <T>s", out)
        OUT[key] = out
        print(f"  {key:<18} 退出码 {code}  {len(out)} 字符")


TEMPLATE = r'''# w2l/commands/sed.py — 地址语义与正则翻译

`w2l/commands/sed.py` 有 1390 行，是 `w2l/commands/` 下最长的一个指令实现（第二名 `tail.py` 是 1140 行）。它要在一个流式文本编辑器里同时装下三样东西：**脚本解析**（把一串字符切成一条条命令）、**地址求值**（判定当前行该不该被处理）、**正则翻译**（把 GNU 的 BRE/ERE 方言翻成 Python 的 `re` 认得的写法）。

三样里最容易误解的是地址。sed 的地址不是布尔值，是个小状态机：`2,3` 这种范围要记住「现在在不在范围里」，`/re/,/re2/` 的终点往往要在起点之后好几行才命中，`first~step` 又是另一套步进逻辑。写错了不会报错，只会安静地少打几行。

本轮实测查出**三处本实现与 GNU sed 4.9 的行为差异**，另有一处**`-i` 在真实命令行入口上不可用**（属源码范围，本轮只记录不修）。都列在最后两节。

## 为什么这么创建

### 决定一：默认输出整行，`-n` 才静音

GNU sed 的默认行为是「每处理一行就自动打印一行」。本实现把它放进引擎：`sed()` 第 1284 行建引擎时把 `args.quiet` 传进去，引擎每处理完一行、只要没有指令主动打断循环，就自动写一行。

所以 `-n` 不是「过滤输出」，而是「关掉自动打印」。副作用是 `a`/`i`/`c`/`=` 这几条指令在 `-n` 下**照样有输出**——它们是主动写的，不走自动打印那条路。这与 GNU 一致。

### 决定二：默认方言是 BRE，`-r` 才切 ERE

GNU sed 默认基本正则（BRE），`-r`/`-E` 切扩展正则（ERE）。本实现在 `_compile`（第 295~302 行）里按 `self.extended` 分岔：

```python
    source = _translate_posix_classes(pattern)
    if not self.extended:
        source = _translate_bre(source)
    try:
        return re.compile(source, re.MULTILINE)
    except re.error as exc:
        raise UsageError(f"无效的正则表达式 '{pattern}': {exc}") from exc
```

**ERE 模式下不做任何翻译**，直接交给 Python 的 `re`——Python 的 `re` 本来就是 ERE 语义，正好省事。BRE 模式下先跑 `_translate_posix_classes`（把 `[[:alpha:]]` 换成等价字符范围），再跑 `_translate_bre`（把 BRE 方言翻成 Python 方言）。

代价是 BRE 与 ERE 的差别全靠「翻译」这一层兜住。翻译规则写漏一条，就是一处不一致——最后一节第 1 处差异就是这么来的。

### 决定三：地址编译成一个对象，判定时才求值

`_Address`（第 59~65 行）只有五个字段：

```python
@dataclass
class _Address:
    kind: str  # line / last / regex / step / plus / tilde
    number: int = 0
    regex: re.Pattern[str] | None = None
    step: int = 0
```

`kind` 决定怎么求值：行号（`line`）、末行（`last`）、正则（`regex`）、首地址步进（`step`）、相对行数（`plus`）、范围终点步进（`tilde`）。

**地址不是布尔，是有状态的**。范围地址要记住「已经进范围了吗」「范围从第几行开始的」「终点匹配过几次」，这三个状态存在 `_Command` 里（第 95~99 行）：

```python
    # 范围状态：每条指令各自维护
    in_range: bool = False
    end_line: int = 0
    base_line: int = 0
    matches: int = 0
```

「每条指令各自维护」这句是重点：两条命令各有自己的范围状态，互不干扰。GNU 也是这个语义。

### 决定四：范围终点分四类，各有各的算法

`_match_range`（第 832~860 行）把范围终点分成几种情况：

| 终点 | 写法 | 判定 |
|---|---|---|
| 行号 | `2,5p` | 数字终点在**起始行就命中**（第 846 行） |
| 相对行数 | `2,+3p` | 终点行号 = 起始行号 + N（第 843~844 行） |
| 正则 | `/a/,/b/p` | 正则终点**不在同一行上试**（GNU 行为） |
| 步进 | `2,~3p` | `_tilde_reached` 单独一套算法（第 862~875 行） |

「正则终点不在同一行上试」是 GNU 的规定：`/a/,/a/` 这种起止同一个模式，起点行不会同时当终点，所以范围至少跨两行。

`plus` 终点在起始行就成立（第 846 行的判断只针对 `line`），所以 `2,+2p` 是第 2、3、4 行三行。

### 决定五：BRE 靠翻译，不靠改引擎

`_translate_bre`（第 589~633 行）是本文件最需要小心的一段。规则是：

| BRE 写法 | 含义 | 翻译成 |
|---|---|---|
| `\(` `\)` | 分组 | `(` `)` |
| `\|` | 或 | `\|` |
| `\{` `\}` | 区间 | `{` `}` |
| `\+` `\?` | 量词 | `+` `?` |
| `(` `)` `{` `}` `\|` `+` `?`（不转义） | 字面量 | 加反斜杠转义 |
| 行首或分组之后的 `*` | 字面量 | `\*` |
| `\<` `\>` | 词边界 | `\b` |

实现是**逐字符扫**的（不是正则替换），因为要判断「这个 `*` 前面是不是分组结束」——变量 `after_group` 记的就是这个：

```python
    after_group = True  # 下一个 * 是否为字面量
    ...
        if char == "*" and after_group:
            out.append(r"\*")
            after_group = False
            index += 1
            continue
```

`after_group` 初始为 `True`，所以**表达式开头的 `*` 也算字面量**。它只在「刚处理完 `(` 或 `\(`」时才被置回 `True`（第 608 行 `after_group = nxt in _BRE_GROUP_OPENERS`）。**锚点 `^` `$` 之后不会置 `True`**——落到第 630~631 行那条默认分支上。这就是最后一节第 1 处差异的根因。

### 决定六：编码靠「文本可信度打分」，不靠「第一个能解的」

`_detect_encoding`（第 1109~1127 行）与 `cat.py` 同一套思路：先嗅探前 8192 字节（`_SNIFF_SIZE`），含 NUL 直接判 latin-1（按字节处理），否则挨个候选编码解码后打分（`_text_score`），**得分最高**的胜出。

打分规则（第 1090~1106 行）：ASCII 可打印字符 1.0 分，CJK 汉字 3.0 分，中文标点与全角 1.0 分，制表换行回车 0.5 分，其余高位字节 0.2 分。`_SCORE_MARGIN = 0.3` 是「换编码要领先这么多分才换」，防的是两个编码平分时来回跳。

为什么不能取「第一个能解的」：英文 Windows 的系统首选编码是 cp1252，它几乎不报错，能把 GBK 字节解成乱码，按顺序取第一个可解码的会让中文内容彻底搜不到。

**代价是输出被统一成 UTF-8**：GBK 文件读进来解码成 Unicode，再按 UTF-8 写出。GNU 是字节透传。这是项目一贯的取舍（`cat`、`tail` 都这样）。

### 决定七：原地修改走「临时文件 + 原子替换」

`_process_in_place`（第 1353~1365 行）：

```python
    payload = "".join(collected)
    if suffix:
        backup = path.with_name(path.name + suffix)
        backup.write_bytes(path.read_bytes())
    temporary = path.with_name(path.name + ".w2l-sed.tmp")
    temporary.write_bytes(payload.encode(encoding, errors="replace"))
    os.replace(temporary, path)
```

先写同目录的临时文件，再 `os.replace` 换名——Windows 上 `os.replace` 是原子的，中途崩了不会把原文件写成半截。备份文件是**原文件的字节拷贝**（`path.read_bytes()`），不是改之前的内容。

### 决定八：不支持的指令明确报错，不静默忽略

`_UNSUPPORTED_COMMANDS` 里的 15 条指令（`P D h H g G x l r R w W e z F`）在解析阶段就报错：

```python
        if name in _UNSUPPORTED_COMMANDS:
            raise UsageError(f"暂不支持 sed 指令 {name}（{_UNSUPPORTED_COMMANDS[name]}）")
```

「静默忽略」是流式文本编辑器最坏的失败方式——用户以为改了，其实没改。

## 这个文件是做什么

它是 `w2l/commands/` 下的一个指令实现，1390 行，职责边界是：**按一段 sed 脚本流式改写文本**。

### 数据流

```
sed()                      第 1266~1334 行  入口：定脚本来源、分文件/拼流、跑引擎
├ _ScriptParser            第 123 行        把脚本切成命令序列
│ ├ _parse_address()       第 228~252 行    解析一条地址
│ ├ _parse_regex_address() 第 254~271 行    解析正则地址（分隔符任意）
│ ├ _read_delimited()      第 273~293 行    读到未转义的分隔符为止
│ ├ _compile()             第 295~302 行    编译正则（BRE 先翻译）
│ ├ _parse_payload()       第 306~337 行    按指令名分派参数解析
│ ├ _parse_substitution()  第 339 行        解析 s 命令
│ └ _parse_replacement()   第 466 行        解析替换串（&、\1、\U 等）
├ _translate_posix_classes() 第 579~586 行  POSIX 字符类 → 字符范围
├ _translate_bre()         第 589~633 行    BRE → Python 正则
├ _Engine                  第 726 行        执行引擎
│ ├ _match_range()         第 832~860 行    范围地址求值
│ ├ _tilde_reached()       第 862~875 行    ,~step 的步进判定
│ ├ _match_address()       第 877~895 行    单条地址求值
│ ├ _execute()             第 899 行        执行一条指令
│ ├ _do_substitute()       第 970 行        s 命令
│ └ _replace_nth()         第 1031 行       只换第 N 个匹配
├ _expand()                第 1043 行       展开 & 与反向引用
├ _detect_encoding()       第 1109~1127 行  嗅探编码
├ _text_score()            第 1090~1106 行  文本可信度打分
├ _read_file_lines()       第 1147~1161 行  读文件 + 定编码 + 文本模式去 CR
├ build_parser()           第 1181~1218 行  命令行选项
├ split_inplace()          第 1221 行       把 -i 从短选项簇里拆出来
└ _process_in_place()      第 1353~1365 行  临时文件 + 原子替换
```

### 选项清单

命令行共 24 个选项串（含别名），按用途分组：

| 选项 | 作用 |
|---|---|
| `-e SCRIPT` | 追加一段脚本，可给多次 |
| `-f FILE` | 从文件读脚本，可给多次 |
| `-n` | 不自动打印每一行 |
| `-r` / `-E` | 用 ERE，默认 BRE |
| `-s` | 每个文件单独处理，不拼成一条流 |
| `--in-place` | 原地修改文件 |
| `--in-place-suffix SUFFIX` | 原地修改时留备份后缀 |
| `-b` | 二进制模式，保留行尾 CR |
| `-z` | 用 NUL 而不是换行分隔输入行 |
| `--follow-symlinks` | 原地修改时跟随符号链接（Windows 上无效） |
| `--unbuffered` / `-u` | 少缓冲地读写（接受但不改变行为） |
| `--posix` | POSIX 模式（接受但不改变行为） |
| `--debug` | 打印执行注解（接受但不改变行为） |
| `--sandbox` | 沙箱模式（接受但不改变行为） |

后四个是「占位选项」：GNU 有、项目**接受但不实现**，写了不报错也不改变行为。留着它们是为了让 GNU 脚本原样搬过来时不炸。

### 退出码

| 码 | 什么时候 |
|---|---|
| 0 | 正常结束 |
| 2 | 用法错误或运行错误：脚本没闭合、未知指令、正则非法、文件不存在、目录当文件用 |
| 其他 | 由脚本里的 `q N` 指定（`q3` → 退出码 3），`q` 不带数字则是 0 |

sed 没有「无结果返回 1」的语义，本实现也没有——退出码 1 只会由脚本自己写的 `q1` 产生。

## 有什么用

- **批量改文本**。`sed 's/old/new/g' file` 是最常用的一条。
- **只读筛选**。`-n '/pattern/p'` 把匹配的行挑出来；`grep` 不擅长「只按行号取」这类事，`sed` 可以。
- **按行改**。`sed '2,5d'`、`sed '1i\...'`、`sed -n '2,+3p'` 这类按行号操作，用 `awk` 更笨重。
- **照抄的设计**。三个值得搬走：**地址是有状态的判定而不是布尔**、**BRE 靠逐字符翻译成目标方言**、**原地修改用临时文件 + 原子替换**。

## 怎么用（过程教程）

### 第 1 步：准备演示夹具

后面的例子全部用固定夹具，不用项目源码。理由是源码会变：拿 `w2l/commands/sed.py` 当例子，源码一改教程里写死的预期输出就全过期了。

```bash
cd E:\1\NULL\Windows-to-Linux
python AI/脚本/_t1010_make_sed_fixture.py
```

预期输出：

```
@@FIXTURE@@
```

夹具在 `AI/数据/sed_demo/`，这个目录在 `.gitignore` 里，不进仓库。

主力语料 `a.txt` 是五行英文、每行一个单词：

```
alpha
bravo
charlie
delta
echo
```

`u.txt` 每行内容唯一（L1~L8），含 `X` 的是第 2/4/6 行——范围地址到底覆盖了哪几行，看输出就知道，不用猜。

### 第 2 步：最基础的三种替换

`s/re/repl/` 不带 `g` 时只换每行的第一个匹配：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 's/a/b/' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@S1@@
```

带 `g` 则换光这一行所有匹配：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 's/a/b/g' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@S2@@
```

第三个标志是「只换第 N 个匹配」：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 's/a/A/2' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@S3@@
```

`2` 指**这一行里的第 2 个匹配**，不是第 2 行。

还有一个 `I` 标志（忽略大小写）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 's/a/A/I' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@S4@@
```

### 第 3 步：`-n` 与地址

`-n` 关掉自动打印，只留下指令主动写出来的东西：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -n '\|bravo|p' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@S5@@
```

**注意地址的分隔符写法**：`\|bravo|p` 是「分隔符用 `|`、内容是 `bravo`」。

- `\|bravo|p` ✅ 正确
- `\|bravo\|p` ❌ 错：结尾那个 `\|` 是「转义的分隔符」，会被当成字面量，于是找不到收尾的分隔符
- `/bravo/p` ⚠️ 在 Git Bash 里会被 MSYS 改写成路径，见第 12 步

行号地址：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -n '2p' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@S6@@
```

### 第 4 步：范围地址

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -n '2,3p' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@S7@@
```

相对行数终点 `+N`：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -n '2,+2p' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@S8@@
```

`+2` 的意思是「从起点往后数 2 行」，所以是第 2、3、4 行三行。

正则终点（`/echo/` 是文件最后一行）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -n '\|bravo|,/echo/p' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@S9@@
```

两个地址也可以用同一个分隔符：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -n '\|bravo|,\|echo|p' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@S9B@@
```

起点写 `0` 表示「第一行之前」，所以范围从第 1 行开始：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -n '0,/echo/p' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@S10@@
```

**正则终点不在起始行上试**——起止用同一个模式时，范围至少跨两行：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'a\na\nb\n' | python main.py sed -n '\|a|,\|a|p'
```

预期输出：

```
@@RANGE_SAME@@
```

第 1 行是起点，但终点要等下一行才试，所以范围是第 1~2 行（GNU 同样给这两行）。

### 第 5 步：BRE 与 ERE 的差别（最容易踩的一步）

**BRE（默认）里 `(` `)` `|` 都是字面量**，要分组必须转义：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 's/\(a\)\(l\)/\2\1/' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@BRE_GRP@@
```

同一个意思用 ERE 写（`-r`）就不转义：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -r 's/(a)(l)/\2\1/' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@ERE_GRP@@
```

不转义的括号在 BRE 里是字面量，所以匹配不到东西：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 's/(a)/X/' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@BRE_PAREN@@
```

裸竖线同理：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 's/a|o/X/' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@BRE_OR@@
```

**这两个命令不报错、退出码 0，只是原样输出**——BRE 方言用错最典型的表现。

### 第 6 步：替换串里的 `&` 与修饰符

`&` 代表「匹配到的那一段」：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 's/a/&b/' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@AMP@@
```

大小写修饰符 `\U`（转大写）、`\L`（转小写）、`\u`（首字母大写）、`\l`（首字母小写）、`\E`（结束修饰）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 's/a/\Uab/' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@MOD@@
```

### 第 7 步：`a` / `i` / `c` 与 `-n`

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed '1a\inserted' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@APPEND@@
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed '1i\prepended' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@INSERT@@
```

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed '1c\changed' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@CHANGE@@
```

`-n` 下 `a` 照样输出（主动写的，不走自动打印）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -n '1a\APPENDED' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@AN@@
```

### 第 8 步：跳转与多行

跳转靠标签：`b` 无条件跳、`t` 替换成功才跳、`:name` 定义标签。多行脚本用 `-f` 从文件读（命令行里塞多行脚本不方便）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -n -f AI/数据/sed_demo/jump.sed AI/数据/sed_demo/a.txt
```

预期输出：

```
@@JUMP@@
```

`jump.sed` 的内容是：

```
/bravo/{
s/a/X/
t end
}
p
:end
```

读法：遇到含 `bravo` 的行先把 `a` 换成 `X`，替换成功就跳到 `:end`（不打印）；其他行照常 `p` 打印。所以 `bravo` 那行不见了。

`N` 把下一行接进模式空间：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -n 'N;s/\n/-/;p' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@NCMD@@
```

### 第 9 步：`y` 转写

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 'y/abc/xyz/' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@Y@@
```

`y` 是逐字符替换，两个串必须一样长，否则报错（见第 15 步）。

### 第 10 步：多文件与 `-s`

默认把多个文件拼成一条流，行号连续：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -n '=' AI/数据/sed_demo/m1.txt AI/数据/sed_demo/m2.txt
```

预期输出：

```
@@MULTI@@
```

`-s` 让每个文件各算各的行号：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -n -s '=' AI/数据/sed_demo/m1.txt AI/数据/sed_demo/m2.txt
```

预期输出：

```
@@SEP@@
```

### 第 11 步：多条 `-e`、标准输入、末行无换行

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -e 's/a/b/' -e 's/b/c/' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@EE@@
```

两段脚本按顺序作用在同一个模式空间上。

读标准输入：

```bash
cd E:\1\NULL\Windows-to-Linux
printf 'alpha\nbravo\n' | python main.py sed 's/a/b/'
```

预期输出：

```
@@STDIN@@
```

末行没有换行符时，输出也不补：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 's/no/NOT/' AI/数据/sed_demo/nonl.txt
```

预期输出：

```
@@NONL@@
```

### 第 12 步：Git Bash 里的路径改写坑（实操最容易翻车的一步）

在 Git Bash（MSYS2）里，**以 `/` 开头的参数会被自动改写成 Windows 路径**。`python` 是原生 Windows 程序，躲不掉：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -n '/bravo/p' AI/数据/sed_demo/a.txt
```

预期输出（退出码 2）：

```
@@SLASH@@
```

`/bravo/p` 被改写成了 `E:/Program Files/Git/bravo/p` 之类的东西，sed 拿到脚本的第一个字符是 `E`，于是报「未知的 sed 指令 'E'」。

**解法一：换分隔符**（推荐，跨 shell 都对）：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -n '\|bravo|p' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@SLASH_OK@@
```

**解法二：关掉路径改写**：

```bash
cd E:\1\NULL\Windows-to-Linux
MSYS_NO_PATHCONV=1 python main.py sed -n '/bravo/p' AI/数据/sed_demo/a.txt
```

预期输出：

```
@@SLASH_OK2@@
```

顺带看一眼「两边都转义」那种写法错在哪：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -n '\|bravo\|p' AI/数据/sed_demo/a.txt
```

预期输出（退出码 2）：

```
@@DELIM_BAD@@
```

换分隔符的规则是「**转义的开头 + 不转义的结尾**」，而且开头必须是转义形式。裸的 `%re%` 不行：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -n '%bravo%p' AI/数据/sed_demo/a.txt
```

预期输出（退出码 2）：

```
@@PCT_BAD@@
```

GNU 也一样不认 `%re%`（报 `unknown command: %'`），要写就写 `\%re%`。

### 第 13 步：编码、CRLF 与 `-z`

GBK 文件：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 's/一/ONE/' AI/数据/sed_demo/gbk.txt
```

预期输出：

```
@@GBK@@
```

本实现按 GBK 解码、按 UTF-8 输出，所以中文能正常替换、输出也是 UTF-8。GNU 是字节透传，同一条命令给 GNU 跑：

```bash
cd E:\1\NULL\Windows-to-Linux
sed 's/一/ONE/' AI/数据/sed_demo/gbk.txt | cat -v
```

预期输出：

```
@@GNU_GBK@@
```

那串 `M-` 记号就是原始 GBK 字节。两边的**文件内容**其实一样，差别只在**本实现多做了一次「解码 + 重新编码」**。

CRLF 文件在文本模式下会被去掉行尾的 CR：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 's/one/1/' AI/数据/sed_demo/crlf.txt
```

预期输出：

```
@@CRLF@@
```

`-b` 二进制模式保留 CR：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -b 's/one/1/' AI/数据/sed_demo/crlf.txt
```

预期输出：

```
@@BIN@@
```

`-z` 用 NUL 而不是换行分隔输入行：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -z 's/^b/X/' AI/数据/sed_demo/nul.txt | python main.py cat -v
```

预期输出：

```
@@Z@@
```

不加 `-z` 时整个文件是一行，`^b` 匹配不上：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 's/^b/X/' AI/数据/sed_demo/nul.txt | python main.py cat -v
```

预期输出：

```
@@NOZ@@
```

（`cat -v` 把 NUL 显示成 `^@`。）

### 第 14 步：原地修改

`--in-place`：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed --in-place 's/a/A/g' AI/数据/sed_demo/ip.txt
```

这一步没有输出，退出码 0，文件已被改写。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat AI/数据/sed_demo/ip.txt
```

预期输出：

```
@@INPLACE_SHOW@@
```

`--in-place-suffix=.bak` 留一份备份：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed --in-place-suffix=.bak 's/a/A/g' AI/数据/sed_demo/ip2.txt
```

这一步没有输出，退出码 0。

备份文件是**改动前**的字节：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py cat AI/数据/sed_demo/ip2.txt.bak
```

预期输出：

```
@@INPLACE_BAK_SHOW@@
```

**`-i` 短选项在真实命令行入口上不可用**：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -i 's/a/A/g' AI/数据/sed_demo/ip2.txt
```

预期输出（退出码 2）：

```
@@I_SHORT@@
```

原因在 `w2l/cli.py` 第 82~83 行：命令行参数直接交给 `parser.parse_args(argv[1:])`，**没走 `split_inplace()` 的改写**；而 `build_parser()` 里也只注册了 `--in-place` / `--in-place-suffix`，没有 `-i`。

`split_inplace()`（第 1221 行）其实已经把 `-i` 拆得挺好（`-ni`、`-i.bak` 都认），只是真实入口没调用它。项目里 `du.py` 的 `_DuParser`（第 117 行起）就是现成的解法参照：继承 `argparse.ArgumentParser` 覆写 `parse_known_args`，让 CLI 路径也能吃到改写。

### 第 15 步：错误路径与退出码

未知指令：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 'nosuchcmd' AI/数据/sed_demo/a.txt
```

预期输出（退出码 2）：

```
@@ERR1@@
```

不支持的指令：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 'h' AI/数据/sed_demo/a.txt
```

预期输出（退出码 2）：

```
@@ERR2@@
```

脚本没闭合：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 's/a/b' AI/数据/sed_demo/a.txt
```

预期输出（退出码 2）：

```
@@ERR3@@
```

匹配序号为 0：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 's/a/b/0' AI/数据/sed_demo/a.txt
```

预期输出（退出码 2）：

```
@@ERR4@@
```

`y` 两个串长度不同：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 'y/abc/xy/' AI/数据/sed_demo/a.txt
```

预期输出（退出码 2）：

```
@@ERR5@@
```

文件不存在：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 's/a/b/' AI/数据/sed_demo/nosuch.txt
```

预期输出（退出码 2）：

```
@@ERR6@@
```

目录当文件用：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 's/a/b/' AI/数据/sed_demo
```

预期输出（退出码 2）：

```
@@ERR7@@
```

不给脚本：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed
```

预期输出（退出码 2）：

```
@@ERR8@@
```

`q N` 能指定退出码：

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 'q3' AI/数据/sed_demo/a.txt
```

预期输出（退出码 3）：

```
@@Q@@
```

`q3` 在第一行就退出，所以只打了第一行。

### 第 16 步：跑相关测试

```bash
cd E:\1\NULL\Windows-to-Linux
python -m pytest tests/test_sed.py 2>&1 | tail -1
```

预期输出（耗时每次不同，用 `<T>` 占位）：

```
@@TEST_SED@@
```

`tests/test_sed.py` 有 44 个用例，覆盖正常路径、选项组合、错误路径三块。注意命令末尾的 `| tail -1`：本项目的 `pyproject.toml` 里 `addopts = "-q"`，`pytest -q` 的输出被压成一行进度条，看不到用例数。

### 第 17 步：与 GNU sed 4.9 对拍

本机有 GNU sed 4.9（Git Bash 自带），三处差异都是实测出来的，不是推测。

**差异 1：BRE 里锚点后跟 `*`**。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed 's/^*/X/' AI/数据/sed_demo/star.txt
```

预期输出（退出码 2）：

```
@@STAR_OURS@@
```

GNU 跑同样这条：

```bash
cd E:\1\NULL\Windows-to-Linux
sed 's/^*/X/' AI/数据/sed_demo/star.txt
```

预期输出：

```
@@STAR_GNU@@
```

**差异 2：范围终点 `,~N`**。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -n '2,~3p' AI/数据/sed_demo/u.txt
```

预期输出：

```
@@TILDE_OURS@@
```

GNU 跑同样这条：

```bash
cd E:\1\NULL\Windows-to-Linux
sed -n '2,~3p' AI/数据/sed_demo/u.txt
```

预期输出：

```
@@TILDE_GNU@@
```

**差异 3：首地址 `1~0`（步长为 0）**。

```bash
cd E:\1\NULL\Windows-to-Linux
python main.py sed -n '1~0p' AI/数据/sed_demo/u.txt
```

预期输出：

```
@@STEP_OURS@@
```

GNU 跑同样这条：

```bash
cd E:\1\NULL\Windows-to-Linux
sed -n '1~0p' AI/数据/sed_demo/u.txt
```

预期输出：

```
@@STEP_GNU@@
```

### 实测出的与 GNU sed 4.9 的三处差异

#### 第 1 处：BRE 里锚点后跟 `*`，本实现比 GNU 严格

**现象**：GNU 把 `^*` 当成「行首这个锚点，重复 0 次以上」，等价于匹配行首的空位置，于是 `s/^*/X/` 能给每行开头插一个 `X`；本实现直接报「无效的正则表达式」。

**根因**：`_translate_bre`（第 589~633 行）的 `after_group` 标志。它初始为 `True`（表达式开头的 `*` 算字面量），处理完 `\(` 或 `(` 之后被置回 `True`，**但处理完 `^` `$` 之后不会**——落到第 630~631 行那条默认分支上。

于是 `^*` 翻译成 `^*`，Python 的 `re` 认为「`^` 后面没有可重复的东西」，报 `nothing to repeat`。

**GNU 怎么做的**：GNU 的 BRE 语法（`RE_SYNTAX_POSIX_BASIC`）允许锚点后跟重复符，两边都按字面锚点处理。

**影响面**：只在 BRE 下出现。`-r`（ERE）模式下两边都报「Invalid preceding regular expression」，行为一致。

**修法方向**：在 `_translate_bre` 里把锚点也算成「可以让 `*` 跟着」的位置，但译出来的还得跟 GNU 的语义对齐，不能只是把 `^` 变成 `(^)*` 就完事。

#### 第 2 处：范围终点 `,~N` 的取模算法不同

**现象**：`2,~3p` 在 GNU 下覆盖第 2~3 行，本实现覆盖第 2~5 行。

**根因**：两边算法完全不同。

GNU 上游 `execute.c` 的 `ADDR_IS_STEP_MOD` 分支（第 871~874 行）：

```
end = start + step - (start % step)
```

即「终点 = 起点往后 step 行，但先按 step 对齐」。start=2、step=3 → `2 + 3 - (2 % 3)` = `2 + 3 - 2` = 3 ⇒ 范围是第 2~3 行。

本实现 `_tilde_reached`（第 862~875 行）走的是「起点是行号时按行号差取模」：

```python
        offset = source.number - command.base_line
        return offset > 0 and offset % step == 0
```

offset=3 时 `3 % 3 == 0` 成立 ⇒ 范围一直延到第 5 行。

**修法方向**：把 `_tilde_reached` 的行号分支换成 GNU 的 `end = start + step - (start % step)`；起点是正则时也要另算一套（现在用的是「数匹配次数」，与 GNU 不同）。

#### 第 3 处：首地址 `1~0`（步长为 0）的退化行为不同

**现象**：GNU 把 `1~0` 当成普通的行号地址（只打第 1 行），本实现当成「步长 1」，打出了全部 8 行。

**根因**：`_match_address` 的 `step` 分支（第 887~894 行）用 `max(address.step, 1)` 兜底，步长 0 被当成 1。GNU 在步长为 0 时直接退化成普通行号地址。

#### 另有：`-i` 短选项在真实 CLI 入口上不可用

这不是与 GNU 的语义差异，是**本实现的缺陷**：`split_inplace()` 能拆 `-i`，但 `w2l/cli.py` 第 82~83 行的真实入口没调用它，`build_parser()` 也没注册 `-i`。第 14 步有实测。

属源码范围（`w2l/`、`README.md`），本轮按只读原则没改。

### 常见疑问

**Q：为什么 `sed 's/(a)/X/'` 什么都不换？**

BRE 里 `(` 是字面量，匹配的是字面的 `(a)`。要么转义成 `\(`，要么加 `-r` 切 ERE。

**Q：为什么地址要写成 `\|bravo|p` 而不是 `/bravo/p`？**

两个原因：一是 `/bravo/p` 在 Git Bash 里会被 MSYS 改写成路径；二是 `\|bravo\|p` 这种「两边都转义」的写法是错的——结尾的 `\|` 是转义的分隔符，会被当成字面量，然后报「命令没有闭合」。正确写法是**结尾用不转义的分隔符**：`\|bravo|p`。

**Q：那换分隔符到底怎么写？**

开头转义、结尾不转义：`\|re|`、`\%re%`、`\#re#` 都认（GNU 也认）。不认的有两种：结尾也转义的 `\|re\|`（找不到收尾分隔符），以及开头没转义的裸符号（`%re%` 里的 `%` 会被当成指令字符）。

**Q：`sed` 和 `awk` 怎么选？**

按行号、按行改写、正则替换是 `sed` 的主场；按字段切列、算术、多条件分支是 `awk` 的主场。粗略地说：**一行当一个整体改 → sed；一行拆成几段算 → awk**。

**Q：为什么 `sed` 读 GBK 文件输出的是 UTF-8？**

因为本实现把文件解码成 Unicode 再输出（编码靠「文本可信度打分」选），GNU 是字节透传。项目里 `cat`、`tail`、`grep` 都是这个口径，跨指令保持一致。

### 相关教程

- `teach/21-w2l-commands-cat.py-编码判定与显示记号.md` — 编码判定与本篇同一套思路（嗅探 + 打分），`cat -v`/`-A` 的记号规则也在这篇
- `teach/24-w2l-commands-find.py-表达式语法与遍历语义.md` — `find` 与 `sed` 常配合：前者找路径，后者按行改
- `teach/22-w2l-commands-wc.py-列宽模型与词数判定.md` — 统计类指令的口径是怎么定的，和本篇的「替换语义」是两类问题
- `teach/13-新增一个指令的完整过程.md` — 新指令怎么加（`build_parser` + `@command` + 测试）
- `teach/17-AGENTS.md-项目守则.md` — 退出码约定（0 成功 / 1 无结果 / 2 用法或运行错误）的出处
'''


def main() -> int:
    print("一、逐条真跑，录下预期输出")
    capture_all()

    text = TEMPLATE
    for key, value in OUT.items():
        token = "@@%s@@" % key
        if token not in text:
            # 有些命令本身没有输出（原地修改那两条），它们只用来改夹具状态。
            # 这时必须确认输出确实是空的，否则就是漏了预期输出块。
            if value.strip():
                raise SystemExit("模板里没有占位符 %s，但这条命令有输出：%r" % (token, value))
            continue
        text = text.replace(token, value)

    leftover = re.findall(r"@@[A-Z_0-9]+@@", text)
    if leftover:
        raise SystemExit("还有没替换的占位符：%s" % leftover)
    if "\ufffd" in text:
        raise SystemExit("正文里混进了坏字符 U+FFFD")

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with open(TARGET, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("[result] 已写入 %s" % TARGET)
    print("[result] %d 字节，%d 行" % (len(text.encode("utf-8")), text.count("\n") + 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
