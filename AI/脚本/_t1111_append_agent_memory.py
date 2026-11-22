"""把本轮的两条通用踩坑追加到 agent 记忆文件（MEMORY.md）。

memory 工具这轮没能接受 append 参数，改用脚本直接追加，
追加前先检查同一段文字是否已存在，避免重复写入。
"""

from __future__ import annotations

from pathlib import Path

MEMORY = Path(r"C:\Users\26708\.minimax\agents\mavis\memory\MEMORY.md")

ENTRY = """
### Windows 上量性能与写端到端探针的两个必踩坑（2026-11-23 实测）

**坑一：Defender 会逐个扫新创建的文件，不预热就量到的是杀毒时间不是算法时间。**
- **证据**：同一棵 912 文件的树，第一次 grep 要 24.374s、第二次 0.070s；新建一棵树第一次 0.642s、第二次 0.066s。GNU grep 在同一棵**热**树上只要 0.057s ⇒ 第一轮基线一度得出「本项目比 GNU grep 慢 220 倍」的错误结论，差点据此判断整个技术方向错了。
- **正解**：量任何耗时前**先跑一次预热并丢弃**，正式测量连跑两次取较小值；同一份测量里所有档位（基线/优化版/参照实现）必须紧挨着跑，中间不要插入别的负载。
- **配套**：机器上有别人的重负载时，同一档位两次可能差 45% ⇒ 报**区间**不报单值，别把噪声当结论。

**坑二：探针把 stdout 接成 PIPE 却等进程退出后才读 ⇒ 约 4KB 管道缓冲写满 ⇒ 子进程卡在写上永不退出 ⇒ 父进程死等。**
- **证据**：症状像「实现挂死」（进程列表里只剩父进程、子进程全没了），一度以为是 multiprocessing 的 bug；实际把 stdout 改成 DEVNULL 立刻正常。
- **正解**：比对输出用 `subprocess.run(capture_output=True)`（内部 communicate 并发读两个管道）；要边跑边看 stderr 就 `Popen(stdout=DEVNULL, stderr=PIPE)` + 单独线程抽干 stderr；**不要** Popen(PIPE) 后 `poll()` 忙等、最后才 `communicate()`。
- **配套**：忙等循环（无 sleep）会抢 CPU，把测量本身搞失真，轮询要加 sleep。

**何时应用**：任何在 Windows 上做性能测量、任何用 subprocess 拉子进程做端到端验证的场合；
任何「跑出来慢得离谱 / 进程卡住不退」的现象——**先分诊是测量方法错还是被测实现错**。
★ 与已有「先怀疑探针，改判据而不是改产物」同族：探针自身写错时，症状会**伪装成被测对象的 bug**；
分诊顺序是「先复现成最小案例（换个变量能立刻分叉）→ 再看子进程有没有真的起来」。
★ 配套：Windows 只有 spawn，子进程会重新 import 主模块 ⇒ 主入口必须有 `if __name__ == "__main__"` 守卫，
否则并行/子进程方案会在子进程里递归执行主流程。
★ 配套：并行要保序时用 `Pool.imap`（按输入顺序返回）而不是 `imap_unordered`，
切片数取**进程数的若干倍**（本例 4 倍）让快进程动态多领活，均衡负载而不破坏顺序。
"""


def main() -> int:
    if not MEMORY.exists():
        print(f"记忆文件不存在: {MEMORY}")
        return 1
    text = MEMORY.read_text(encoding="utf-8", errors="replace")
    if "Windows 上量性能与写端到端探针的两个必踩坑" in text:
        print("已存在，跳过追加")
        return 0
    if not text.endswith("\n"):
        text += "\n"
    with MEMORY.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(ENTRY.lstrip("\n"))
    print(f"已追加 {len(ENTRY)} 字符到 {MEMORY}")
    print(f"追加后总行数: {len(MEMORY.read_text(encoding='utf-8', errors='replace').splitlines())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
