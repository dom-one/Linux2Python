"""把本 tick 的收获/负面结果写进 _t11_progress.py 的调用参数里。

命令行参数太长，直接在 bash 里拼容易出错（还容易把引号写坏）。
这里把参数写成 JSON，再由调用方读进来传给 _t11_progress.py。
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

PAYLOAD = {
    "主题": "实现 du 指令",
    "理由": "命令队列里下一个（ls→cat→head→tail→wc→find→tree→du）",
    "产出": (
        "w2l/commands/du.py、tests/test_du.py、tests/conftest.py（新增 run_du 辅助函数）、"
        "README.md（du 章节 + 指令清单 + 目录结构）；另单独提交 AI/脚本/ 下 12 个探针与差分脚本"
    ),
    "收获": (
        "GNU du 的默认口径是磁盘占用（按块向上取整），MSYS2 的 st_blocks 是模拟层产物"
        "（ceil(size/512) 再乘 1024），跟 NTFS 真实分配对不上，Windows 的 Python 又拿不到 st_blocks，"
        "所以本实现默认改按文件字节数统计，等价于 GNU 的 --apparent-size，82 组差分用例逐条一致；"
        "取整模型是「先按原始字节求和、只在显示时向上取整到块」，不是每个文件各自取整再求和；"
        "-t 的阈值跟字节数比而不是跟块数比（-t 1K 会留下块数 1、字节数 10 的小文件），"
        "负阈值则只留不大于它的条目；-h 的尾数向上取整到一位小数、取整后达到 10 就改成整数，"
        "10239 字节是 10K 而不是 9.9K，且 --si 与 -h 谁靠后听谁的（后者会覆盖前者的进制）；"
        "--time 给目录的是子树里最新的 mtime（含目录自身），不是目录自己的 mtime；"
        "同一个文件只算一次，目录被多个操作数覆盖时后来那份既不统计也不输出，-l 才重复计入；"
        "-s 与 -d N（N>=1）互相冲突，-s 等于 --max-depth=0；"
        "Windows 上 os.scandir().stat() 给的是目录枚举缓存，st_dev 与 st_ino 全是 0，"
        "硬链接去重与 -x 都会失效，必须改用 os.stat() 才拿得到真实的卷标识与文件索引"
    ),
    "负面": (
        "第一版差分 47 组里 43 组不一致，根因是用了 os.scandir().stat()：Windows 上它返回的 "
        "st_dev/st_ino 全是 0，所有文件在去重集合里撞成同一个，文件全被当成重复项跳过；"
        "改成 os.stat() 后 47 组全对；"
        "中途又用了一次 python - <<EOF 的 heredoc 内联解释器，触发 Python 3.14 的 REPL 崩溃循环，"
        "AGENTS.md 里白纸黑字写了这条禁令仍然再犯（本轮已是第二次），已立刻停掉并 taskkill 清掉孤儿进程；"
        "探针用 ctypes 的 SetFilePointerEx + SetEndOfFile 造大文件时并没有生成稀疏文件，"
        "实打实占了 13.7 GB 磁盘，清理脚本才把 AI/数据 降回 2.6 MB——以后造大文件只能走 fsutil 且要放在纯 ASCII 路径下；"
        "清理脚本顺手把上一轮 tree 的参考源码 AI/数据/tree_ref/*.c 也删了（不在本次范围内，已无备份）；"
        "测试前两轮 6 处期望值是我手算错的（fixture 少建了一层 tree 目录、sub 的总数算成 2 实际是 5、"
        "-l 重复计入时我以为总行会相加实际是各自报一次）"
    ),
    "剩余": (
        "-L/-H/-P 的符号链接行为在本机没法验证（Windows 上创建符号链接要管理员权限，报 WinError 1314）；"
        "1TB 以上的稀疏文件在本盘建不出来，所以 T/P/E 档的单位字母只按 coreutils 的规则实现、没做实测对照；"
        "顺带发现 tree.py 的 -x 也有同样的 st_dev==0 问题（它用 item.stat()，会把它自己的子项全滤掉），"
        "本轮按「一次只做一个命令」的约定没动它，下个 tick 可以顺手修"
    ),
}

out = HERE / "_t124_du_tick_payload.json"
out.write_text(json.dumps(PAYLOAD, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"written: {out}")
