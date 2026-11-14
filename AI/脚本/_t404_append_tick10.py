"""追加 tick #10 的日志到 AI/阅读进度.md。

用 _t11_progress.py 的格式化函数，tick 号只按「#### tick #N」段头现算
（不扫全文，免得文件头的「本次会话：cron tick #N」把号数顶高一位）。
最后再补一行「推送未成功」，跟 tick #9 的写法保持一致。
"""

from __future__ import annotations

import importlib.util
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROGRESS = ROOT / "AI" / "阅读进度.md"

spec = importlib.util.spec_from_file_location("t11_progress", HERE / "_t11_progress.py")
t11 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t11)

TICK_HEAD = re.compile(r"^####\s*tick\s*#(\d+)", re.MULTILINE)


def next_tick(text: str) -> int:
    highest = 0
    for match in TICK_HEAD.finditer(text):
        highest = max(highest, int(match.group(1)))
    return highest + 1


THEME = "实现 awk-lite 指令"

REASON = (
    "命令队列里最后一个（ls→cat→head→tail→wc→find→tree→du→sed→awk-lite），"
    "做完这一项队列就走完了"
)

PRODUCTS = (
    "w2l/commands/awk_lite.py、tests/test_awk_lite.py、"
    "tests/conftest.py（新增 run_awk_lite 辅助函数）、"
    "README.md（awk-lite 章节 + 指令清单 + 目录结构 + 快速开始）；"
    "另单独提交 AI/脚本/ 下 4 个探针与差分脚本；三个交付文件已登记进 E:\\1data\\过滤器\\索引\\索引.jsonl"
)

GAIN = (
    "GNU awk 5.3.2 的分隔符分三档：没给分隔符或给单个空格 → 按空白串切"
    "（连续空白算一个，两端空白不算字段，空行字段数是 0）；给单个字符 → 按字面量切"
    "（`.` 就是一个点不是任意字符，连续出现切出空字段）；给多个字符 → 按正则切"
    "（所以 `-F '..'` 把 abcdef 切成 4 个空字段而不是 3 个，这一档最容易照抄错）；"
    "显式给一个空格等同默认。{print} 等价 {print $0}（GNU 也认），print(...) 也认，"
    "多个 print 参数用 OFS 连接。字段号超范围是空串不报错，$NF 是最后一列；"
    "模式是正则（ERE），只写模式打整行；NR 跨文件连续、FNR 每文件从头、FILENAME 是命令行给的名字；"
    "-v 变量放在字段位置时数字当字段号，非数字当字段名（GNU 没有具名字段所以给整行，照抄）；"
    "目录操作数 GNU 只是警告后跳过（rc 0），本项目按惯例返回 2。"
    "**差分对照必须用 `awk -f` 传程序**：Windows Python 拉起 MSYS 的 awk.exe 时，"
    "不含空格参数里的大括号会被 MSYS 运行时吃掉（{print} 变成 print，gawk 报 "
    "cmd. line:1: print ^ syntax error），同一个程序在 Git Bash 里跑却完全正常，"
    "带空格的参数不受影响——这是本轮最容易把人带沟里的坑"
)

NEGATIVE = (
    "测试里 5 处期望值是我手算错的：{print FILENAME} 是每行打一次（4 行不是 1 行）、"
    "-F, 用在分号分隔的样例文件上当然切不开（我拿 semi.log 当逗号文件用了 4 次，-F; 才对）；"
    "第一版实现有两个真 bug：相对路径按进程 cwd 解析而不是 ctx.cwd"
    "（sed 那轮踩过同一个坑，本轮又踩了一次），读标准输入时完全忽略了 -F；"
    "差分脚本第一轮 52 组全显示不一致，根因不是逻辑而是 Windows 文本模式把 \\n 写成 \\r\\n，"
    "归一换行后 52 组全对、补完用例到 64 组全对；"
    "推送连续三次失败（第三次是本轮开工时补推 tick #9 的遗留提交）"
)

PENDING = (
    "编码判定整套逻辑（_detect_encoding/_candidate_encodings/_decode_sample/_text_score）"
    "现在在 cat.py、grep.py、sed.py、wc.py、awk_lite.py 里各写了一份，属已知重复，本轮没动；"
    "多字符分隔符按正则这条已对齐 GNU，但正则里出现 Python re 独有语法时行为跟 POSIX ERE 不完全一样；"
    "只支持 print 动作，算术、字符串拼接、BEGIN/END、函数、数组、printf 一律明确报错不支持"
)

PUSH_NOTE = (
    "- **推送未成功**：本轮两个提交（feat(awk-lite) / 归档探针脚本）都还在本地，"
    "连同 tick #9 遗留的三个提交一共 5 个没推上去。"
    "`git push origin main` 试了 4 次，报错原文有三种："
    "`fatal: unable to access 'https://github.com/dom-one/Linux2Python/': Recv failure: Connection was reset`、"
    "`fatal: unable to access 'https://github.com/dom-one/Linux2Python/': Failed to connect to github.com port 443 after 21145 ms: Could not connect to server`、"
    "以及开工时补推 tick #9 遗留提交时同样报 Recv failure。"
    "用 HTTPS HEAD 探 github.com 也连不上，是网络层不通、不是凭据问题（凭据问题会先弹登录框）。"
    "本地提交不回滚，下个 tick 开工前先补推一次。"
)


def main() -> int:
    raw = PROGRESS.read_bytes()
    before = raw.decode("utf-8")
    tick = next_tick(before)
    block = t11.build_block(tick, THEME, REASON, PRODUCTS, GAIN, NEGATIVE, PENDING)
    with PROGRESS.open("ab") as handle:
        handle.write(block.encode("utf-8"))
        handle.write((PUSH_NOTE + "\n").encode("utf-8"))
    print(f"tick #{tick} 已追加到 {PROGRESS}")
    print(f"时间戳: {time.strftime('%Y-%m-%d %H:%M')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
