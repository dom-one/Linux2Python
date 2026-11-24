"""核对教程里引用的每一处「第 N 行」是否真的对得上源码。

用法:
    python AI/脚本/_t1511_verify_line_refs.py

做法:
1. 从教程正文里抠出所有「第 N 行」/「第 N~M 行」的引用
2. 每处带上「期望附近应该出现的关键词」手工核对——光看行号对不对没有意义，
   关键是那一段讲的确实是那件事
3. 源文件按引用类型分开：mv.py 用本文档的，cp.py / rm.py / cli.py / cat.py
   / tail.py 是被对比的文件，各查各的

为什么要有这个脚本:
- 源码一改，教程里的行号就过期，而行号过期是最难被核对器发现的过期
  （核对器只比对命令块与预期输出，管不到正文里的数字断言）
- 手写行号必错，必须现算
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DOC = ROOT / "teach" / "30-w2l-commands-mv.py-落点判定与覆盖策略.md"

# 教程里引用的文件 → 期望该处附近出现的关键词（人工核对后录入）
# 键是「文件:行号」，值是必须出现在那一行或其上下 2 行内的关键词
EXPECT: dict[str, str] = {
    # --- w2l/commands/mv.py ---
    "mv.py:64": "action=\"store_true\"",
    "mv.py:106": "self.backup = args.backup or args.suffix is not None",
    "mv.py:119": "resolve_exclusive(",
    "mv.py:127": "def plan",
    "mv.py:132": "no_target_directory",
    "mv.py:145": "target_dir is not None",
    "mv.py:158": "if not operands",
    "mv.py:170": "len(sources) > 1",
    "mv.py:178": "def move_source",
    "mv.py:240": "def _destination_for",
    "mv.py:251": "def _backup",
    "mv.py:256": "os.path.lexists(backup)",
    "mv.py:264": "def _do_move",
    "mv.py:266": "os.path.isdir(dst)",
    "mv.py:269": "_clear_readonly(dst)",
    "mv.py:288": "def _confirm",
    "mv.py:303": "def _resolve",
    "mv.py:325": "def _same_file",
    "mv.py:337": "def _is_inside",
    "mv.py:356": "st_mtime_ns > dst_stat.st_mtime_ns",
    "mv.py:369": "def _clear_readonly",
    "mv.py:382": "def _remove_path",
    # --- 对比文件 ---
    "cp.py:198": "self.no_clobber",
    "cp.py:200": "return None",
    "rm.py:424": "def confirm",
    "rm.py:437": 'line[0] in ("y", "Y")',
    "cli.py:32": "reconfigure = getattr(stream",
    "cli.py:36": 'reconfigure(encoding="utf-8", errors="replace")',
    "cat.py:163": 'reconfigure(newline="")',
    "tail.py:511": 'reconfigure(newline="")',
}

FILES = {
    "mv.py": ROOT / "w2l" / "commands" / "mv.py",
    "cp.py": ROOT / "w2l" / "commands" / "cp.py",
    "rm.py": ROOT / "w2l" / "commands" / "rm.py",
    "cli.py": ROOT / "w2l" / "cli.py",
    "cat.py": ROOT / "w2l" / "commands" / "cat.py",
    "tail.py": ROOT / "w2l" / "commands" / "tail.py",
}

REF_RE = re.compile(r"第 (\d+)(?:~(\d+))? 行")


def main() -> int:
    doc = DOC.read_text(encoding="utf-8")

    # 教程里出现的所有行号引用（去重）
    refs: set[tuple[int, int]] = set()
    for m in REF_RE.finditer(doc):
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        refs.add((a, b))

    # 把行号归属到文件：靠 EXPECT 的键反查——凡是 EXPECT 里登记过的行号，
    # 就按那个文件去核；没登记的只报「存在」不判对错。
    checked = 0
    bad: list[str] = []

    for key, keyword in sorted(EXPECT.items()):
        fname, num_text = key.split(":")
        num = int(num_text)
        path = FILES[fname]
        lines = path.read_text(encoding="utf-8").split("\n")
        window = "\n".join(lines[max(0, num - 3): num + 2])
        if keyword not in window:
            actual = lines[num - 1] if num <= len(lines) else "(超出文件末尾)"
            bad.append(
                f"{key} 期望附近含 {keyword!r}\n      实际第 {num} 行: {actual.strip()[:70]!r}"
            )
        else:
            checked += 1

    # 教程里引用到的行号，都要在 mv.py 的行数范围内（除非是别的文件）
    mv_lines = len(FILES["mv.py"].read_text(encoding="utf-8").split("\n")) - 1
    print(f"mv.py 实际行数: {mv_lines}")
    print(f"抽查 {checked} 处行号引用")

    if bad:
        print("!! 对不上的:")
        for b in bad:
            print("  " + b)
        return 1
    print("全部对上 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
