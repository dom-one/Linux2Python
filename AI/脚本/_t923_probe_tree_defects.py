"""复核 tree.py 交接回来的三处缺陷：-x 全过滤、-P 少展开一层、目录联接不被认成链接。

本轮只做只读验证：不改源码，只把实测结果落盘，供修实现时对照。

产出：AI/数据/tree_defects_probe.txt
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "tree_defect_demo"
OUT = ROOT / "AI" / "数据" / "tree_defects_probe.txt"

lines: list[str] = []


def emit(text: str = "") -> None:
    lines.append(text)


def run_tree(argv: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "tree"] + argv,
        cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def make_fixture() -> Path:
    """三层夹具：root/hit/direct.txt + root/hit/mid/leaf.txt + root/hit/mid/leaf2.txt。"""
    if DATA.is_dir():
        return DATA
    root = DATA / "tree_deep"
    hit = root / "hit"
    mid = hit / "mid"
    mid.mkdir(parents=True)
    (hit / "direct.txt").write_bytes(b"d" * 5)
    (mid / "leaf.txt").write_bytes(b"l" * 4)
    (mid / "leaf2.txt").write_bytes(b"l" * 4)
    return root


def probe_x() -> None:
    """缺陷 1：-x 在 Windows 上把整棵树都过滤掉了。"""
    emit("=" * 72)
    emit("缺陷 1：-x（一文件系统）")
    emit("=" * 72)
    emit()
    root = make_fixture()

    emit("--- 1a. DirEntry.stat() 与 os.stat() 的 st_dev 对比 ---")
    scanner = os.scandir(root)
    with scanner:
        for item in scanner:
            try:
                dst = item.stat(follow_symlinks=False)
            except OSError:
                continue
            ost = os.stat(item.path, follow_symlinks=False)
            emit("  条目：%s" % item.name)
            emit("    DirEntry.stat(): st_dev=%s st_ino=%s" % (dst.st_dev, dst.st_ino))
            emit("    os.stat(path)  : st_dev=%s st_ino=%s" % (ost.st_dev, ost.st_ino))
            emit("    两者 st_dev 相等：%s" % (dst.st_dev == ost.st_dev))
            break

    emit()
    emit("--- 1b. 根目录的 st_dev（state.root_dev 的来源）---")
    emit("  root.lstat().st_dev = %s" % root.lstat().st_dev)

    emit()
    emit("--- 1c. tree -x 与 tree 的输出对比 ---")
    code_plain, out_plain, _ = run_tree([str(root)], cwd=ROOT)
    code_x, out_x, _ = run_tree(["-x", str(root)], cwd=ROOT)
    emit("  tree（不带 -x）退出码 %s，输出 %d 行" % (code_plain, len(out_plain.splitlines())))
    emit("  tree -x      退出码 %s，输出 %d 行" % (code_x, len(out_x.splitlines())))
    emit("  -x 的输出：")
    for line in out_x.splitlines():
        emit("    | %s" % line)
    emit()
    emit("  结论：-x 输出为空则说明整棵树被过滤掉了（缺陷成立）")
    emit()


def probe_pattern() -> None:
    """缺陷 2：-P 命中目录时少展开一层。"""
    emit("=" * 72)
    emit("缺陷 2：-P（只列匹配的文件）命中目录时的展开范围")
    emit("=" * 72)
    emit()
    root = make_fixture()

    for pattern in ("hit", "mid"):
        emit("--- tree -P '%s' ---" % pattern)
        code, out, _ = run_tree(["-P", pattern, str(root)], cwd=ROOT)
        emit("  退出码 %s" % code)
        for line in out.splitlines():
            emit("    | %s" % line)
        emit()

    emit("  GNU 的规则：目录命中 -P 时，它下面的内容全部列出。")
    emit("  预期 -P 'hit'：hit 下的 direct.txt 与 mid/ 下的两个文件都要列出来")
    emit("  预期 -P 'mid'：mid 下的 leaf.txt 与 leaf2.txt 要列出来")
    emit()


def probe_junction() -> None:
    """缺陷 3：目录联接不被认成符号链接。"""
    emit("=" * 72)
    emit("缺陷 3：目录联接（junction）")
    emit("=" * 72)
    emit()
    base = DATA / "junction_demo"
    if base.is_dir():
        return
    target = base / "sub"
    target.mkdir(parents=True)
    (target / "inside.txt").write_bytes(b"i" * 6)
    link = base / "link_to_sub"
    # 目录联接不需要管理员权限（符号链接才需要）
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    emit("  建联接的退出码：%s" % proc.returncode)
    emit("  建联接的输出：%s" % (proc.stdout.strip() or proc.stderr.strip()))
    if proc.returncode != 0:
        emit("  建不了联接，本条缺陷本轮无法实测")
        emit()
        return

    emit()
    emit("--- 3a. Python 怎么看这个联接 ---")
    st = link.lstat()
    emit("  lstat().st_mode      = %o" % st.st_mode)
    emit("  S_ISLNK              = %s" % stat.S_ISLNK(st.st_mode))
    emit("  S_ISDIR              = %s" % stat.S_ISDIR(st.st_mode))
    emit("  os.path.islink()     = %s" % os.path.islink(link))
    try:
        emit("  os.readlink()        = %s" % os.readlink(link))
    except OSError as exc:
        emit("  os.readlink()        失败：%s" % exc)

    emit()
    emit("--- 3b. tree 对联接的处理（-l 是跟随链接）---")
    for extra in ([], ["-l"]):
        code, out, err = run_tree(extra + [str(base)], cwd=ROOT)
        emit("  tree %s 退出码 %s" % (" ".join(extra) or "(不带 -l)", code))
        for line in out.splitlines():
            emit("    | %s" % line)
        if err.strip():
            emit("    stderr: %s" % err.strip().splitlines()[0])
        emit()

    emit("  GNU 的规则：符号链接默认不展开，-l 才跟随。")
    emit("  联接若不被认成链接，就会无条件展开，同一份内容列两遍。")
    emit()


def main() -> None:
    probe_x()
    probe_pattern()
    probe_junction()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("已写出 %s（%d 行）" % (OUT, len(lines)))


if __name__ == "__main__":
    main()
