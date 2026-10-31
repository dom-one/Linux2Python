"""把本实现的 ls 输出跟 Git Bash 里的 GNU ls 逐条对照。

同一棵目录树、同一组选项，两边各跑一遍，比对「结构」：
块的划分、标题行、条目顺序、空行分隔。

长格式（-l）只比对条目名，权限列、属主列、total 行在 Windows 上与 GNU
本来就不一样，属于有意为之的差异，不在这里比。

用法：python AI/脚本/_t19_compare_ls.py
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.conftest import run_ls  # noqa: E402

# 参考树必须放在纯 ASCII 路径下：MSYS 的 bash 映射不了带中文的工作目录，
# 待在中文目录里跑 GNU ls 会直接报 ERROR_PATH_NOT_FOUND。
DATA = ROOT / "AI" / "ls_ref_tmp"


def build_tree() -> None:
    if DATA.exists():
        for item in sorted(DATA.rglob("*"), reverse=True):
            if item.is_file():
                os.chmod(item, 0o666)
                item.unlink()
            elif item.is_dir():
                item.rmdir()
        DATA.rmdir()
    DATA.mkdir(parents=True)

    (DATA / "alpha.txt").write_text("hello\n", encoding="utf-8")
    (DATA / "Beta.txt").write_text("B\n", encoding="utf-8")
    (DATA / "gamma.log").write_text("x" * 2048, encoding="utf-8")
    (DATA / "big.bin").write_bytes(b"\x00" * 5000)
    (DATA / ".hidden").write_text("h\n", encoding="utf-8")
    (DATA / "run.bat").write_text("@echo off\n", encoding="ascii")
    (DATA / "emptydir").mkdir()

    sub = DATA / "sub"
    sub.mkdir()
    (sub / "deep.txt").write_text("deep\n", encoding="utf-8")
    (sub / "nested").mkdir()
    (sub / "nested" / "leaf.txt").write_text("leaf\n", encoding="utf-8")


def gnu_ls(args: list[str]) -> str:
    """在 Git Bash 里跑 GNU ls。

    两个坑：
    1. 不能写死 "bash"：CreateProcess 找可执行文件时 System32 优先于 PATH，
       会先命中 C:\\Windows\\System32\\bash.exe（WSL 启动器），它会去挂载
       D:\\WSL\\ext4.vhdx 并报 MountDiskPath / ERROR_PATH_NOT_FOUND。
       必须用 shutil.which 拿到 Git Bash 的绝对路径。
    2. 不用 cd 进目录：MSYS 处理带中文的路径会失败，直接把工作目录
       设成 Windows 路径，让 bash 自己继承。
    """
    bash = shutil.which("bash")
    if bash is None:
        raise RuntimeError("找不到 bash，无法与 GNU ls 对照")
    quoted = " ".join(f"'{arg}'" for arg in args)
    result = subprocess.run(
        [bash, "-c", f"ls {quoted}"],
        cwd=str(DATA),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode not in (0, 1, 2):
        raise RuntimeError(f"GNU ls 执行失败: {result.stderr}")
    return result.stdout


def structure(text: str) -> list[str]:
    """抽出结构信息：标题行与条目名，忽略长格式的前导列。"""
    lines = []
    for line in text.splitlines():
        if not line.strip():
            lines.append("<blank>")
            continue
        if line.endswith(":") and " " not in line:
            lines.append(f"HEADER {line}")
            continue
        if line.startswith("total "):
            continue
        if re.match(r"^[-dlps][rwx-]{9}\s", line):
            lines.append(f"NAME {line.split()[-1]}")
            continue
        lines.append(f"NAME {line}")
    return lines


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build_tree()
    cases: list[list[str]] = [
        [],
        ["-a"],
        ["-A"],
        ["-F"],
        ["-R"],
        ["-l"],
        ["-t"],
        ["-S"],
        ["-r"],
        ["-d", "sub"],
        ["gamma.log", "alpha.txt", "sub"],
        ["-R", "."],
    ]

    failures = 0
    report: list[str] = []
    for case in cases:
        gnu = structure(gnu_ls(case))
        _, mine_out, _ = run_ls(case, cwd=DATA)
        mine = structure(mine_out)
        label = "ls " + " ".join(case)
        if gnu == mine:
            report.append(f"[一致] {label}")
            continue
        failures += 1
        report.append(f"[不一致] {label}")
        report.append(f"   GNU : {gnu}")
        report.append(f"   本实现: {mine}")

    report.append("")
    report.append(f"共 {len(cases)} 组，不一致 {failures} 组")

    target = ROOT / "AI" / "数据" / "ls_compare.txt"
    target.write_text("\n".join(report) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n".join(report))
    print(f"报告已写入 {target}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
