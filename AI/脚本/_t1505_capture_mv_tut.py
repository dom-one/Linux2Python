"""把 teach/30 教程里每个步骤的**真跑输出**录下来，供誊进文档。

用法:
    python AI/脚本/_t1505_capture_mv_tut.py

做法:
1. 每个案例先用 _t1504_prep_mv_case.py 重建现场（mv 是破坏性操作）
2. 真跑一次主实现（python main.py mv ...），录下退出码、stdout、stderr
3. 需要对照的，再跑一次 GNU /usr/bin/mv，记下两边差异
4. 输出写进 AI/数据/mv_tutorial_capture.txt

为什么必须用脚本录而不是手抄:
- mv 的输出里混着中文报错与 GNU 原文，手抄必错
- 目录树与文件字节数必须现算
- 手抄进 markdown 之后，核对器比对的是「抄错的版本」，报错时看不出是哪边错
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEMO = ROOT / "AI" / "数据" / "mv_demo"
CASE_ROOT = DEMO / "case"
OUT = ROOT / "AI" / "数据" / "mv_tutorial_capture.txt"

PY = sys.executable
GNU_MV = shutil.which("mv")

# 案例名, 说明, 命令（相对 case 目录）, 是否对照 GNU, 额外准备
CASES: list[tuple[str, str, list[str], bool, str | None]] = [
    ("s2", "文件改新名字", ["a.txt", "a.renamed.txt"], False, None),
    ("s3", "目标是不存在的目录名，整个目录改名", ["dir1", "dir1.renamed"], False, None),
    ("s4", "目标是已存在的目录，落点是目录/源名", ["a.txt", "destdir"], False, None),
    ("s5", "移动目录到已存在的目录", ["dir1", "destdir"], False, None),
    ("s6", "源目录尾部带斜杠，落点不变", ["dir1/", "destdir"], False, None),
    ("s7", "同名目录非空，报目录非空", ["dir1", "destdir"], False, "destdir-dir1-nonempty"),
    ("s8", "同名目录是空的，移动照常", ["dir1", "destdir"], False, "destdir-dir1-empty"),
    ("s9", "多个源，目标必须是已存在的目录", ["a.txt", "b.txt", "destdir"], False, None),
    ("s10", "-v 打印 renamed 行", ["-v", "a.txt", "a.renamed.txt"], False, None),
    ("s11", "-v 搬目录只打印一行", ["-v", "dir1", "destdir"], False, None),
    ("s12", "-n 不覆盖已存在的目标", ["-n", "a.txt", "b.txt"], False, None),
    ("s13", "-u 源不够新就跳过", ["-u", "old.txt", "future.txt"], False, None),
    ("s14", "-u 源更新才搬", ["-u", "future.txt", "old.txt"], False, None),
    ("s15", "-b 覆盖前把旧目标改名备份", ["-b", "a.txt", "b.txt"], False, None),
    ("s16", "-S 单独给就隐含开备份", ["-S", ".bak", "a.txt", "b.txt"], False, None),
    ("s17", "-i 覆盖前问一句，应答 y", ["-i", "a.txt", "b.txt"], True, None),
    ("s18", "-i 应答 yeah（GNU 认，本实现不认）", ["-i", "a.txt", "b.txt"], True, None),
    ("s19", "-i 应答 ' y'（GNU 不认，本实现认）", ["-i", "a.txt", "b.txt"], True, None),
    ("s20", "-t 把目标目录写死", ["-t", "destdir", "a.txt"], False, None),
    ("s21", "-T 把目标当普通文件", ["-T", "a.txt", "destdir"], False, None),
    ("s22", "把文件移动到它自己", ["a.txt", "a.txt"], False, None),
    ("s23", "把目录移进它自己的子目录", ["dir1", "dir1/sub"], False, None),
    ("s24", "目标的父目录不存在", ["a.txt", "nodir/out.txt"], False, None),
    ("s25", "二进制文件逐字节保真", ["payload.bin", "payload.copy"], False, None),
    ("s26", "GBK 文件不被改写", ["legacy.txt", "legacy.copy"], False, None),
    ("s27", "缺操作数", [], False, None),
    ("s28", "源不存在", ["nosuch.txt", "out.txt"], False, None),
    ("s29", "用普通文件覆盖目录", ["a.txt", "dir1"], False, None),
    ("s30", "-b 且备份名已存在是个目录", ["-b", "a.txt", "b.txt"], True, "backup-dir"),
    ("s31", "-n -f 一起给（GNU：后给的赢）", ["-n", "-f", "a.txt", "b.txt"], True, None),
    ("s32", "-b -n 一起给（GNU 报互斥）", ["-b", "-n", "a.txt", "b.txt"], True, None),
    ("s33", "--backup=numbered（GNU 独有能力）", ["--backup=numbered", "a.txt", "b.txt"], True, None),
    ("s34", "只读目标照样能搬", ["a.txt", "b.txt"], False, "readonly-b"),
]

# 需要喂标准输入的案例
STDIN_CASES = {
    "s17": "y\n",
    "s18": "yeah\n",
    "s19": " y\n",
}


def prep(case: str, extra: str | None) -> Path:
    argv = [PY, str(HERE / "_t1504_prep_mv_case.py"), case]
    if extra:
        argv[-1] = f"{case}-{extra}"
    subprocess.run(argv, cwd=str(ROOT), stdout=subprocess.DEVNULL, check=True)
    return CASE_ROOT / argv[-1]


def tree(root: Path) -> str:
    lines = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            lines.append(f"    {rel}/")
        else:
            lines.append(f"    {rel}  ({path.stat().st_size} 字节)")
    if not lines:
        lines.append("    (空)")
    return "\n".join(lines)


def run_mine(cwd: Path, argv: list[str], stdin_text: str | None) -> dict:
    # cwd 是案例目录，但 main.py 在仓库根，所以用绝对路径调 main.py；
    # 相对路径参数按 cwd 解析（w2l/cli.py 第 84 行用 Path.cwd()）。
    proc = subprocess.run(
        [PY, str(ROOT / "main.py"), "mv", *argv],
        cwd=str(cwd),
        input=stdin_text.encode() if stdin_text else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "rc": proc.returncode,
        "out": proc.stdout.decode("utf-8", "replace"),
        "err": proc.stderr.decode("utf-8", "replace"),
    }


def run_gnu(cwd: Path, argv: list[str], stdin_text: str | None) -> dict:
    if GNU_MV is None:
        return {"rc": -1, "out": "", "err": "(本机找不到 GNU mv)"}
    proc = subprocess.run(
        [GNU_MV, *argv],
        cwd=str(cwd),
        input=stdin_text.encode() if stdin_text else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "rc": proc.returncode,
        "out": proc.stdout.decode("utf-8", "replace"),
        "err": proc.stderr.decode("utf-8", "replace"),
    }


def main() -> int:
    chunks: list[str] = []
    for case, title, argv, with_gnu, extra in CASES:
        stdin_text = STDIN_CASES.get(case)
        work = prep(case, extra)
        mine = run_mine(work, argv, stdin_text)
        mine_tree = tree(work)

        gnu_text = ""
        if with_gnu:
            work2 = prep(case, extra)
            gnu = run_gnu(work2, argv, stdin_text)
            gnu_tree = tree(work2)
            gnu_text = (
                f"\n  [GNU /usr/bin/mv] 退出码 {gnu['rc']}\n"
                f"    stdout: {gnu['out']!r}\n"
                f"    stderr: {gnu['err'].strip()!r}\n"
                f"    落地:\n{gnu_tree}\n"
            )

        chunks.append(
            "=" * 72
            + f"\n### {case} · {title}\n"
            + f"命令: python main.py mv {' '.join(argv)}\n"
            + (f"标准输入: {stdin_text!r}\n" if stdin_text else "")
            + f"  [本实现] 退出码 {mine['rc']}\n"
            + f"    stdout: {mine['out']!r}\n"
            + f"    stderr: {mine['err'].strip()!r}\n"
            + f"    落地:\n{mine_tree}\n"
            + gnu_text
        )

    OUT.write_text("\n".join(chunks), encoding="utf-8")
    print(f"已录制 {len(CASES)} 个案例 -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
