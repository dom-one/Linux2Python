"""实测 tree 修完三处缺陷后的行为，作为写回归测试的依据。

三处缺陷（教程 teach/25 交接回来的）：
1. -x 在 Windows 上把整棵树都过滤掉了（DirEntry.stat() 的 st_dev 恒为 0）
2. -P 命中目录时少展开一层（child_active 算晚了一级）
3. 目录联接不被认成符号链接（无条件展开 + 自引用递归 64 层）

产出：AI/数据/tree_fix_probe.txt

用法:
    python AI/脚本/_t929_probe_tree_fixed.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEST = ROOT / "AI" / "数据" / "tree_fix_demo"

MAIN = ROOT / "main.py"
OUT = ROOT / "AI" / "数据" / "tree_fix_probe.txt"

lines: list[str] = []


def note(text: str = "") -> None:
    lines.append(text)


def run(args: list[str], cwd: Path) -> tuple[int, str, str]:
    """跑一次 python main.py tree <args>，返回 (退出码, 标准输出, 标准错误)。"""
    proc = subprocess.run(
        [sys.executable, str(MAIN), "tree", *args],
        cwd=str(cwd),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def show(title: str, args: list[str], cwd: Path) -> None:
    code, out, err = run(args, cwd)
    note("--- %s：tree %s（cwd=%s）" % (title, " ".join(args), cwd.name))
    note("  退出码 = %d" % code)
    for line in out.splitlines():
        note("  | " + line)
    if err.strip():
        for line in err.splitlines():
            note("  ! " + line)
    note()


def make_junction(link: Path, target: Path) -> bool:
    """用 mklink /J 建目录联接（不需要管理员权限）。"""
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode == 0


def build() -> Path:
    if DEST.exists():
        shutil.rmtree(DEST, ignore_errors=True)
    base = DEST / "base"
    base.mkdir(parents=True)
    (base / "a.txt").write_bytes(b"a\n")
    (base / "b.txt").write_bytes(b"b\n")
    sub = base / "sub"
    sub.mkdir()
    (sub / "inside.txt").write_bytes(b"inside\n")
    hit = base / "hit"
    hit.mkdir()
    (hit / "direct.txt").write_bytes(b"direct\n")
    mid = hit / "mid"
    mid.mkdir()
    (mid / "leaf.txt").write_bytes(b"leaf\n")
    (mid / "leaf2.txt").write_bytes(b"leaf2\n")
    return base


def main() -> None:
    base = build()
    note("=" * 70)
    note("tree 三处缺陷修复后的实测")
    note("=" * 70)
    note()

    note("### 一、-x：同一卷的树必须照常列出来（修之前整棵树是空的）")
    show("-x 正常树", ["-x", "."], base)
    show("不带 -x 对照", ["."], base)
    note()

    note("### 二、-P：命中目录时它下面的内容全部列出")
    show("-P hit", ["-P", "hit", "."], base)
    show("-P mid", ["-P", "mid", "."], base)
    show("-P *.txt", ["-P", "*.txt", "."], base)
    note()

    note("### 三、目录联接：当成链接，默认不展开")
    link = base / "link_to_sub"
    ok = make_junction(link, base / "sub")
    note("  建联接 link_to_sub -> sub：%s" % ("成功" if ok else "失败"))
    if not ok:
        note("  建联接失败，后面的联接用例跳过")
        note()
        (ROOT / "AI" / "数据").mkdir(parents=True, exist_ok=True)
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        return

    show("默认（不跟随）", ["."], base)
    show("-l 跟随", ["-l", "."], base)
    show("-F 类型标记", ["-F", "."], base)
    note()

    note("### 四、自引用联接：不能一路递归下去")
    loop = base / "loop"
    ok2 = make_junction(loop, base)
    note("  建自引用联接 loop -> base：%s" % ("成功" if ok2 else "失败"))
    if ok2:
        show("默认（不跟随）", ["."], base)
        show("-l 跟随（应报 recursive, not followed）", ["-l", "."], base)
    note()

    note("### 五、跨卷的 -x 语义（需要第二个卷）")
    other = None
    for candidate in ("C:/Windows/Temp", "C:/Temp"):
        p = Path(candidate)
        if p.is_dir():
            other = p
            break
    if other is None:
        note("  没找到第二个卷，跳过")
    else:
        note("  第二个卷取 %s" % other)
        probe = DEST / "xdev"
        probe.mkdir(parents=True, exist_ok=True)
        (probe / "local.txt").write_bytes(b"local\n")
        xlink = probe / "xlink"
        if make_junction(xlink, other):
            note("  建跨卷联接 xlink -> %s：成功" % other)
            show("-x（跨卷目录应打印但不展开）", ["-x", "."], probe)
            show("-l -x（跨卷目录仍不展开）", ["-l", "-x", "."], probe)
            show("-l（不加 -x，跟随跨卷目录）", ["-l", "."], probe)
        else:
            note("  建跨卷联接失败，跳过")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("探针结果已写入 %s（%d 行）" % (OUT, len(lines)))


if __name__ == "__main__":
    main()
