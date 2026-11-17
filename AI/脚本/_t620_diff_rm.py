"""AI/脚本/_t620_diff_rm.py —— 本实现的 rm 与 GNU rm 8.32 的差分对照。

用法:
    python AI/脚本/_t620_diff_rm.py

输出:
    AI/数据/rm_diff_out.txt

对照口径（GNU 的退出码 1 在本项目里对应 2，所以只比「是否为 0」）：

- 退出码：是否成功
- 目录树：删完之后剩下的东西必须完全一致
- 标准输出：-v 的文案两边逐字比对（本实现沿用 GNU 文案）
- 提示条数：stderr 里 "? " 的个数必须一致
- 报错路径：报错消息里引号包起来的路径集合必须一致
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
ROOT = AI_DIR.parent
DATA = AI_DIR / "数据"
GNU_RM = Path(r"E:\software\Git\Git\usr\bin\rm.exe")
OUT = DATA / "rm_diff_out.txt"

# 现场：4 个文件 + 一个两层目录 + 一个空目录。
BASE = [
    ("a.txt", "alpha\n"),
    ("b.txt", "beta\n"),
    ("c.txt", "gamma\n"),
    ("other.txt", "other\n"),
    ("dir", None),
    ("dir/inner.txt", "inner\n"),
    ("dir/sub", None),
    ("dir/sub/deep.txt", "deep\n"),
    ("empty", None),
]

# (名字, 参数, 标准输入, 追加现场, 只读文件)
SCENARIOS = [
    ("无操作数", [], "", [], []),
    ("不存在的文件", ["nope.txt"], "", [], []),
    ("删普通文件", ["a.txt"], "", [], []),
    ("删目录（无 -r）", ["dir"], "", [], []),
    ("递归删除", ["-r", "dir"], "", [], []),
    ("-d 空目录", ["-d", "empty"], "", [], []),
    ("-d 非空目录", ["-d", "dir"], "", [], []),
    ("-d 普通文件", ["-d", "a.txt"], "", [], []),
    ("-v 递归", ["-v", "-r", "dir"], "", [], []),
    ("-v 多个文件", ["-v", "a.txt", "b.txt"], "", [], []),
    ("-v 带 ./ 前缀", ["-v", "-r", "./dir"], "", [], []),
    ("-f 不存在的文件", ["-f", "nope.txt"], "", [], []),
    ("-f 缺操作数", ["-f"], "", [], []),
    ("-f 目录（无 -r）", ["-f", "dir"], "", [], []),
    ("-f 递归", ["-f", "-r", "dir"], "", [], []),
    ("-i 全部同意", ["-i", "a.txt", "b.txt"], "y\ny\n", [], []),
    ("-i 拒绝第一个", ["-i", "a.txt", "b.txt"], "n\ny\n", [], []),
    ("-i 拒绝第二个", ["-i", "a.txt", "b.txt"], "y\nn\n", [], []),
    ("-i 递归全同意", ["-i", "-r", "dir"], "y\ny\ny\ny\n", [], []),
    ("-i 递归拒绝进入", ["-i", "-r", "dir"], "n\n", [], []),
    ("-i 递归拒绝进入子目录", ["-i", "-r", "dir"], "y\ny\nn\n", [], []),
    ("-i 递归拒绝文件后仍问父目录", ["-i", "-r", "dir"], "y\nn\ny\ny\ny\ny\n", [], []),
    ("-i 两个操作数", ["-i", "a.txt", "dir"], "y\ny\ny\ny\ny\n", [], []),
    ("-i 递归拒绝文件", ["-i", "-r", "dir"], "y\nn\ny\n", [], []),
    ("-i 空目录", ["-i", "-d", "empty"], "y\n", [], []),
    ("-i 缺操作数", ["-i"], "", [], []),
    ("-I 三个文件不问", ["-I", "a.txt", "b.txt", "c.txt"], "", [], []),
    ("-I 四个文件问一次", ["-I", "a.txt", "b.txt", "c.txt", "other.txt"], "y\n", [], []),
    ("-I 递归问一次", ["-I", "-r", "dir"], "y\n", [], []),
    ("-I 递归拒绝", ["-I", "-r", "dir"], "n\n", [], []),
    ("--interactive=never", ["--interactive=never", "a.txt"], "", [], []),
    ("--interactive=once", ["--interactive=once", "a.txt"], "", [], []),
    ("--interactive=always", ["--interactive=always", "a.txt"], "y\n", [], []),
    ("--interactive 裸写", ["--interactive", "a.txt"], "y\n", [], []),
    ("--interactive 空格形式", ["--interactive", "once"], "", [], []),
    ("--interactive 无效值", ["--interactive=bad", "a.txt"], "", [], []),
    ("--interactive 缩写", ["--inter=once", "a.txt"], "", [], []),
    ("rm -r .", ["-r", "."], "", [], []),
    ("rm -r sub/.", ["-r", "dir/sub/."], "", [], []),
    ("只读文件", ["-r", "dir"], "", [], ["dir/inner.txt"]),
    ("重复同一文件", ["a.txt", "a.txt"], "", [], []),
    ("-- 分隔", ["--", "a.txt"], "", [], []),
    ("-f -i 顺序", ["-f", "-i", "a.txt"], "", [], []),
    ("-i -f 顺序", ["-i", "-f", "a.txt"], "", [], []),
    ("-f --interactive=never", ["-f", "--interactive=never", "nope.txt"], "", [], []),
    ("--interactive=never -f", ["--interactive=never", "-f", "nope.txt"], "", [], []),
    ("--interactive=always -f", ["--interactive=always", "-f", "nope.txt"], "", [], []),
    ("多操作数其中一个不存在", ["a.txt", "nope.txt"], "", [], []),
    ("-r 与 -d 同时", ["-r", "-d", "dir"], "", [], []),
]


def build(base: Path, extra: list[tuple[str, str | None]], readonly: list[str]) -> None:
    for rel, content in BASE:
        target = base / rel
        if content is None:
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    for rel, content in extra:
        target = base / rel
        if content is None:
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    for rel in readonly:
        os.chmod(base / rel, 0o444)


def snapshot(base: Path) -> list[str]:
    items: list[str] = []
    for current, dirs, files in os.walk(base):
        rel = os.path.relpath(current, base)
        for name in sorted(dirs):
            items.append(f"D {os.path.join(rel, name)}")
        for name in sorted(files):
            items.append(f"F {os.path.join(rel, name)}")
    return sorted(items)


def strip_prompts(text: str) -> str:
    """把提示语从 stderr 里摘掉，剩下的就是错误消息。"""
    out = text
    while True:
        index = out.find("? ")
        if index < 0:
            return out
        out = out[index + 2:]


def quoted_paths(text: str) -> set[str]:
    """取出报错消息里引号包起来的路径。

    过滤两类噪音：GNU 的 "Try 'xxx --help' for more information." 提示行，
    以及选项名（以 - 开头，例如 '--interactive' 的可选值列表）。
    """
    kept: list[str] = []
    for line in text.splitlines():
        if line.startswith("Try '"):
            continue
        # GNU 报错时会附一串「合法取值」，那些不是路径。
        if line.startswith("Valid arguments are:") or line.startswith("  - "):
            continue
        kept.append(line)
    paths = set()
    for item in re.findall(r"'([^']*)'", "\n".join(kept)):
        if item.startswith("-"):
            continue
        paths.add(item)
    return paths


def run_gnu(cwd: Path, argv: list[str], stdin_text: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        [str(GNU_RM), *argv],
        cwd=str(cwd),
        input=stdin_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_ours(cwd: Path, argv: list[str], stdin_text: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "rm", *argv],
        cwd=str(cwd),
        input=stdin_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    if not GNU_RM.exists():
        print(f"找不到 GNU rm: {GNU_RM}")
        return 2

    DATA.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    failures = 0

    for name, argv, stdin_text, extra, readonly in SCENARIOS:
        workdir = Path(tempfile.mkdtemp(prefix="rmdiff_"))
        gnu_dir = workdir / "gnu"
        ours_dir = workdir / "ours"
        gnu_dir.mkdir()
        ours_dir.mkdir()
        build(gnu_dir, extra, readonly)
        build(ours_dir, extra, readonly)

        try:
            g_rc, g_out, g_err = run_gnu(gnu_dir, argv, stdin_text)
            o_rc, o_out, o_err = run_ours(ours_dir, argv, stdin_text)
            g_tree = snapshot(gnu_dir)
            o_tree = snapshot(ours_dir)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        checks = {
            # GNU 出错用 1、本项目用 2，所以只比「成功 / 失败」这一位。
            "退出码": ((g_rc == 0) == (o_rc == 0), True),
            "目录树": (g_tree == o_tree, True),
            "标准输出": (g_out == o_out, True),
            "提示条数": (g_err.count("? ") == o_err.count("? "), True),
            "报错路径": (
                quoted_paths(strip_prompts(g_err)) == quoted_paths(strip_prompts(o_err)),
                True,
            ),
        }
        bad = [key for key, (ok, _) in checks.items() if not ok]
        if bad:
            failures += 1

        lines.append("=" * 74)
        lines.append(f"[{name}] argv={argv} stdin={stdin_text!r}")
        lines.append(f"  GNU  rc={g_rc} out={g_out!r}")
        lines.append(f"  本实现 rc={o_rc} out={o_out!r}")
        lines.append(f"  GNU  err={g_err!r}")
        lines.append(f"  本实现 err={o_err!r}")
        lines.append(f"  GNU  tree={g_tree}")
        lines.append(f"  本实现 tree={o_tree}")
        lines.append(f"  判定 = {'一致' if not bad else '不一致: ' + ', '.join(bad)}")

    lines.append("=" * 74)
    lines.append(f"### 共 {len(SCENARIOS)} 个场景，不一致 {failures} 个")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已写出 {OUT}")
    print(f"共 {len(SCENARIOS)} 个场景，不一致 {failures} 个")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
