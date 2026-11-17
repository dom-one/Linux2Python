"""追加 teach 任务的 tick 日志（走 _t11_progress.py，参数用列表传，避免 shell 转义）。

用法:
    python AI/脚本/_t712_append_teach_tick.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PROGRESS = Path(ROOT) / "AI" / "脚本" / "_t11_progress.py"

THEME = "补充 w2l/commands/find.py 教程"

REASON = (
    "教程清单第 25 项；w2l/commands/ 下还缺逐文件教程的指令里 find.py 的命令行是唯一一门语言"
    "（路径在前表达式在后的两段式、! > -a > -o 的优先级、动作截断与运算链、-prune 不算动作），"
    "读者最容易误解"
)

PRODUCT = (
    "teach/24-w2l-commands-find.py-表达式语法与遍历语义.md（41 个命令块，核对器逐条真跑全部一致）；"
    "另更新 teach/00 索引页（篇数 23→25、依赖表加第 24 行、可用指令清单补 rm、"
    "结构树补 rm.py 与 test_rm.py）；AI/脚本/ 下 _t700~_t711 共 12 个探针与夹具脚本"
)

GAIN = (
    "find 的命令行不能交给 argparse：表达式里混着括号、!、-o 和裸参数，argparse 会当选项或位置参数报错，"
    "所以 _FindParser 只在 --help 时用 argparse，其余把 argv 原样塞进 raw_args 自己解析，"
    "代价是帮助文案得手写（第 199~224 行）。表达式做成树：_Test 只判真假、_Action 执行副作用并带 is_action 标记、"
    "_And/_Or/_Not 组合，is_action 这个标记就是让动作能截断与运算链——_And 里左边是动作就直接返回不再算右半边，"
    "与 GNU 逐条对拍一致。-prune 不算动作，所以 _PRINT_SUPPRESSORS 只列 print/print0/printf/exec/delete 五个，"
    "find . -type d -name sub -prune 仍打印 sub 目录，GNU 实测同样只输出一行。"
    "隐式 -print 是往整条表达式末尾挂一个 _And 节点而不是包住整棵树，这样 -prune 命中的目录照样打印但不往下走。"
    "Windows 上 fnmatch.fnmatch 会先过 os.path.normcase 把大小写抹平（实测 fnmatch(B.TXT, *.txt)=True），"
    "所以 -name 必须用 fnmatchcase、-iname 才用 fnmatch——照抄 fnmatch 会让 -name 连大写文件一起匹配。"
    "目录大小一律按 0 算，因为 Windows 的目录 st_size 不稳（空目录 0、条目一多变 4096）而 GNU 侧恒为 0。"
    "-mmin 的整分钟计数比直觉多 1（count = age // 60 + 1），所以 -mmin 0 永远匹配不到东西、"
    "刚建好的文件落在 -mmin 1；-mmin 的负数是小于等于、-mtime 的负数是小于，GNU 同口径。"
    "-printf 的 %T@ 用整数纳秒算（divmod(st_mtime_ns, 10**9) 再补一个 0），不用浮点秒"
    "（浮点尾数带二进制噪声），实测本项目与 GNU 的 %T@ 逐字节一致（1794946258.5768073000）。"
    "显示路径与访问路径分开存：_Item.display 给用户看并统一成正斜杠，fs_path 给 os 用。"
    "-exec 在 Windows 上找不到可执行文件时退回 cmd /c，且整条命令用 list2cmdline 合成一个参数传过去"
    "（拆成多个参数 cmd 会按自己的编码重拼命令行、中文路径变 GBK 字节）；"
    "不过本机 where echo 显示 Git 自带的 echo.exe 排在前面，实际走不到这条回退分支"
)

NEGATIVE = (
    "对拍查出 3 处本实现的缺陷（不是取舍），已在教程「与 GNU 的差异」一节逐条列根因："
    "_expand_placeholder 把整个参数替换掉了，-exec echo A{}B 只输出路径、A 和 B 丢了，"
    "一个参数里多个 {} 也只替换第一个；"
    "_Or.evaluate 少了「左半边是裸动作就短路」这个分支（_And 有、_Or 没有），"
    "-print -o -name 会被命中项打印两遍而 GNU 只一遍；"
    "管道里输出是 CRLF，因为 find.py 没像 tail.py（502~508 行）和 cat.py（154~160 行）那样调 "
    "reconfigure(newline=空串)，多出来的 \\r 会让 grep -x 和 $(...) 比较对不上。"
    "三处都属源码范围，开发任务可修，本轮按只读原则没动。"
    "另有 2 处与 GNU 不同但属有意取舍：-exec 不带 {} 时本项目追加路径而 GNU 不追加、"
    "-exec CMD + 不带 {} 时 GNU 报错而本项目接受；"
    "-printf 遇到不认识的指令 GNU 会 stderr 警告而本项目静默。"
    "探针方法上：预期输出不能凭印象写，全部 41 个命令块的预期都由 "
    "AI/脚本/_t709_capture_find_tutorial.py 实跑录到 AI/数据/find_tutorial_capture.txt 后再誊进文档——"
    "第一版核对器就报了 1 处不匹配，是我在空输出块里写了「（无输出）」三个字；"
    "引入段的示例代码块必须用 text 围栏而不是 bash 围栏，否则核对器会拿它当可执行命令去跑。"
    "夹具的遍历顺序也要确认稳不稳：同一份文件名按同一顺序创建，NTFS 的 readdir 顺序重建 3 次都一样"
    "（AI/脚本/_t706_probe_find_order.py），所以预期输出可以写死顺序不用 sort。"
    "-mmin 的演示更要卡时间：夹具的 mtime 是固定的，跑久了 age 会跨过 60 秒的台阶，"
    "所以那一步把造文件的脚本和查询放进同一条命令（&& 连接），文件刚建好 count 恒为 1"
)

PENDING = (
    "F 类过期点仍未修：本轮全量核对 25 篇共 370 个命令块、268 个带预期，30 处不匹配，"
    "集中在 teach/13（ls 输出与指令清单 7 处）、teach/07（grep 行号 5 处）、teach/08（pytest 条数 4 处）、"
    "teach/02（2 处），teach/01/03/05/06/09/11/15/17/18/19/20/23 各 1 处；"
    "本轮新增的 teach/24 与 teach/00 全部一致。"
    "find.py 的 3 处缺陷已写进本文件第 3 节，属开发任务范围。"
    "清单下一个待写文件按顺序是 w2l/commands/tree.py"
)


def main() -> None:
    args = [
        sys.executable,
        str(PROGRESS),
        "--进度", "AI/教程进度.md",
        "--主题", THEME,
        "--理由", REASON,
        "--产出", PRODUCT,
        "--收获", GAIN,
        "--负面", NEGATIVE,
        "--剩余", PENDING,
    ]
    proc = subprocess.run(args, cwd=str(ROOT))
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
