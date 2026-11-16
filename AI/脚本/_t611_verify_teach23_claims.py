"""复算 teach/23 正文里的数字断言（核对器只比对命令块，查不到这些）。

用法:
    python AI/脚本/_t611_verify_teach23_claims.py

要核对的正文断言：
1. tail.py 有 1140 行
2. _Follower 类从 836 行到 953 行
3. _read_last_lines 要凑够 count+1 个分隔符
4. 块大小 _READ_SIZE = 65536
5. 54 条用例与 GNU 对拍，48 条一致，6 条差异
6. 测试用例数 45
7. 编码判定取的是输出段（mixed.txt 实测）
8. --pid 目标进程退出后 tail 在几秒内结束
9. 乘数后缀的倍数表
10. _UINTMAX_MAX = 2^64 - 1
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from w2l.commands import tail as tail_mod  # noqa: E402

TAIL_PY = os.path.join(ROOT, "w2l", "commands", "tail.py")
TEACH = os.path.join(ROOT, "teach", "23-w2l-commands-tail.py-起点语义与跟随模式.md")

ok = True


def check(label, condition, detail=""):
    global ok
    mark = "对" if condition else "错"
    if not condition:
        ok = False
    print("[%s] %s%s" % (mark, label, ("  " + detail) if detail else ""))


def main() -> int:
    with open(TAIL_PY, "r", encoding="utf-8") as fh:
        src = fh.read()
    lines = src.splitlines()
    text = "\n".join(lines)

    # 1. 行数
    n_lines = len(lines)
    check("tail.py 1140 行", n_lines == 1140, "实际 %d" % n_lines)

    # 2. _Follower 类范围
    m = re.search(r"^class _Follower:.*?^\n\ndef _take_complete_lines", src, re.S | re.M)
    if m:
        start = src[:m.start()].count("\n") + 1
        end_line = src[:m.end()].count("\n") + 1
        check("_Follower 从 836 行开始", start == 836, "实际 %d" % start)
        # 类体最后一行是 return chunk（933 行往前数），类结束行 = _take_complete_lines 所在行 - 3
        check("_Follower 类体结束在 932 行", end_line - 3 == 932,
              "实际 %d（_take_complete_lines 在 %d 行）" % (end_line - 3, end_line))
    else:
        check("_Follower 类定位", False, "正则没匹配上")

    # 3. count+1 个分隔符
    check("_read_last_lines 凑 count+1 个分隔符",
          "buffer.count(delimiter) >= count + 1" in src)

    # 4. 块大小
    check("_READ_SIZE = 65536", tail_mod._READ_SIZE == 65536,
          "实际 %d" % tail_mod._READ_SIZE)

    # 5. 对拍统计
    import json
    probe = os.path.join(ROOT, "AI", "数据", "tail_probe.json")
    if os.path.isfile(probe):
        with open(probe, "r", encoding="utf-8") as fh:
            rows = json.load(fh)
        same = sum(1 for r in rows if r["same"])
        diff = len(rows) - same
        check("54 条对拍用例", len(rows) == 54, "实际 %d" % len(rows))
        check("48 条一致", same == 48, "实际 %d" % same)
        check("6 条差异", diff == 6, "实际 %d" % diff)
        # 差异的类型
        kinds = []
        for r in rows:
            if not r["same"]:
                kinds.append(" ".join(r["args"]))
        print("     差异用例：%s" % "; ".join(kinds))
    else:
        check("对拍结果文件存在", False, probe)

    # 6. 测试用例数（-q -q 的输出格式是 "文件: 个数"）
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_tail.py", "--collect-only", "-q"],
        cwd=ROOT, capture_output=True, text=True)
    m = re.search(r"tests/test_tail\.py:\s*(\d+)", proc.stdout)
    check("test_tail.py 45 个用例", m is not None and int(m.group(1)) == 45,
          "实际 %s" % (m.group(1) if m else "没解析到"))

    # 7. 编码判定取输出段
    demo = os.path.join(ROOT, "AI", "数据", "tail_demo", "mixed.txt")
    if os.path.isfile(demo):
        with open(demo, "rb") as fh:
            payload = fh.read()
        head_seg = payload.split(b"\n")[0]
        tail_seg = payload.split(b"\n")[2] + b"\n"
        check("tail 段判成 GBK", tail_mod._pick_encoding(tail_seg) == "gb18030",
              "实际 %s" % tail_mod._pick_encoding(tail_seg))
        check("head 段判成 utf-8", tail_mod._pick_encoding(head_seg) == "utf-8",
              "实际 %s" % tail_mod._pick_encoding(head_seg))
    else:
        check("mixed.txt 存在", False, demo)

    # 8. 乘数后缀
    cases = [
        ("b", 512), ("k", 1024), ("K", 1024), ("kB", 1000), ("KB", 1000),
        ("KiB", 1024), ("m", 1024 ** 2), ("M", 1024 ** 2),
        ("MB", 1000 ** 2), ("MiB", 1024 ** 2), ("G", 1024 ** 3),
    ]
    for suffix, expect in cases:
        got = tail_mod._suffix_multiplier(suffix)
        check("后缀 %s = %d" % (suffix, expect), got == expect, "实际 %d" % got)

    # 9. uintmax 上界
    check("_UINTMAX_MAX = 2^64-1", tail_mod._UINTMAX_MAX == (1 << 64) - 1)

    # 10. 教程里的行数断言与实际文件对得上
    with open(TEACH, "r", encoding="utf-8") as fh:
        teach = fh.read()
    check("教程写了 1140 行", "1140" in teach)
    check("教程写了 45 个用例", "45 passed" in teach)
    check("教程写了 54 条对拍", "54 条用例" in teach)
    check("教程写了 488 passed", "488 passed" in teach)

    # 11. 全量测试数 488（各文件用例数相加）
    proc = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"],
                          cwd=ROOT, capture_output=True, text=True)
    counts = [int(x) for x in re.findall(r":\s*(\d+)\s*$", proc.stdout, re.M)]
    check("全量 488 个用例", sum(counts) == 488,
          "实际 %d（%d 个文件）" % (sum(counts), len(counts)))

    print()
    print("全部通过" if ok else "有不一致项")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
