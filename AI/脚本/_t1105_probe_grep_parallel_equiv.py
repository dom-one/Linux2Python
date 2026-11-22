"""并行搜索：串行与并行的输出必须逐字节一致。

三件事要钉死：
① 并行输出 == 串行输出（逐字节），这是并行方案唯一不可让步的前提；
② 真的起了子进程（不是把串行循环假装成并行）——用返回 os.getpid() 的
   任务函数验证进程号与父进程不同；
③ 真的走了并行分支（不是被 _PARALLEL_MIN_FILES 挡回串行）——把
   grep.map_ordered 换成记录调用的包装函数，看它有没有被调用。

语料要杂：普通文本、GBK 文本、空文件、二进制文件、嵌套目录都要有，
因为不同分支（_search_binary / -l / -c / -o）走的代码路径不一样。
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "grep_parallel"
REPORT = DATA / "equiv.txt"

sys.path.insert(0, str(ROOT))

from w2l.commands import grep as grep_mod  # noqa: E402
from w2l.commands.grep import build_parser, grep  # noqa: E402
from w2l.context import RunContext  # noqa: E402
from w2l.parallel import map_ordered  # noqa: E402


def build_tree(root: Path) -> int:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    count = 0
    for d in range(8):
        sub = root / f"dir{d}"
        sub.mkdir()
        for f in range(6):
            (sub / f"f{f}.txt").write_text(
                f"head {d} {f}\nERROR here\ntail {f}\n", encoding="utf-8", newline="\n"
            )
            count += 1
        nested = sub / "deep"
        nested.mkdir()
        (nested / "n.txt").write_text("ERROR nested\nok\n", encoding="utf-8", newline="\n")
        (nested / "gbk.txt").write_bytes("ERROR 中文\n".encode("gbk"))
        (nested / "empty.txt").write_bytes(b"")
        (nested / "bin.dat").write_bytes(b"\x00\x01ERROR\x00\n")
        count += 4
    return count


def run(argv: list[str]) -> tuple[int, str, str]:
    namespace = build_parser().parse_args(argv)
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(cwd=ROOT, stdout=out, stderr=err, stdin=io.StringIO(""))
    code = grep(namespace, ctx)
    return code, out.getvalue(), err.getvalue()


def _pid_probe(_item):
    return os.getpid()


def main() -> int:
    lines: list[str] = []

    def say(text: str) -> None:
        lines.append(text)
        print(text)

    tree = DATA / "equiv_tree"
    count = build_tree(tree)
    say(f"语料文件数={count}（阈值 _PARALLEL_MIN_FILES={grep_mod._PARALLEL_MIN_FILES}）")

    # ② 负控制：确认 map_ordered 真的会起子进程
    pids = map_ordered(_pid_probe, list(range(8)), 4)
    say(f"① 子进程检查: 父进程 pid={os.getpid()} 子进程 pid 集合={sorted(set(pids))}")
    say(f"   是否真的起了别的进程={'是' if set(pids) != {os.getpid()} else '否'}")

    # ③ 记录 map_ordered 有没有被调用
    calls: list[tuple[int, int]] = []
    original = grep_mod.map_ordered

    def spy(func, items, jobs):
        payload = list(items)
        calls.append((len(payload), jobs))
        return original(func, payload, jobs)

    grep_mod.map_ordered = spy
    try:
        serial_code, serial_out, serial_err = run(["-r", "ERROR", str(tree)])
        parallel_code, parallel_out, parallel_err = run(["-j", "4", "-r", "ERROR", str(tree)])
    finally:
        grep_mod.map_ordered = original

    say(f"② 并行分支检查: map_ordered 调用记录={calls}")
    say(f"③ 输出逐字节一致: {'是' if serial_out == parallel_out else '否'}")
    say(f"   串行 exit={serial_code} 字节={len(serial_out)}")
    say(f"   并行 exit={parallel_code} 字节={len(parallel_out)}")
    if serial_out != parallel_out:
        for i, (a, b) in enumerate(zip(serial_out.splitlines(), parallel_out.splitlines())):
            if a != b:
                say(f"   首个差异行 {i}: 串行={a!r} 并行={b!r}")
                break
    say(f"   stderr 一致: {'是' if serial_err == parallel_err else '否'} 串行={serial_err!r}")

    # 各选项分支都要一致
    for extra in (["-n"], ["-c"], ["-l"], ["-o"], ["-i"], ["-v"], ["-E"], ["-w"]):
        s_code, s_out, _ = run(extra + ["-r", "ERROR", str(tree)])
        p_code, p_out, _ = run(extra + ["-j", "4", "-r", "ERROR", str(tree)])
        say(f"   选项 {''.join(extra):4s} 一致={'是' if (s_out == p_out and s_code == p_code) else '否'}")

    # 与 GNU grep 对照命中数
    exe = shutil.which("grep")
    if exe:
        proc = subprocess.run(
            [exe, "-r", "ERROR", str(tree)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        gnu_lines = proc.stdout.count("\n")
        say(f"④ GNU grep 命中行数={gnu_lines} 本项目串行命中行数={serial_out.count(chr(10))}")

    DATA.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"\nreport -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
