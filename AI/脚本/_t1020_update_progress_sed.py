"""更新 AI/教程进度.md：状态、教程清单、本轮实测到的 sed.py 缺陷小节。

为什么写脚本：进度文件里有 20 多处「只有文字佐证」的数字（篇数、下一步清单），
本轮加了一篇教程，这些数字都得跟着动。手工改容易漏，且改漏了没人查。

幂等：每处替换都先看新串在不在（不是先看旧串）——有些旧串是新串的子串，
先判旧串会每次都再插一行。

用法：python AI/脚本/_t1020_update_progress_sed.py
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TARGET = ROOT / "AI" / "教程进度.md"

FINDINGS = r"""<!-- sed-findings:start -->
### 2026-11-22 sed.py 与 GNU sed 4.9 的三处差异、`-i` 入口缺陷（本轮实测）

给 `w2l/commands/sed.py` 写教程时，用 Git Bash 自带的 GNU sed 4.9 对拍，
查出 3 处**行为差异**，另有 1 处**真实命令行入口的缺陷**。前三处源码范围属开发任务，
本轮按只读原则没动：

| 现象 | 根因 | 位置 |
|---|---|---|
| BRE 里 `^*` `$*` `a^*` 直接报「无效的正则表达式」，GNU 当字面量正常出结果 | `_translate_bre` 的 `after_group` 标志在处理完 `^` `$` 之后不置位，锚点后的 `*` 没被当字面量 | `w2l/commands/sed.py` 第 589~633 行（默认分支第 630~631 行） |
| 范围终点 `,~N` 覆盖的行数与 GNU 不同（`2,~3p`：本实现给第 2~5 行，GNU 给第 2~3 行） | 本实现按「行号差取模 `offset % step == 0`」；GNU 上游 `execute.c` 的 `ADDR_IS_STEP_MOD` 是 `end = start + step - (start % step)` | `w2l/commands/sed.py` 第 862~875 行；GNU `execute.c` 第 871~874 行 |
| 首地址 `1~0`（步长为 0）本实现打成全部 8 行，GNU 只打第 1 行 | `_match_address` 的 step 分支用 `max(address.step, 1)` 兜底，步长 0 被当成 1；GNU 在步长为 0 时退化成普通行号地址 | `w2l/commands/sed.py` 第 887~894 行 |

第四处是**入口缺陷**，不是与 GNU 的语义差异：

| 现象 | 根因 | 位置 |
|---|---|---|
| `python main.py sed -i 's/a/A/g' f` 报 `unrecognized arguments: -i`，退出码 2，文件没改 | `split_inplace()` 能把 `-i` 拆成 `--in-place`，但 `w2l/cli.py` 第 82~83 行直接 `parser.parse_args(argv[1:])` 没走改写；`build_parser()` 也只注册了 `--in-place` / `--in-place-suffix` | `w2l/commands/sed.py` 第 1221 行（`split_inplace`）、`w2l/cli.py` 第 82~83 行 |

`--in-place` 与 `--in-place-suffix=.bak` 在真实入口上正常。README 第 502~503 行把 `-i`
与 `-i.后缀` 写成可用示例，与实际不符，属 README 范围。

另有**地址分隔符写法**的实测结论（GNU 4.9 同样如此），与项目文档对不上的有两处：

| 写法 | 本实现 | GNU 4.9 | 文档怎么说 |
|---|---|---|---|
| 结尾也转义：`\|re\|p` | 报错「命令没有闭合」 | 报错 `unterminated address regex` | README 第 499 行与第 550 行把它当可用写法 |
| 开头没转义：`%re%p` | 报错「未知的 sed 指令 '%'」 | 报错 `unknown command: %'` | README 第 538 行说「`%re%` 这种写法同样认」 |
| 开头转义、结尾不转义：`\|re|`、`\%re%`、`\#re#` | 都认 | 都认 | — |

也就是说：**开头必须转义、结尾不能转义**（`\|re|`、`\%re%`、`\#re#`）。

README 第 524 行写「162 组用例输出逐条一致」——那 162 组里没有覆盖 `^*` 与 `,~N`
这两类写法，实测它们与 GNU 不一致。

实测脚本：`AI/脚本/_t1001_probe_sed_diff.py`（157 组脚本 + 9 组原地 + 6 组 stdin 对拍）、
`_t1004_probe_sed_tilde.py`、`_t1006_probe_sed_tilde_detail.py`、
`_t1008_probe_sed_final.py`、`_t1009_probe_sed_anchor_star.py`、
`_t1013_probe_sed_inplace.py`、`_t1014_probe_sed_delim.py`、
`_t1007_fetch_sed_src.py`（取 GNU sed 4.9 上游源码定位 `execute.c` 的算法）。
逐条结论见 `teach/27` 的「实测出的与 GNU sed 4.9 的三处差异」一节。

<!-- sed-findings:end -->

"""

REPLACEMENTS: list[tuple[str, str, str]] = [
    ("最后更新日期",
     "最后更新：2026-11-21",
     "最后更新：2026-11-22"),
    ("本次会话",
     "本次会话：cron tick（补充 w2l/commands/du.py 教程，已完成 27 篇）",
     "本次会话：cron tick（补充 w2l/commands/sed.py 教程，已完成 28 篇）"),
    ("完成度",
     "- 完成度：27/27",
     "- 完成度：28/28"),
    ("下一步清单",
     "- 下一步：`w2l/commands/` 下还差 `sed.py`、`awk_lite.py`、`cp.py`、`mv.py`、"
     "`rm.py`、`chmod.py` 六篇",
     "- 下一步：`w2l/commands/` 下还差 `awk_lite.py`、`cp.py`、`mv.py`、"
     "`rm.py`、`chmod.py` 五篇"),
    ("已写篇目的括号说明",
     "`du.py` 见 teach/26，`ls.py` 的内容被 teach/13 当例子覆盖过）",
     "`du.py` 见 teach/26、`sed.py` 见 teach/27，"
     "`ls.py` 的内容被 teach/13 当例子覆盖过）"),
    ("教程清单加第 28 行",
     "| 27 | `w2l/commands/du.py` | `26-w2l-commands-du.py-统计口径与去重规则.md` | 已完成 |",
     "| 27 | `w2l/commands/du.py` | `26-w2l-commands-du.py-统计口径与去重规则.md` | 已完成 |\n"
     "| 28 | `w2l/commands/sed.py` | `27-w2l-commands-sed.py-地址语义与正则翻译.md` | 已完成 |"),
]


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    changed = 0
    for label, old, new in REPLACEMENTS:
        if new in text:
            print("  [已] %s" % label)
        elif old in text:
            if text.count(old) != 1:
                raise SystemExit("[%s] 旧串出现 %d 次，不唯一" % (label, text.count(old)))
            text = text.replace(old, new)
            changed += 1
            print("  [改] %s" % label)
        else:
            raise SystemExit("[%s] 既找不到旧串也找不到新串" % label)

    # 缺陷小节插在「## 4. tick 日志」之前，用标记做幂等
    if "<!-- sed-findings:start -->" in text:
        print("  [已] sed.py 缺陷小节")
    else:
        anchor = "## 4. tick 日志"
        if text.count(anchor) != 1:
            raise SystemExit("找不到唯一的「## 4. tick 日志」锚点")
        text = text.replace(anchor, FINDINGS + anchor)
        changed += 1
        print("  [改] sed.py 缺陷小节")

    if "\ufffd" in text:
        raise SystemExit("正文里混进了坏字符 U+FFFD")

    with open(TARGET, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("[result] 已写入 %s（改动 %d 处）" % (TARGET, changed))
    print("[result] %d 字节，%d 行" % (len(text.encode("utf-8")), text.count("\n") + 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
