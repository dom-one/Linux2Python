"""为 ls 教程采集真实输出：逐条跑命令，把退出码与原始输出写进文件。

用途：teach/19 教程的「怎么用」段落要求命令可直接跑、预期输出准确，
所以先真跑一遍再照抄，避免写出与实现不符的示例。

输出写到 AI/数据/_t49_ls_probe.txt（UTF-8），便于逐行核对。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "main.py"
OUT = ROOT / "AI" / "数据" / "_t49_ls_probe.txt"

lines: list[str] = []


def run(args: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(MAIN), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def show(title: str, ls_args: list[str], cwd: Path) -> None:
    code, out, err = run(["ls", *ls_args], cwd)
    lines.append("=" * 70)
    lines.append(f"# {title}")
    lines.append(f"$ python main.py ls {' '.join(ls_args)}".rstrip())
    lines.append(f"[exit={code}]")
    if out:
        lines.append("--- stdout ---")
        lines.append(out.rstrip("\n"))
    if err:
        lines.append("--- stderr ---")
        lines.append(err.rstrip("\n"))
    lines.append("")


def build_tree(base: Path) -> Path:
    tree = base / "demo"
    tree.mkdir()
    (tree / "alpha.txt").write_text("hello\n", encoding="utf-8")
    (tree / "Beta.txt").write_text("B\n", encoding="utf-8")
    (tree / "gamma.log").write_text("x" * 2048, encoding="utf-8")
    (tree / "big.bin").write_bytes(b"\x00" * 5000)
    (tree / ".hidden").write_text("h\n", encoding="utf-8")
    (tree / "run.bat").write_text("@echo off\n", encoding="ascii")
    (tree / "empty").mkdir()
    sub = tree / "sub"
    sub.mkdir()
    (sub / "deep.txt").write_text("deep\n", encoding="utf-8")
    nested = sub / "nested"
    nested.mkdir()
    (nested / "leaf.txt").write_text("leaf\n", encoding="utf-8")
    return tree


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="ls_probe_"))
    try:
        tree = build_tree(base)

        show("默认：列当前目录（临时树）", [], tree)
        show("-a 含 . 与 ..", ["-a"], tree)
        show("-A 隐藏条目但不含 . 与 ..", ["-A"], tree)
        show("-l 长格式", ["-l"], tree)
        show("-lh 人类可读大小", ["-lh"], tree)
        show("-F 类型标记", ["-F"], tree)
        show("-d 列目录本身", ["-d", "sub"], tree)
        show("-R 递归", ["-R"], tree)
        show("-r 反序", ["-r"], tree)
        show("多操作数：文件先于目录块", ["gamma.log", "alpha.txt", "sub"], tree)
        show("多操作数：块之间空一行", ["alpha.txt", "sub"], tree)
        show("文件操作数原样打印", ["alpha.txt"], tree)
        show("不存在的路径 → 退出码 2", ["nope"], tree)
        show("出错不影响其他操作数", ["nope", "alpha.txt"], tree)
        show("空目录 → 退出码 1", ["empty"], tree)

        show("项目真实目录：ls", [], ROOT)
        show("项目真实目录：ls -l w2l", ["-l", "w2l"], ROOT)
        show("项目真实目录：ls -lh w2l/commands", ["-lh", "w2l/commands"], ROOT)
        show("项目真实目录：ls -R w2l/commands", ["-R", "w2l/commands"], ROOT)
        show("项目真实目录：ls -F w2l/commands", ["-F", "w2l/commands"], ROOT)
        show("项目真实目录：ls -t w2l", ["-t", "w2l"], ROOT)
        show("项目真实目录：ls -S w2l/commands", ["-S", "w2l/commands"], ROOT)
        show("项目真实目录：ls -d w2l/commands", ["-d", "w2l/commands"], ROOT)
        show("项目真实目录：ls -a w2l", ["-a", "w2l"], ROOT)
        show("项目真实目录：ls -A w2l", ["-A", "w2l"], ROOT)
    finally:
        shutil.rmtree(base, ignore_errors=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"written: {OUT}")
    print(f"lines: {len(lines)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
