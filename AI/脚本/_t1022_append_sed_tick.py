"""追加本轮（sed.py 教程）的 tick 日志。

为什么不直接用命令行传参：日志正文里有单引号（`/未知指令 '/'`）、反斜杠
（`\\|bravo\\|p`）、反引号（`` `^*` ``）三种在 shell 里都会出事的字符。
写成脚本直接调 _t11_progress.main()，参数不过 shell，零转义风险。

用法：python AI/脚本/_t1022_append_sed_tick.py
"""
from __future__ import annotations

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

_spec = importlib.util.spec_from_file_location(
    "t11", os.path.join(HERE, "_t11_progress.py")
)
t11 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(t11)

THEME = "w2l/commands/sed.py 教程"

REASON = (
    "教程清单第 28 项；sed.py 是 w2l/commands/ 下最长的指令实现"
    "（1390 行，第二名 tail.py 1140 行），"
    "地址语义与 BRE/ERE 方言差别最容易误解，"
    "实测还查出三处与 GNU sed 4.9 的差异和一处 -i 入口缺陷"
)

PRODUCTS = (
    "teach/27-w2l-commands-sed.py-地址语义与正则翻译.md"
    "（63 个命令块，核对器逐条真跑全部一致）；"
    "另更新 teach/00 索引页（篇数 27→28、依赖表加第 27 行、两条阅读路线加 sed、"
    "结构树订正 find.py 905→1002 行、tree.py 575→673 行、"
    "test_find.py 37→52 例、test_tree.py 34→45 例）；"
    "AI/脚本/ 下 _t1001~_t1021 共 20 个探针与验证脚本"
)

GAIN = (
    "地址不是布尔，是有状态的判定：_Command 里存 in_range / base_line / end_line / matches "
    "四个状态，每条指令各自维护；范围终点分四类各走各的算法——行号终点在起始行就命中"
    "（第 846 行）、plus 终点是起点+N（第 843~844 行）、正则终点不在起始行上试"
    "（实测起止同模式 /a/,/a/p 的范围跨两行，GNU 同样给两行）、"
    "tilde 走 _tilde_reached 单独一套（第 862~875 行）。"
    "BRE 靠逐字符翻译成 Python 正则而不是改引擎：_translate_bre 用 after_group 标志判断"
    "「这个 * 是不是字面量」，初始 True（表达式开头的 * 是字面量），处理完 \\( 或 ( 才置回 True"
    "——锚点 ^ $ 之后不置位，这就是 ^* 报 nothing to repeat 的根因。"
    "地址分隔符的规则是「开头转义、结尾不转义」：\\|re\\|、\\%re\\%、\\#re# 都认（GNU 同样认）；"
    "结尾也转义的 \\|re\\|p 两边都报错（README 第 499/550 行把它当可用写法）、"
    "裸的 %re%p 两边都报错（README 第 538 行说同样认）；"
    "README 第 524 行说「162 组用例输出逐条一致」——那 162 组里没有覆盖 ^* 与 ,~N 这两类写法。"
    "Git Bash 里 python 是原生 Windows 程序，MSYS 会把以 / 开头的参数改写成路径："
    "/bravo/p 变成 E:/software/Git/Git/bravo/p，sed 拿到第一个字符 E 就报「未知的 sed 指令 E」；"
    "GNU sed 自身是 MSYS 程序不受这层改写影响，所以「GNU 好使、这里不好使」，"
    "绕法是换分隔符或加 MSYS_NO_PATHCONV=1。"
    "编码靠嗅探前 8192 字节 + 文本可信度打分（ASCII 1.0 / CJK 3.0 / 全角 1.0 / 控制符 0.5 / "
    "其余高位 0.2，换编码要领先 0.3 分），不是取第一个能解的——cp1252 几乎不报错会把 GBK 解成乱码；"
    "代价是输出统一成 UTF-8（GNU 是字节透传），是项目一贯取舍。"
    "原地修改走「同目录临时文件 + os.replace」原子替换（第 1353~1365 行），备份是原文件字节拷贝。"
    "三处与 GNU 4.9 的差异都定位到了根因与行号：BRE 锚点后 *（_translate_bre 第 589~633 行）、"
    "范围终点 ,~N（_tilde_reached 第 862~875 行 vs GNU execute.c 第 871~874 行的 "
    "end = start + step - (start % step)）、首地址 1~0"
    "（_match_address 第 887~894 行用 max(step,1) 兜底，GNU 步长 0 退化成普通行号地址）。"
    "另有一处入口缺陷：-i 在真实 CLI 上不可用——split_inplace（第 1221 行）能把 -i 拆成 "
    "--in-place，但 w2l/cli.py 第 82~83 行直接 parser.parse_args(argv[1:]) 没走改写，"
    "build_parser 也没注册 -i；--in-place 与 --in-place-suffix=.bak 在真实入口上正常"
)

NEGATIVE = (
    "捕获脚本第一版把地址分隔符写成两边都转义的写法，48 条命令里 7 条直接抛「命令没有闭合」"
    "——教训：转义规则要先在真跑里钉死，再批量写。"
    "GNU sed 的可执行文件路径写错（bin\\sed.exe 不存在，实际在 usr\\bin\\ 下），"
    "第一版对照整段报「系统找不到指定的文件」。"
    "用 --in-place 测夹具时把 AI/数据/sed_demo/a.txt 改写了，后面的捕获全被污染，"
    "必须重建夹具再重跑。"
    "多行 sed 脚本不能直接写进 bash 块：核对器把同一块里的多行用 && 串起来会把脚本拼坏"
    "（报「未知的 sed 指令 /」），改用 -f 读脚本文件（夹具里加 jump.sed）。"
    "「这一步没有输出」的预期块不能让下一段围栏紧跟着：核对器会把下一段围栏"
    "当本命令的预期输出比对而报不匹配；写成「这一步没有输出」且后面紧跟 bash 块才安全。"
    "更新 teach/00 的脚本第一版幂等性就破了：旧串是新串的子串（依赖表那行），"
    "先判旧串会每次都再插一行，文件从 184 行涨到 185 行；改成先判新串才稳。"
    "复算断言脚本第一版把区间判断写成 all()，19 条区间断言全部误报失败；"
    "区间语义应该是 any()。"
    "FINDINGS 改成原始串之后才发现里面写的是双反斜杠，改回单反斜杠并从干净版本重跑，"
    "才没让 markdown 里出现四反斜杠。"
    "git push 连着三次报「Failed to connect to github.com port 443」，第四次才推上去；"
    "本地提交没有回滚"
)

PENDING = (
    "F 类过期点仍未修：本轮全量核对 28 篇共 500 个命令块、394 个带预期、45 个跳过、40 处不匹配，"
    "本轮新增的 teach/27 与改过的 teach/00 全部一致，不匹配全在旧篇目上——"
    "teach/25 有 5 处（tree.py 行数、test_tree.py 条数、-x 不再全过滤、-P 少展开一层），"
    "teach/24 有 4 处（find.py 行数、pytest 条数、od -c 的 CRLF），"
    "集中在 teach/13（ls 输出与指令清单 7 处）、teach/07（grep 行号 5 处）、"
    "teach/08（pytest 条数 4 处）、teach/02 与 teach/03（各 2 处），"
    "teach/01/05/06/09/11/15/17/18/19/20/23 各 1 处；"
    "teach/15 的 ls -1 AI 每轮都会因为新增脚本与目录而多一行，属会自己长的过期点。"
    "sed.py 的三处差异与 -i 入口缺陷属源码与 README 范围（开发任务可修），"
    "本轮按只读原则没动，逐条结论见 teach/27 与本文件第 3 节。"
    "清单下一个待写文件按顺序是 w2l/commands/awk_lite.py"
)


def main() -> int:
    argv = [
        "prog",
        "--进度", os.path.join(ROOT, "AI", "教程进度.md"),
        "--主题", THEME,
        "--理由", REASON,
        "--产出", PRODUCTS,
        "--收获", GAIN,
        "--负面", NEGATIVE,
        "--剩余", PENDING,
    ]
    saved = sys.argv
    sys.argv = argv
    try:
        t11.main()
    finally:
        sys.argv = saved
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
