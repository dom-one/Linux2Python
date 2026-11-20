"""查清一件事：du 的 -x 到底拿哪个 st_dev 去比对。

怀疑：os.stat(path, follow_symlinks=False) 与 os.lstat(path) 在 Windows 上
对「目录联接」给的结果不一样，所以 _list_children 里的比对口径
和 _scan_operand 里的根目录口径不是同一个。

产出：AI/数据/du_x_mechanism.txt
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "AI" / "数据" / "du_demo"
OUT = ROOT / "AI" / "数据" / "du_x_mechanism.txt"

lines: list[str] = []


def emit(text: str = "") -> None:
    lines.append(text)


def main() -> None:
    temp = Path(os.environ.get("TEMP", r"C:\Windows\Temp"))
    xdir = temp / "w2l_du_x3"
    xdir.mkdir(exist_ok=True)
    cross = xdir / "to_e"
    if cross.exists():
        subprocess.run(["cmd", "/c", "rmdir", str(cross)], capture_output=True)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(cross), str(DATA / "tree")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not cross.exists():
        print("建不了跨卷联接")
        return 1

    target = DATA / "tree"
    emit("源目录 : %s" % xdir)
    emit("联接   : %s -> %s" % (cross, target))
    emit()

    emit("各种 stat 口径的结果：")
    emit("  %-46s %-22s %-22s" % ("调用", "st_dev", "st_ino"))
    variants = [
        ("os.lstat(联接)", lambda p: os.lstat(p)),
        ("os.stat(联接)", lambda p: os.stat(p)),
        ("os.stat(联接, follow_symlinks=False)",
         lambda p: os.stat(p, follow_symlinks=False)),
        ("os.stat(联接, follow_symlinks=True)",
         lambda p: os.stat(p, follow_symlinks=True)),
    ]
    for label, fn in variants:
        st = fn(str(cross))
        emit("  %-46s %-22d %-22d" % (label, st.st_dev, st.st_ino))

    emit()
    emit("  对照：")
    for label, path in [("os.stat(源目录)", xdir), ("os.stat(目标)", target)]:
        st = os.stat(str(path))
        emit("  %-46s %-22d %-22d" % (label, st.st_dev, st.st_ino))
    emit()

    # 项目实际走的两条路径
    root_stat = os.lstat(str(xdir))
    child_stat = os.stat(str(cross), follow_symlinks=False)
    emit("du 内部实际用的两个值：")
    emit("  根目录 root_dev  = os.lstat(源目录).st_dev = %d" % root_stat.st_dev)
    emit("  子项 child.st_dev = os.stat(联接, follow_symlinks=False).st_dev = %d" % child_stat.st_dev)
    emit("  两者相同？ %s" % (root_stat.st_dev == child_stat.st_dev))
    emit()
    if root_stat.st_dev != child_stat.st_dev:
        emit("  ⇒ 不相等，所以 -x 把联接挡住了。")
        emit("    原因：follow_symlinks=False 对「联接」没有生效，Python 仍然跟随到了目标，")
        emit("    拿到的 st_dev 是目标所在卷（E:），与根目录的 C: 不同。")
        emit("    而 os.lstat 对联接是有效的，给的是联接自己所在的卷（C:）。")
    else:
        emit("  ⇒ 相等，-x 挡不住。")
    emit()

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("机制查明写入: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
