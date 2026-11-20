"""追加本 tick 到 AI/教程进度.md。

用官方脚本 _t11_progress.py 追加（字节追加，历史不重写），
追加完再核对：tick 号连续、四个必填字段都在。

用法:
    python AI/脚本/_t919_append_tick11.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PROGRESS = ROOT / "AI" / "教程进度.md"

SUBJECT = "补充 w2l/commands/du.py 教程"
REASON = ("教程清单第 27 项；w2l/commands/ 下还缺逐文件教程的指令里，"
          "du.py 的统计口径最容易误解（默认报表观大小而不是磁盘占用、"
          "去重用 inode 而不是路径、阈值跟字节数比而不是跟块数比），"
          "而且 -h 的换档边界实测与 GNU 差了一整段区间，读者最容易踩")

HARVEST = (
    "与 GNU coreutils 8.32 对拍 16 个案例，15 个逐字节一致，1 个不一致（默认口径，"
    "本实现等价 GNU 的 --apparent-size，目录树 6259 字节本实现报 7 块、GNU 报 11 块）。"
    "查出一处真差异：-h 的换档规则用「商不超过 999」（du.py 第 492 行），"
    "GNU 的规则是「商不超过 1023」——字节数落在 [1022977, 1047552] 这段 24 KB 区间时，"
    "本实现显示 1.0M、GNU 显示 1000K~1023K；二分法定位到两个切换点（1022977 与 1047553）。"
    "同一个 999 常量在 1000 进制（--si）下恰好是对的（五个采样点全一致），"
    "所以要修得分成两个常量。查目录联接（mklink /J）：Python 的 os.lstat 对联接给的是 "
    "S_ISLNK=False、S_ISDIR=True、st_mode=0o40777，所以本实现把它当普通目录钻进去算内容，"
    "GNU 当符号链接只报它自己占的那一块（10 行 vs 2 行）。"
    "顺带查清 -x 的机制：根目录用 os.lstat（联接自己的卷），子项用 "
    "os.stat(follow_symlinks=False)（也是联接自己的卷），两者相同，"
    "所以联接这一层挡不住，du 会钻进去，真正被 st_dev 比对挡掉的是联接里面的文件——"
    "结果是错的，但白走了一遍目录树。"
    "另外查到 du.py 第 391~392 行的注释「不能用 item.stat()」是对的（Windows 上它给的 "
    "st_dev 与 st_ino 恒为 0），tree.py 没跟着改才导致 -x 全过滤。"
    "自引用联接不会无限递归：_claim 的 (st_dev, st_ino) 去重表挡住了第二次遇到的同一个 inode，"
    "这是 tree.py 那边踩过（递归到 64 层）而 du.py 躲过去的坑。"
    "去重的键选 inode 而不是路径，是因为同一个文件可以有多个路径别名（硬链接、符号链接、"
    "tree 与 tree/ 两种写法），按路径去重会把 . 和 ./ 算成两棵树。"
    "阈值跟字节数比不是跟块数比：-t 1K 留的是字节数 >= 1024 的条目，"
    "不是「块数 >= 1」的条目（后者会把所有非空文件都留下）。"
    "_rewrite_argv 把「选项 + 负号开头的值」改写成 -t=-1K 这种 argparse 认得的写法，"
    "只有 -d/--max-depth/-B/--block-size/-t/--threshold 六个选项在名单里，-- 之后不再改写。"
    "-h 与 --si 共用 human_base 这一个 dest，命令行上靠后的那个决定进制（GNU 同规则）。"
    "--time 的目录行取的是子树里最新的 mtime（含目录自身），不是目录自己的。"
)

NEGATIVE = (
    "预期输出第一版是手抄进 markdown 的，抄错了两处：GNU 默认口径那段抄成了本项目的输出"
    "（因为我给 GNU 跑的时候一律加了 --apparent-size），以及 pytest 那段写成「tests/test_du.py: 30」"
    "但 pyproject.toml 的 addopts=\"-q\" 让输出被压成一行进度条——核对器立刻报了 1 处不匹配，"
    "改成 `| tail -1` 后才对上。"
    "教训有三条：① 给 GNU 跑对照命令时，「同口径」和「默认口径」是两种命令，不能一个 helper 全加 --apparent-size，"
    "得把开关做成参数；② pytest 的输出永远要用 `| tail -1` 取汇总行，不要写死条数；"
    "③ 预期输出必须由生成脚本真跑录入（_t914），手抄必错。"
    "写盘踩了两次行尾坑：Windows 上 open(..., 'w') 默认把 \\n 翻译成 \\r\\n，"
    "第一次写完 teach/00 用 git diff 看是 179 行全变（整篇重写），"
    "而 teach/ 下其余各篇都是 LF——必须显式写 newline=\"\\n\"。"
    "夹具的 mtime 也踩了：初版每个目录的 mtime 都比它里面的文件新，"
    "结果 --time 的输出看不出「目录行取子树最新」这条规则，"
    "得把 tree/sub/deeper/e.txt 的 mtime 设成比它父目录还晚才看得出来。"
    "生成脚本的占位符检查原来用 split 奇偶下标判断，正文里出现奇数个 @@ 就 IndexError，"
    "改成正则 re.findall(r'@@[A-Z_]+@@')；同一个脚本还漏了 re 的 import，第一次跑就 NameError。"
    "探针脚本里对二进制输出用 endswith 判断单位（「1.0M」结尾）是错的——"
    "输出行是「大小<TAB>路径」，路径尾巴是 one.bin，永远不以 M 结尾，"
    "二分查找恒为 False，报出的「切换点 1048576」是假的；改成先 split('\\t')[0] 取第一列才对。"
    "另外探针脚本用 write 写盘时混进过两个 U+FFFD 坏字符（「不加」变成了「不加」），"
    "是编码转换吃掉的，肉眼看不出来，得在落盘前 assert 检查。"
    "还有一处：正文里写「自引用联接在 -x 下的递归深度问题比第 2 处更微妙」是我推测的，"
    "实测发现同卷的自引用联接在 -x 下输出与不加 -x 完全一样（都是 3 行），"
    "因为同卷根本不跨卷、挡住递归的是 inode 去重——推测性的说法已改成实测结论。"
    "最后一处：teach/00 的清单编号是 1..26，新行该编 27，我第一次写成了 26，"
    "被脚本里「清单第 27 行重复了」的断言拦下来了。"
)

REMAINING = (
    "F 类过期点仍未修：本轮全量核对 27 篇共 437 个命令块、333 个带预期、36 处不匹配，"
    "比上轮的 32 处多 4 处——多出来的全在 teach/24（find.py 从 905 行涨到 1002 行、"
    "test_find.py 从 37 条涨到 52 条、全量从 537 条涨到 585 条，"
    "以及 find 的 CRLF 缺陷被开发任务修掉了、od -c 的预期输出从 \\r\\n 变成了 \\n），"
    "属开发任务 tick #15 改源码的连带影响，不是本轮引入的。"
    "teach/23 的 2 处是 pytest 条数（488 -> 585）与 tail --pid 演示的耗时（4.3s -> 4.6s，"
    "属计时抖动不是真错）。"
    "其余 32 处与上轮同源，集中在 teach/13（ls 输出与指令清单 7 处）、teach/07（grep 行号 5 处）、"
    "teach/08（pytest 条数 4 处）、teach/02 与 teach/03（各 2 处），"
    "teach/01/05/06/09/11/15/17/18/19/20 各 1 处。"
    "本轮新增的 teach/26 与修过的 teach/00 全部一致。"
    "du.py 的两处缺陷属源码范围（开发任务可修），本轮按只读原则没动："
    "① _format_human 第 492 行的换档常量 999 应在 1024 进制下改成 1023（--si 仍要 999）；"
    "② 目录联接被当普通目录钻进去，与 GNU 的符号链接口径不一致。"
    "清单下一个待写文件按顺序是 w2l/commands/sed.py"
)


def main() -> int:
    before = PROGRESS.read_text(encoding="utf-8")
    ticks_before = re.findall(r"^#### tick #(\d+)", before, re.M)
    last_before = int(ticks_before[-1]) if ticks_before else 0

    cmd = [
        sys.executable, str(HERE / "_t11_progress.py"),
        "--进度", str(PROGRESS),
        "--主题", SUBJECT,
        "--理由", REASON,
        "--产出", "teach/26-w2l-commands-du.py-统计口径与去重规则.md",
        "--收获", HARVEST,
        "--负面", NEGATIVE,
        "--剩余", REMAINING,
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    print(proc.stdout.strip())
    if proc.returncode != 0:
        print("追加失败: %s" % proc.stderr.strip())
        return 1

    after = PROGRESS.read_text(encoding="utf-8")
    ticks_after = re.findall(r"^#### tick #(\d+)", after, re.M)
    last_after = int(ticks_after[-1]) if ticks_after else 0

    assert last_after == last_before + 1, (
        "tick 号没接上：%d -> %d" % (last_before, last_after))
    assert after.startswith(before[:200]), "文件开头被改动了"
    assert len(after) > len(before), "没追加进去"
    assert "\ufffd" not in after, "进度文件里有 U+FFFD"

    print("tick #%d 已追加，字节数 %d -> %d" % (
        last_after, len(before.encode("utf-8")), len(after.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
