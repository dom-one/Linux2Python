#!/usr/bin/env python
"""更新 AI/教程进度.md 的状态段、清单与发现段。

用法：
    python AI/脚本/_t1308_update_awk_progress.py

只做「就地替换 + 追加」，不改写历史 tick 日志。
每处替换都断言命中一次，命中数不对就报错退出（防止静默没改上）。
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PROGRESS = ROOT / "AI" / "教程进度.md"

REPLACEMENTS: list[tuple[str, str]] = [
    # 头部
    (
        "最后更新：2026-11-22\n本次会话：cron tick（补充 w2l/commands/sed.py 教程，已完成 28 篇）",
        "最后更新：2026-11-23\n本次会话：cron tick（补充 w2l/commands/awk_lite.py 教程，已完成 29 篇）",
    ),
    # 第 0 节 当前状态
    (
        "- 当前阶段：补 `w2l/commands/` 下新指令的逐文件教程\n- 完成度：28/28",
        "- 当前阶段：补 `w2l/commands/` 下新指令的逐文件教程\n- 完成度：29/29",
    ),
    # 第 1 节 清单：补一行
    (
        "| 28 | `w2l/commands/sed.py` | `27-w2l-commands-sed.py-地址语义与正则翻译.md` | 已完成 |",
        "| 28 | `w2l/commands/sed.py` | `27-w2l-commands-sed.py-地址语义与正则翻译.md` | 已完成 |\n"
        "| 29 | `w2l/commands/awk_lite.py` | `28-w2l-commands-awk_lite.py-字段投影与解析边界.md` | 已完成 |",
    ),
]

FINDINGS = """
<!-- awk-findings:start -->
### 2026-11-23 awk-lite 与 GNU awk 5.3.2 的差异、11 个崩溃输入（本轮实测）

给 `w2l/commands/awk_lite.py` 写教程时，用 Git Bash 自带的 GNU awk 5.3.2 对拍了
82 组用例，23 组不一致。其中**一处是源码缺陷**（属开发任务，本轮按只读原则没动），
其余是实现取舍或语义分歧。

#### 一、源码缺陷：11 个输入让程序抛 Python traceback

`_format_number`（`w2l/commands/awk_lite.py` 第 443~447 行）第 445 行那句
`if number == int(number) and abs(number) < 1e16:`，在值是无穷大或 NaN 时
**先炸在 `int()` 上**（`int(inf)` 抛 OverflowError、`int(nan)` 抛 ValueError）；
而 `_to_number`（第 433~440 行）用的是 Python 的 `float()`，它接受
`inf` / `infinity` / `nan` / `1e400`。异常一路冒到 `main.py` 顶层，
用户看到的是 Python traceback，而不是本项目统一的 `错误: ...` 格式。

| 输入 | 异常 |
|---|---|
| `-v x=inf` / `INF` / `Infinity` / `-inf` / `1e400` | OverflowError |
| `-v x=nan` / `NaN` | ValueError |
| `-v n=inf '{print $n}'` / `-v n=nan '{print $n}'` | OverflowError / ValueError |
| `{print 1e400}` / `{print -inf}` | OverflowError |

GNU awk 对应的输入都不崩（`{print 1e400}` 打 `+inf`，`-v x=inf` 打 `inf`）。
另有一个不对称：`{print inf}` **不崩**，因为 `_parse_item` 先判
`_IDENT.fullmatch(piece)`——`inf` 是合法标识符，被当成变量名，报
「变量 'inf' 没有赋值」；而 `{print -inf}` 里 `-` 不是标识符字符，
落到 `_to_number` 分支才炸。

**修法方向**：`_to_number` 里用 `math.isfinite()` 判一道，无穷大与 NaN 不当数字
（或明确报错）；`_format_number` 里也加同样的保险。

#### 二、16 处与 GNU awk 的行为差异（逐条实测）

| # | 写法 | 本实现 | GNU awk 5.3.2 | 性质 |
|---|---|---|---|---|
| 1 | `{print 10000000000000000}`（1e16） | `1e+16` | `10000000000000000` | 语义分歧 |
| 2 | `{print 100000000000000000000000}`（1e23） | `1e+23` | `99999999999999991611392` | 语义分歧 |
| 3 | `-v x=007 '{print x}'` | `7` | `007` | 语义分歧 |
| 4 | `-v x=1e3 '{print x}'` | `1000` | `1e3` | 语义分歧 |
| 5 | `-v x=1_000 '{print x}'` | `1000` | `1_000` | 语义分歧（Python 的 `float()` 认下划线） |
| 6 | `-F ''` | 当成默认，按空白串切 | **逐字符切**，每字一字段 | 语义分歧 |
| 7 | `-F 'x*'`（能匹配空串的正则） | 报错退出 2 | 接受，NF 恒为 1 | 语义分歧 |
| 8 | `-F';' -v FS=,'` | `-F` 赢 | `-v FS=` 赢（命令行上后者覆盖前者） | 语义分歧 |
| 9 | `{print foo}`（foo 未赋值） | 报错退出 2 | 打印空行 | 有意严格化 |
| 10 | `{print $foo}`（foo 未赋值） | 报错退出 2 | 打印整行 | 有意严格化 |
| 11 | `{print "a" "b"}` | `a" "b` | `ab` | 语义分歧 |
| 12 | `{print $1 "\\t" $2}` | 报错退出 2 | `INFO<TAB>start` | 语义分歧 |
| 13 | 中间文件读不到 | 跳过并继续，最后退 2 | **fatal**，后面的文件不处理 | 有意取舍 |
| 14 | 目录当文件用 | 报错退 2 | 警告后跳过，**退 0** | 有意取舍 |
| 15 | 空程序 `''` | 报错退 2 | 退 0（空程序=没有规则） | 有意取舍 |
| 16 | 语法错误退出码 | 2 | 1 | 约定不同 |

另有两条环境差异（README 已记录）：本实现输出 CRLF（GNU 是 LF，82 组里有 63 组
只差这个），GBK 文件解码成 Unicode 后按 UTF-8 输出（GNU 是字节透传）。

**其中第 8 条与 README 第 590 行附近「`-F` 优先于 `-v FS=...`」的写法冲突**：
README 描述的是本实现的约定，与 GNU 的「后者覆盖前者」不同。属 README 范围。

#### 三、探针自己骗人：MSYS 运行时改写 argv

差分对拍第一版报出一堆「GNU awk 不认 `{print}`」的**假差异**。真相是
**GNU awk 是 MSYS 程序，原生 Windows 程序 spawn 它时，MSYS 运行时会对
未加引号的 argv 元素做花括号展开**（跟 bash 的花括号展开一个道理）：

| 传给 awk 的字符串 | awk 实际收到的 |
|---|---|
| `{print}` | `print` |
| `{print$1}` | `print$1` |
| `a{b}c` | `abc` |
| `{a,b}` | `a`（`b` 变成另一个 argv 元素） |
| `{print $1}` | `{print $1}`（原样） |

规律：**带空格的参数被 Python 的 `subprocess` 加了引号，MSYS 就不动它；
不带空格的裸参数被展开**。`MSYS_NO_PATHCONV=1` 挡不住这个（它管路径转换，
不管花括号展开）。绕法：把程序写进文件，用 `awk -f prog.awk` 传。

**对本项目无影响**：本项目是原生 Windows 程序（`python.exe`），argv 不经 MSYS
运行时，`{print}` 原样到达。**对用户有影响**：从 cmd.exe 直接调 GNU awk，
`awk "{print}" file` 的花括号会被吃掉、awk 报语法错误；同一命令在 Git Bash 里正常。

实测脚本：`AI/脚本/_t1301_probe_awk_diff.py`（82 组对拍，产出
`AI/产物/awk-diff/cases.json`）、`_t1302_probe_msys_braces.py`（argv 改写）、
`_t1303_probe_awk_numbers.py`（数字转字符串分界）、`_t1304_probe_awk_crash.py`
（崩溃面）、`_t1305_probe_awk_cases.py`（查单条用例）、`_t1306_make_awk_demo.py`
（教程夹具）、`_t1307_fix_teach28_paths.py`（教程命令块路径改写）。
逐条结论见 `teach/28` 的「实测出的与 GNU awk 5.3.2 的差异」与
「实测出的崩溃面：11 个输入」两节。

<!-- awk-findings:end -->
"""


def main() -> int:
    text = PROGRESS.read_text(encoding="utf-8")

    for old, new in REPLACEMENTS:
        count = text.count(old)
        if count != 1:
            print(f"替换锚点命中 {count} 次（应为 1），退出：\n{old[:80]}")
            return 1
        text = text.replace(old, new)

    marker = "<!-- awk-findings:end -->"
    if marker in text:
        print("发现段已存在，跳过追加")
        return 1

    anchor = "<!-- sed-findings:end -->"
    if text.count(anchor) != 1:
        print("找不到 sed-findings 锚点，退出")
        return 1
    text = text.replace(anchor, anchor + "\n" + FINDINGS.strip())

    PROGRESS.write_text(text, encoding="utf-8")
    print(f"已更新 {PROGRESS}")
    print(f"当前字节数 {PROGRESS.stat().st_size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
