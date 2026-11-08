"""修 teach/21 草稿里的错误：4 处命令块输出对不上 + 3 处正文数字错 + 小节结构。

用法:
    python AI/脚本/_t105_fix_teach21.py

为什么用脚本改而不是手工编辑:
    这份草稿 1057 行，要改的是「预期输出块」里的字节转储——手敲八进制
    极易错位（一个数字错一位，整行的语义就变了）。所以每处替换都按
    唯一长串精确匹配，匹配不到就报错退出，绝不静默跳过。

改完先写 .preview 并断言，再 os.replace 覆盖原文件（不直接覆盖）。

核对器报的 4 处与根因:
    块 #12  cat -E w2l/errors.py
        文档每行结尾少写了两个引号。源码里是三引号开头三引号结尾，
        加 -E 后行尾是三引号加 $，文档写成了单引号加 $。
    块 #30  cat gbk_demo.txt | od -c
        命令与意图不符：管道里的 cat 已经解码过了，看到的是 UTF-8。
        要看源文件原始字节得直接 od 文件本身。
    块 #32  cat gbk_demo.txt | od -c
        八进制转储手抄错了两处：第 16 个字节 254 写成 253，
        且 od 每行 16 字节的换行位置也错了。
    块 #39  cat nope.txt w2l/errors.py
        核对器用 2>&1 合并 stdout 与 stderr，错误信息行排在最前面，
        文档的预期块只列了 stdout。

正文里核对器查不到的三处数字:
    「4 个汉字 + 2 个汉字 = 6 个汉字」→ 实际 4 + 5 = 9 个
    「errors.py 有 9 行，其中 3 行空行」→ 实际 4 行空行
    「-b 的编号是 1、2、3、4」→ 实际编号到 5（非空行只有 5 行）
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "teach" / "21-w2l-commands-cat.py-编码判定与显示记号.md"
PREVIEW = DOC.with_suffix(".md.preview")


def block(*lines: str) -> str:
    return "\n".join(lines)


# --- 替换清单：(说明, 旧串, 新串, 期望命中次数) ---
EDITS: list[tuple[str, str, str, int]] = []


def edit(desc: str, old: str, new: str, count: int = 1) -> None:
    EDITS.append((desc, old, new, count))


# 1) 汉字个数：演示文件是「中文内容」+「第二行内容」，4 + 5 = 9 个汉字
edit(
    "汉字个数 6 -> 9",
    "实测 `AI/数据/gbk_demo.txt`（4 个汉字 + 2 个汉字 = 6 个汉字，GBK 共 20 字节）：",
    "实测 `AI/数据/gbk_demo.txt`（4 个汉字 + 5 个汉字 = 9 个汉字，"
    "GBK 下 9 个汉字占 18 字节，加 2 个换行共 20 字节）：",
)

# 2) errors.py 的空行数：9 行里 4 行空行（不是 3 行）
edit(
    "errors.py 空行数 3 -> 4（决定六）",
    "所以 `w2l/errors.py` 有 9 行，其中 3 行空行，"
    "`-b` 的编号是 1、2、3、4 而不是 1、2、3、4、5、6。",
    "所以 `w2l/errors.py` 有 9 行，其中 4 行空行，"
    "`-b` 的编号是 1、2、3、4、5，而不是 1 到 9。",
)

# 3) errors.py 的空行数：正文那句同样要改
edit(
    "errors.py 空行数 3 -> 4（过程教程）",
    "文件共 9 行、3 行空行，编号只到 5。",
    "文件共 9 行、4 行空行，编号只到 5。",
)

# 4) 字节数换算说明
edit(
    "字节换算 6 个汉字 -> 9 个汉字",
    "源文件 20 字节，输出 29 字节——6 个 GBK 汉字（2 字节）"
    "变成了 6 个 UTF-8 汉字（3 字节）。",
    "源文件 20 字节，输出 29 字节——9 个 GBK 汉字（18 字节）"
    "变成了 9 个 UTF-8 汉字（27 字节），两边各加 2 个换行字节。",
)

# 5) -E 预期块：每行结尾补回两个引号
edit(
    "-E 预期块补回结尾引号",
    block(
        '"""指令执行过程中使用的两类异常。"$',
        "$",
        "$",
        "class UsageError(Exception):$",
        '    """用法错误，退出码 2。"$',
        "$",
        "$",
        "class CommandError(Exception):$",
        '    """指令执行失败，退出码 1。"$',
    ),
    block(
        '"""指令执行过程中使用的两类异常。"""$',
        "$",
        "$",
        "class UsageError(Exception):$",
        '    """用法错误，退出码 2。"""$',
        "$",
        "$",
        "class CommandError(Exception):$",
        '    """指令执行失败，退出码 1。"""$',
    ),
)

# 6) 看源文件原始字节：命令改成直接 od 文件
edit(
    "看原始字节的命令改为直接 od 文件",
    block(
        "然后看它的原始字节：",
        "",
        "```bash",
        "cd E:\\1\\NULL\\Windows-to-Linux",
        "python main.py cat AI/数据/gbk_demo.txt | od -c",
        "```",
    ),
    block(
        "然后看它的原始字节（直接 od 文件，不经过本项目的 cat）：",
        "",
        "```bash",
        "cd E:\\1\\NULL\\Windows-to-Linux",
        "od -c AI/数据/gbk_demo.txt",
        "```",
    ),
)

# 7) 解码后字节的八进制转储：改对字节值与换行位置
edit(
    "解码后 od 转储修正",
    block(
        "0000000 344 270 255 346 226 207 345 206 205 345 256 271  "
        "\\n 347 253 254 344 272 214",
        "0000020 350 241 214 345 206 205 345 256 271  \\n",
        "0000035",
    ),
    block(
        "0000000 344 270 255 346 226 207 345 206 205 345 256 271  "
        "\\n 347 254 254",
        "0000020 344 272 214 350 241 214 345 206 205 345 256 271  \\n",
        "0000035",
    ),
)

# 8) 错误路径：改成 2>&1 合并，并说明为什么错误行在前
edit(
    "错误路径改为 2>&1 合并",
    block(
        "出错不影响其余文件：",
        "",
        "```bash",
        "cd E:\\1\\NULL\\Windows-to-Linux",
        "python main.py cat nope.txt w2l/errors.py",
        "```",
        "",
        "预期输出（退出码 2，错误信息走 stderr，内容照常输出到 stdout）：",
        "",
        "```",
        '"""指令执行过程中使用的两类异常。"""',
        "",
        "",
        "class UsageError(Exception):",
        '    """用法错误，退出码 2。"""',
        "",
        "",
        "class CommandError(Exception):",
        '    """指令执行失败，退出码 1。"""',
        "```",
    ),
    block(
        "出错不影响其余文件——打不开的文件只报错，后面的文件照常输出：",
        "",
        "```bash",
        "cd E:\\1\\NULL\\Windows-to-Linux",
        "python main.py cat nope.txt w2l/errors.py 2>&1",
        "```",
        "",
        "预期输出（退出码 2）：",
        "",
        "```",
        "cat: 无法打开 'nope.txt': No such file or directory",
        '"""指令执行过程中使用的两类异常。"""',
        "",
        "",
        "class UsageError(Exception):",
        '    """用法错误，退出码 2。"""',
        "",
        "",
        "class CommandError(Exception):",
        '    """指令执行失败，退出码 1。"""',
        "```",
        "",
        "错误信息走 stderr、文件内容走 stdout，是两路输出。`2>&1` 把两路"
        "合并成一路后，错误行排在最前面，原因是 **stderr 不缓冲、"
        "而重定向到管道时 stdout 是块缓冲**：stderr 立刻落盘，"
        "stdout 要等进程退出才整体刷出。所以合并重定向时错误行先到。",
    ),
)

# 9) 「相关文件」从第五个二级小节降为三级，并移到「这个文件是做什么」节末尾
RELATED_OLD = block(
    "## 相关文件",
    "",
    "| 文件 | 关系 |",
    "|---|---|",
    "| `w2l/commands/grep.py` | 用同一套编码打分思路，判定口径一致 |",
    "| `w2l/commands/head.py` | 同样的输出流处理（surrogateescape + 非终端关换行翻译），但计数语义不同 |",
    "| `w2l/context.py` | `RunContext` 提供 `cwd` / `stdout` / `stderr` / `stdin` |",
    "| `w2l/registry.py` | `@command` 装饰器，注册 `cat` 指令 |",
    "| `tests/test_cat.py` | 34 个用例，逐条对照 Git Bash 的 GNU cat 输出 |",
    "| `AI/脚本/_t95_probe_cat_tut.py` | 本篇的行为实测脚本 |",
    "| `AI/脚本/_t101_make_gbk_demo.py` | 生成 GBK 演示文件并对比文件路径与 stdin |",
)

RELATED_NEW = block(
    "### 相关文件",
    "",
    "| 文件 | 关系 |",
    "|---|---|",
    "| `w2l/commands/grep.py` | 用同一套编码打分思路，判定口径一致 |",
    "| `w2l/commands/head.py` | 同样的输出流处理（surrogateescape + 非终端关换行翻译），但计数语义不同 |",
    "| `w2l/context.py` | `RunContext` 提供 `cwd` / `stdout` / `stderr` / `stdin` |",
    "| `w2l/registry.py` | `@command` 装饰器，注册 `cat` 指令 |",
    "| `tests/test_cat.py` | 34 个用例，逐条对照 Git Bash 的 GNU cat 输出 |",
    "| `AI/脚本/_t95_probe_cat_tut.py` | 本篇的行为实测脚本 |",
    "| `AI/脚本/_t101_make_gbk_demo.py` | 生成 GBK 演示文件并对比文件路径与 stdin |",
    "| `AI/脚本/_t102_probe_teach21_mismatch.py` | 取证 4 处「预期输出与实际不符」的根因 |",
    "| `AI/脚本/_t103_compute_od_dump.py` | 独立复算 od -c 的八进制转储（自算与 GNU od 互相印证） |",
    "| `AI/脚本/_t104_verify_cat_tut_claims.py` | 复算正文里只有文字佐证、核对器查不到的数字 |",
)


def main() -> int:
    apply = "--apply" in sys.argv
    original = DOC.read_bytes()
    text = original.decode("utf-8")

    # 先把「相关文件」整节摘出来
    if text.count(RELATED_OLD) != 1:
        print("中止：找不到唯一的「相关文件」小节，无法移动")
        return 1
    text = text.replace(RELATED_OLD + "\n", "", 1)

    # 插到「## 有什么用」之前，变成「这个文件是做什么」下的三级小节
    anchor = "## 有什么用"
    if text.count(anchor) != 1:
        print("中止：找不到唯一的「## 有什么用」锚点")
        return 1
    text = text.replace(anchor, RELATED_NEW + "\n\n" + anchor, 1)

    # 逐条替换
    for desc, old, new, expect in EDITS:
        found = text.count(old)
        if found != expect:
            print("中止：%s —— 命中 %d 次，期望 %d 次" % (desc, found, expect))
            return 1
        text = text.replace(old, new, 1)
        print("  已改：%s" % desc)

    # 断言：四个二级小节齐全且顺序正确
    heads = [line for line in text.splitlines() if line.startswith("## ")]
    want = ["## 为什么这么创建", "## 这个文件是做什么",
            "## 有什么用", "## 怎么用（过程教程）"]
    if heads != want:
        print("中止：二级小节结构不对，实际是 %r" % heads)
        return 1

    # 断言：四段「相关文件」表头只出现一次
    if text.count("### 相关文件") != 1 or text.count("| 文件 | 关系 |") != 1:
        print("中止：「相关文件」小节数量不对")
        return 1

    # 断言：不再残留旧的错误数字
    for bad in ("6 个汉字", "3 行空行", "编号是 1、2、3、4 而不是"):
        if bad in text:
            print("中止：仍残留旧表述 %r" % bad)
            return 1

    # 行尾保持 LF
    if b"\r\n" in original:
        print("中止：原文件是 CRLF，需另行处理")
        return 1

    PREVIEW.write_bytes(text.encode("utf-8"))
    print()
    print("预览已写到 %s" % PREVIEW)
    print("长度：原 %d 字节 -> 新 %d 字节" % (len(original), len(text.encode("utf-8"))))
    if apply:
        os.replace(PREVIEW, DOC)
        print("已覆盖原文件 %s" % DOC)
    else:
        print("加 --apply 才覆盖原文件")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
