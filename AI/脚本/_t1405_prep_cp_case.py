"""给 teach/29 的每个步骤准备一个干净的现场。

用法：
    python AI/脚本/_t1405_prep_cp_case.py <案例名>

产出目录：AI/数据/cp_demo/case/<案例名>/（在 .gitignore 里，不进仓库）

为什么要这个脚本：cp 的多数选项（-n / -u / -S / -i / --remove-destination）
的输出取决于「目标在不在、谁更新」，同一个命令跑第二遍结果就变了。
教程里的命令块要能被 AI/脚本/_t12_verify_teach.py 反复真跑，
所以每一步都得先把现场重建成同一个样子。

现场分两半：
- src/  源：hello.txt、legacy.txt、payload.bin、project/
- dst/  目标：old.txt（比源旧）、future.txt（比源新）

源和目标必须分开放在两个目录里：把源拷进它自己所在的目录，
落点就是源本身，会撞上「是同一个文件」的检查。

时间戳全部钉死：
- 源            2020-01-01 00:00:00 UTC
- dst/old.txt   2019-01-01 00:00:00 UTC（比源旧）
- dst/future.txt 2030-01-01 00:00:00 UTC（比源新）

这个脚本**不往 stdout 写任何东西**，因为教程里它和 cp 命令在同一个
命令块里，输出要被核对器逐字比对。
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEMO = ROOT / "AI" / "数据" / "cp_demo"
CASE_ROOT = DEMO / "case"

OLD = 1_577_836_800  # 2020-01-01 00:00:00 UTC
OLDER = 1_546_300_800  # 2019-01-01 00:00:00 UTC
NEWER = 1_893_456_000  # 2030-01-01 00:00:00 UTC

# 目标目录里预置的两个文件：一份比源旧、一份比源新。
TARGETS: dict[str, tuple[bytes, int]] = {
    "old.txt": (b"old content\r\n", OLDER),
    "future.txt": (b"future content\r\n", NEWER),
}


def pin(path: Path, stamp: int) -> None:
    os.utime(path, (stamp, stamp))


def build(target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    src = target / "src"
    dst = target / "dst"
    src.mkdir(parents=True)
    dst.mkdir(parents=True)

    # 源：从共享夹具复制一份，时间戳统一钉成 OLD
    for name in ("hello.txt", "legacy.txt", "payload.bin"):
        shutil.copy2(DEMO / name, src / name)
    shutil.copytree(DEMO / "project", src / "project")
    for path in sorted(src.rglob("*"), reverse=True):
        if path.is_file():
            pin(path, OLD)
    pin(src, OLD)

    # 目标：一个比源旧、一个比源新
    for name, (data, stamp) in TARGETS.items():
        path = dst / name
        path.write_bytes(data)
        pin(path, stamp)
    pin(dst, OLD)


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("用法: python AI/脚本/_t1405_prep_cp_case.py <案例名>\n")
        return 2
    build(CASE_ROOT / sys.argv[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
