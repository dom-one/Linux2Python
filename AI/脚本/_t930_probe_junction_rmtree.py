"""验证 shutil.rmtree 遇到目录联接时的行为（写联接测试前的安全检查）。

要确认两件事：
1. rmtree 不会顺着联接把「目标目录」的内容删掉
2. rmtree 会不会因为联接报错（报错的话 pytest 的 tmp_path 清理会挂）

产出：AI/数据/junction_rmtree_probe.txt

用法:
    python AI/脚本/_t930_probe_junction_rmtree.py
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "junction_rmtree_probe.txt"

lines: list[str] = []


def note(text: str = "") -> None:
    lines.append(text)


def main() -> None:
    note("=" * 70)
    note("shutil.rmtree 遇到目录联接的行为")
    note("=" * 70)
    note()

    base = Path(tempfile.mkdtemp(prefix="junct_probe_"))
    target = base / "target"
    target.mkdir()
    (target / "keep.txt").write_text("不能被删掉\n", encoding="utf-8")
    holder = base / "holder"
    holder.mkdir()
    link = holder / "link_to_target"

    note("目标目录：%s" % target)
    note("目标里的文件：%s" % (target / "keep.txt"))
    note()

    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    note("mklink /J 退出码 = %d" % proc.returncode)
    note("mklink 输出：%s" % (proc.stdout or proc.stderr).strip())
    note()

    if link.exists():
        st = os.stat(link, follow_symlinks=False)
        note("联接的 lstat：S_ISLNK=%s S_ISDIR=%s reparse=%s"
             % (stat.S_ISLNK(st.st_mode), stat.S_ISDIR(st.st_mode), getattr(st, "st_reparse_tag", None)))
        note("scandir 看到的 is_dir(follow_symlinks=False)：%s"
             % next(iter(os.scandir(holder))).is_dir(follow_symlinks=False))
        note("os._walk_symlinks_as_files 存在：%s" % hasattr(os, "_walk_symlinks_as_files"))
        note()

    note("--- 试 shutil.rmtree(holder) ---")
    try:
        shutil.rmtree(holder)
        note("  rmtree 正常结束，没有报错")
    except Exception as exc:  # noqa: BLE001 - 就是要看它报不报错
        note("  rmtree 报错：%r" % (exc,))
    note()

    note("  目标文件还在吗：%s" % ((target / "keep.txt").exists()))
    note("  目标目录还在吗：%s" % target.exists())
    note("  holder 还在吗：%s" % holder.exists())
    note()

    note("--- 试 os.rmdir 直接删联接 ---")
    if link.exists():
        try:
            os.rmdir(link)
            note("  os.rmdir(联接) 成功")
        except Exception as exc:  # noqa: BLE001
            note("  os.rmdir(联接) 报错：%r" % (exc,))
    note("  目标文件还在吗：%s" % ((target / "keep.txt").exists()))
    note()

    note("--- 试 os.unlink 直接删联接 ---")
    if link.exists():
        try:
            os.unlink(link)
            note("  os.unlink(联接) 成功")
        except Exception as exc:  # noqa: BLE001
            note("  os.unlink(联接) 报错：%r" % (exc,))
    note("  目标文件还在吗：%s" % ((target / "keep.txt").exists()))
    note()

    shutil.rmtree(base, ignore_errors=True)
    note("探针结果已写入 %s" % OUT)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
