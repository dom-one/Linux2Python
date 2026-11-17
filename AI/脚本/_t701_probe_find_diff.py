"""把本项目的 find 与 Git Bash 的 GNU find 4.10 逐场景对拍。

用法:
    python AI/脚本/_t701_probe_find_diff.py            # 跑全部场景
    python AI/脚本/_t701_probe_find_diff.py --only 名字 # 只跑某个场景

报告写到 AI/数据/find_diff_report.json。

对拍口径:
- 场景在夹具副本里跑，-delete 这类会改文件的场景每次都拿全新副本
- 只比标准输出；退出码单独记录（本项目「无结果=1 / 出错=2」与 GNU 不同）
- 路径分隔符两边都是正斜杠，可直接比
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DEMO = Path(ROOT) / "AI" / "数据" / "find_demo"
REPORT = Path(ROOT) / "AI" / "数据" / "find_diff_report.json"
MAIN = Path(ROOT) / "main.py"
BASH = r"E:\software\Git\Git\bin\bash.exe"

# (场景名, find 的完整参数)
SCENARIOS = [
    ("默认打印全部", [".", "-print"]),
    ("无表达式", ["."]),
    ("name 区分大小写", [".", "-name", "*.txt"]),
    ("name 大写不匹配", [".", "-name", "*.TXT"]),
    ("iname 忽略大小写", [".", "-iname", "*.TXT"]),
    ("name 匹配隐藏文件", [".", "-name", "*"]),
    ("path 整路径匹配", [".", "-path", "*/sub/*"]),
    ("ipath 忽略大小写", [".", "-ipath", "*/SUB/*"]),
    ("regex 整路径正则", [".", "-regex", r".*\.md$"]),
    ("iregex 忽略大小写", [".", "-iregex", r".*\.MD$"]),
    ("type d 目录", [".", "-type", "d"]),
    ("type f 普通文件", [".", "-type", "f"]),
    ("size 默认块 1", [".", "-size", "1"]),
    ("size 默认块 0", [".", "-size", "0"]),
    ("size 精确字节 6c", [".", "-size", "6c"]),
    ("size 大于 6c", [".", "-size", "+6c"]),
    ("size 小于 6c", [".", "-size", "-6c"]),
    ("size k 向上取整", [".", "-size", "+1k"]),
    ("empty 空文件与空目录", [".", "-empty"]),
    ("true 恒真", [".", "-true"]),
    ("false 恒假", [".", "-false"]),
    ("mtime 0 当天", [".", "-type", "f", "-mtime", "0"]),
    ("mtime 9", [".", "-type", "f", "-mtime", "9"]),
    ("mtime 10", [".", "-type", "f", "-mtime", "10"]),
    ("mtime +9", [".", "-type", "f", "-mtime", "+9"]),
    ("mtime +10", [".", "-type", "f", "-mtime", "+10"]),
    ("mtime -10", [".", "-type", "f", "-mtime", "-10"]),
    ("mmin 0", [".", "-type", "f", "-mmin", "0"]),
    ("mmin 1", [".", "-type", "f", "-mmin", "1"]),
    ("mmin -1", [".", "-type", "f", "-mmin", "-1"]),
    ("mmin +0", [".", "-type", "f", "-mmin", "+0"]),
    ("maxdepth 0", [".", "-maxdepth", "0"]),
    ("maxdepth 1", [".", "-maxdepth", "1"]),
    ("maxdepth 2", [".", "-maxdepth", "2"]),
    ("mindepth 1", [".", "-mindepth", "1"]),
    ("mindepth 2", [".", "-mindepth", "2"]),
    ("maxdepth 写在路径后", [".", "-maxdepth", "2", "-type", "f"]),
    ("and 显式", [".", "-name", "*.txt", "-a", "-size", "+0"]),
    ("or 显式", [".", "-name", "*.md", "-o", "-name", "*.py"]),
    ("not 显式", [".", "!", "-name", "*.txt"]),
    ("not 关键字", [".", "-not", "-name", "*.txt"]),
    ("括号分组", [".", "(", "-name", "*.md", "-o", "-name", "*.py", ")"]),
    ("括号加 print", [".", "(", "-name", "*.md", "-o", "-name", "*.py", ")", "-print"]),
    ("优先级 or 与 and", [".", "-type", "f", "-name", "*.txt", "-o", "-name", "*.md"]),
    ("prune 挡下降", [".", "-type", "d", "-name", "sub", "-prune", "-o", "-print"]),
    ("prune 单独用", [".", "-type", "d", "-prune"]),
    ("prune 空目录", [".", "-type", "d", "-name", "empty_dir", "-prune", "-o", "-print"]),
    ("depth 后序", [".", "-depth", "-type", "d"]),
    ("print0", [".", "-name", "*.md", "-print0"]),
    ("printf 基本", [".", "-name", "*.md", "-printf", "%f|%s|%y\n"]),
    ("printf 路径与目录", [".", "-name", "*.md", "-printf", "%p|%h\n"]),
    ("printf 字面量", [".", "-name", "*.md", "-printf", "%%|%f\n"]),
    ("printf 转义", [".", "-name", "*.md", "-printf", "%f\\t\\n"]),
    ("多个操作数", ["sub", "sub2", "-name", "*.txt"]),
    ("操作数是文件", ["notes.md"]),
    ("newer 参照更早的文件", [".", "-type", "f", "-newer", "old.txt"]),
    ("exec 单个", [".", "-name", "*.md", "-exec", "echo", "{}", ";"]),
    ("exec 批量", [".", "-name", "*.md", "-exec", "echo", "{}", "+"]),
    ("exec 无占位符", [".", "-name", "*.md", "-exec", "echo", ";"]),
    ("delete 删文件", [".", "-name", "drop.tmp", "-delete"]),
    ("delete 隐含 depth", [".", "-type", "d", "-name", "gone", "-delete"]),
]


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _run_gnu(args: list[str], cwd: Path) -> tuple[int, str, str]:
    cmd = "find " + " ".join(shlex.quote(a) for a in args)
    proc = subprocess.run(
        [BASH, "-c", cmd],
        cwd=str(cwd),
        capture_output=True,
    )
    return proc.returncode, _decode(proc.stdout), _decode(proc.stderr)


def _run_ours(args: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(MAIN), "find"] + args,
        cwd=str(cwd),
        capture_output=True,
    )
    return proc.returncode, _decode(proc.stdout), _decode(proc.stderr)


def _run_scenario(args: list[str]) -> dict:
    # 每个场景都拿全新副本，避免 -delete 之类污染后续场景
    tmp = Path(tempfile.mkdtemp(prefix="find_diff_"))
    work = tmp / "demo"
    shutil.copytree(DEMO, work)
    try:
        g_code, g_out, g_err = _run_gnu(args, work)
        # GNU 跑完可能已经删了文件，第二个场景要重新铺一份
        shutil.rmtree(work)
        shutil.copytree(DEMO, work)
        o_code, o_out, o_err = _run_ours(args, work)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    g_lines = g_out.splitlines()
    o_lines = o_out.splitlines()
    return {
        "args": args,
        "gnu_code": g_code,
        "ours_code": o_code,
        "same_output": g_lines == o_lines,
        "same_sorted": sorted(g_lines) == sorted(o_lines),
        "gnu_stdout": g_out,
        "ours_stdout": o_out,
        "gnu_stderr": g_err,
        "ours_stderr": o_err,
    }


def main() -> None:
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]

    results = []
    for name, args in SCENARIOS:
        if only and only != name:
            continue
        item = _run_scenario(args)
        item["name"] = name
        results.append(item)
        flag = "同" if item["same_output"] else ("序不同" if item["same_sorted"] else "差")
        print(f"[{flag}] {name:24} GNU(rc={item['gnu_code']}) 本项目(rc={item['ours_code']})")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    diffs = [r for r in results if not r["same_output"]]
    same_sorted_only = [r for r in diffs if r["same_sorted"]]
    really_diff = [r for r in diffs if not r["same_sorted"]]
    print()
    print(f"总场景 {len(results)}，逐字节一致 {len(results) - len(diffs)}，"
          f"仅顺序不同 {len(same_sorted_only)}，内容不同 {len(really_diff)}")
    print(f"报告：{REPORT}")


if __name__ == "__main__":
    main()
