"""检查本轮（tick #11）新增的所有脚本与产出文件里没有 U+FFFD 坏字符。

坏字符是写盘时编码转换吃掉的，肉眼看不出来，必须用字节扫描查。
历史文件（_t99 等上一轮就有的）不在本轮范围内，单独报出来。

用法:
    python AI/脚本/_t922_scan_mojibake.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

# 本轮新增/修改的文件
FILES = [
    "AI/教程进度.md",
    "teach/00-项目总览与阅读顺序.md",
    "teach/26-w2l-commands-du.py-统计口径与去重规则.md",
] + [
    "AI/脚本/_t%03d_%s" % (n, name)
    for n, name in [
        (900, "make_du_fixture.py"),
        (901, "diff_du_gnu.py"),
        (902, "probe_du_edges.py"),
        (903, "probe_du_focus.py"),
        (904, "probe_du_junction.py"),
        (905, "probe_du_h_boundary.py"),
        (906, "probe_du_extra.py"),
        (907, "probe_du_loop_x.py"),
        (908, "verify_du_claims.py"),
        (909, "probe_du_last.py"),
        (910, "probe_du_x_mechanism.py"),
        (911, "probe_du_x_path.py"),
        (912, "probe_du_h_band.py"),
        (913, "make_du_junction.py"),
        (914, "make_teach26.py"),
        (915, "update_teach00.py"),
        (916, "run_full_verify.py"),
        (917, "probe_du_selfref_x.py"),
        (918, "update_progress_status.py"),
        (919, "append_tick11.py"),
        (920, "fix_tick11_mojibake.py"),
        (921, "fix_append_script_mojibake.py"),
        (922, "scan_mojibake.py"),
    ]
]


def main() -> int:
    bad = 0
    missing = 0
    for rel in FILES:
        path = ROOT / rel
        if not path.is_file():
            print("  缺失: %s" % rel)
            missing += 1
            continue
        raw = path.read_bytes()
        count = raw.count(b"\xef\xbf\xbd")
        if count:
            print("  有坏字符: %s（%d 处）" % (rel, count))
            index = 0
            while True:
                index = raw.find(b"\xef\xbf\xbd", index)
                if index < 0:
                    break
                start = max(0, index - 30)
                print("      ...%s..." % raw[start:index + 20].decode("utf-8", "replace"))
                index += 3
            bad += 1
        else:
            print("  干净: %s" % rel)

    print()
    print("合计: 检查 %d 个文件，坏 %d 个，缺失 %d 个" % (len(FILES), bad, missing))
    return 1 if (bad or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
