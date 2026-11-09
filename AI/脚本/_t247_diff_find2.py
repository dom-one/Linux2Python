"""find 指令的差分对照（第二轮）：错误路径 + 随机表达式 fuzz。

第一轮（_t245）比的是正常路径，这一轮补三块：
1. 错误路径：两边都必须失败（退出码口径不同：GNU 用 1，本项目用 2，所以只比「是否失败」）
2. 多操作数、相对路径、-print0 等组合
3. 随机表达式 fuzz：把谓词和运算符随机组合，逐条与 GNU find 比对输出

结果写到 _data_find_diff2/diff2.txt。
"""

from __future__ import annotations

import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
OUT_DIR = HERE / "_data_find_diff2"
GNU_FIND = shutil.which("find") or r"E:\software\Git\Git\usr\bin\find.exe"

PREDICATES = [
    ["-name", "*.txt"],
    ["-name", "*.md"],
    ["-iname", "*.TXT"],
    ["-name", "c*"],
    ["-path", "*/sub/*"],
    ["-path", "*nested*"],
    ["-ipath", "*SUB*"],
    ["-regex", ".*\\.txt"],
    ["-iregex", ".*\\.TXT"],
    ["-type", "f"],
    ["-type", "d"],
    ["-size", "0"],
    ["-size", "1"],
    ["-size", "+0"],
    ["-size", "1c"],
    ["-size", "+5c"],
    ["-size", "3k"],
    ["-empty"],
    ["-true"],
    ["-false"],
    ["-mtime", "0"],
    ["-mtime", "+0"],
    ["-mmin", "0"],
    ["-mmin", "1"],
    ["-mmin", "+1"],
    ["-mmin", "-1"],
    ["-newer", "TREE/a.txt"],
]

ERROR_CASES = [
    ("未知谓词", ["-badpred"]),
    ("-name 缺参数", ["-name"]),
    ("-type 参数非法", ["-type", "x"]),
    ("-size 参数非法", ["-size", "abc"]),
    ("-size 缺参数", ["-size"]),
    ("-maxdepth 参数非法", ["-maxdepth", "x"]),
    ("-maxdepth 缺参数", ["-maxdepth"]),
    ("左括号未闭合", ["(", "-name", "*.txt"]),
    ("多余右括号", [")"]),
    ("路径写在表达式之后", ["-name", "*.txt", "extra"]),
    ("-exec 缺结尾", ["-exec", "echo", "{}"]),
    ("-regex 非法", ["-regex", "["]),
    ("-newer 指向不存在的文件", ["-newer", "TREE/没有这个文件"]),
]

NORMAL_CASES = [
    ("多操作数", ["TREE", "TREE/sub", "-name", "*.txt"]),
    ("相对路径 .", [".", "-name", "*.txt"]),
    ("显式 -print", ["-name", "*.txt", "-print"]),
    ("-print0 混排", ["-name", "*.txt", "-print0"]),
    ("嵌套括号", ["(", "-name", "*.txt", "-o", "(", "-name", "*.md", "-o", "-type", "d", ")", ")"]),
    ("多重否定", ["!", "!", "-name", "*.txt"]),
    ("-a 连写", ["-name", "*.txt", "-a", "-type", "f", "-a", "-size", "+0"]),
    ("-o 连写", ["-name", "*.md", "-o", "-name", "*.py"]),
    ("-printf %%p %%f", ["-printf", "%p|%f|%h|%s|%y|%%\\n"]),
    # 单独的 %T 在 GNU findutils 4.10 的 MSYS 构建里会直接报 "memory exhausted"，
    # 真正的纪元秒数是 %T@
    ("-printf %T@", ["-name", "*.txt", "-printf", "%T@\\n"]),
    ("-size w 单位", ["-size", "3w"]),
    ("-empty 目录", ["-type", "d", "-empty"]),
    ("-maxdepth 0 加表达式", ["-maxdepth", "0", "-type", "d"]),
    ("-mindepth 3", ["-mindepth", "3"]),
    ("-depth 加 -type d", ["-depth", "-type", "d"]),
    ("-prune 指定目录", ["-type", "d", "-name", "sub", "-prune", "-o", "-print"]),
]


def build_tree(root: Path) -> None:
    now = time.time()
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.txt").write_bytes(b"hello\n")
    (root / "B.txt").write_bytes(b"upper\n")
    (root / "c.md").write_bytes(b"# c\n")
    (root / "empty.log").write_bytes(b"")
    (root / ".hidden").write_bytes(b"x\n")
    (root / ".x.txt").write_bytes(b"hidden txt\n")
    sub = root / "sub"
    sub.mkdir(exist_ok=True)
    (sub / "c.txt").write_bytes(b"ccc\n")
    (sub / "d.py").write_bytes(b"print(1)\n")
    nested = sub / "nested"
    nested.mkdir(exist_ok=True)
    (nested / "e.md").write_bytes(b"# t\n")
    (nested / "big.bin").write_bytes(b"z" * 3000)
    (root / "hollow").mkdir(exist_ok=True)
    for name, age in (("old.txt", 90000), ("mid.txt", 3600), ("recent.txt", 90)):
        path = root / name
        path.write_bytes(b"x\n")
        stamp = now - age
        os.utime(path, (stamp, stamp))


def run_gnu(cwd: Path, argv: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        [GNU_FIND, *argv], cwd=str(cwd), capture_output=True,
    )
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n"),
        proc.stderr.decode("utf-8", "replace"),
    )


def run_mine(cwd: Path, argv: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "find", *argv],
        cwd=str(cwd), capture_output=True,
    )
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n"),
        proc.stderr.decode("utf-8", "replace"),
    )


def expand(parts: list[str], tree: str) -> list[str]:
    return [part.replace("TREE", tree) for part in parts]


def random_expression(rng: random.Random) -> list[str]:
    """随机拼一条表达式：1~3 个谓词，用 -a / -o / ! 组合。"""
    parts: list[str] = []
    count = rng.randint(1, 3)
    for index in range(count):
        if index:
            parts.append(rng.choice(["-a", "-o", "!"]))
        parts.extend(rng.choice(PREDICATES))
    if rng.random() < 0.3:
        parts.append(rng.choice(["-print", "-print0"]))
    return parts


def main() -> None:
    fuzz_count = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    tree = OUT_DIR / "tree"
    build_tree(tree)
    empty_cwd = OUT_DIR / "run"
    empty_cwd.mkdir()
    tree_abs = tree.as_posix()

    lines: list[str] = []
    passed = failed = 0
    failures: list[str] = []

    def compare(title: str, extra: list[str], tree_root: str) -> None:
        nonlocal passed, failed
        argv = [tree_root, *expand(extra, tree_abs)]
        gnu_code, gnu_out, _ = run_gnu(empty_cwd, argv)
        my_code, my_out, my_err = run_mine(empty_cwd, argv)
        same_out = gnu_out == my_out
        same_code = gnu_code == my_code or (gnu_code == 0 and my_code == 1)
        if same_out and same_code:
            passed += 1
            return
        failed += 1
        failures.append(title)
        lines.append("=" * 70)
        lines.append(f"[不一致] {title}")
        lines.append(f"$ find {' '.join(extra)}")
        lines.append(f"GNU  exit={gnu_code} 行数={len(gnu_out.splitlines())}")
        lines.append(f"本实现 exit={my_code} 行数={len(my_out.splitlines())}")
        gnu_lines = gnu_out.splitlines()
        my_lines = my_out.splitlines()
        only_gnu = [line for line in gnu_lines if line not in my_lines]
        only_mine = [line for line in my_lines if line not in gnu_lines]
        lines.append(f"只有 GNU 有: {only_gnu[:8]}")
        lines.append(f"只有本实现有: {only_mine[:8]}")
        if my_err:
            lines.append(f"本实现 stderr: {my_err.strip()[:200]}")

    for title, extra in NORMAL_CASES:
        compare(title, extra, tree_abs)

    # 相对路径：把 cwd 设成树所在目录，操作数用 "tree"
    tree_cwd = OUT_DIR
    for title, extra in (("相对操作数 tree", ["tree", "-name", "*.txt"]),
                         ("相对操作数 tree/ 带斜杠", ["tree/", "-name", "*.txt"]),
                         ("相对操作数 .", [".", "-name", "*.txt"])):
        argv = expand(extra, tree_abs)
        gnu_code, gnu_out, _ = run_gnu(tree_cwd, argv)
        my_code, my_out, _ = run_mine(tree_cwd, argv)
        if gnu_out == my_out and (gnu_code == my_code or (gnu_code == 0 and my_code == 1)):
            passed += 1
        else:
            failed += 1
            failures.append(title)
            lines.append("=" * 70)
            lines.append(f"[不一致] {title}")
            lines.append(f"GNU: {gnu_out.splitlines()[:6]}")
            lines.append(f"本实现: {my_out.splitlines()[:6]}")

    # 错误路径：只比「是否失败」
    for title, extra in ERROR_CASES:
        argv = [tree_abs, *expand(extra, tree_abs)]
        gnu_code, gnu_out, gnu_err = run_gnu(empty_cwd, argv)
        my_code, my_out, my_err = run_mine(empty_cwd, argv)
        gnu_failed = gnu_code != 0
        my_failed = my_code != 0
        if gnu_failed and my_failed:
            passed += 1
            lines.append(f"[一致-错误路径] {title}（GNU exit={gnu_code}，本实现 exit={my_code}）")
        else:
            failed += 1
            failures.append(f"错误路径: {title}")
            lines.append("=" * 70)
            lines.append(f"[不一致-错误路径] {title}")
            lines.append(f"GNU exit={gnu_code} stderr={gnu_err.strip()[:160]}")
            lines.append(f"本实现 exit={my_code} stderr={my_err.strip()[:160]}")

    # fuzz
    rng = random.Random(20261110)
    for index in range(fuzz_count):
        expression = random_expression(rng)
        compare(f"fuzz#{index} {' '.join(expression)}", expression, tree_abs)

    header = f"一致 {passed} 条，不一致 {failed} 条（其中 fuzz {fuzz_count} 条）"
    (OUT_DIR / "diff2.txt").write_text("\n".join([header, ""] + lines), encoding="utf-8")
    print(header)
    if failures:
        print("不一致: " + "; ".join(failures[:20]))
    print(f"明细写入 {OUT_DIR / 'diff2.txt'}")


if __name__ == "__main__":
    main()
