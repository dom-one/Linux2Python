"""并行搜索：串行耗时是「冷」的还是「暖」的。

基线探针里本项目 grep -r 用了 24.4 秒，但逐项拆开只加起来 0.05 秒。
两者对不上，说明时间不在被拆开的那几项里。两个候选解释：
① Windows Defender 对新建文件的实时扫描（第一次打开每个文件都要扫一遍）；
② 逐项拆开的探针复用了基线探针已经读过的文件，已经是热的。

这一轮把同一棵树连跑三次（冷→温），再造一棵新树跑一次（冷），
用「同一棵树第二次明显变快、新树第一次又变慢」来钉死是哪一个。
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "grep_parallel"
REPORT = DATA / "coldwarm.txt"

sys.path.insert(0, str(ROOT))

from w2l.commands.grep import build_parser, grep  # noqa: E402
from w2l.context import RunContext  # noqa: E402


def build_tree(root: Path, dirs: int = 30, per_dir: int = 30) -> int:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    count = 0
    for d in range(dirs):
        sub = root / f"pkg{d:03d}"
        sub.mkdir()
        for f in range(per_dir):
            (sub / f"mod{f:03d}.txt").write_text(
                "line one\nERROR boom\nplain text\nanother ERROR line\n",
                encoding="utf-8",
                newline="\n",
            )
            count += 1
    return count


def run_serial(tree: Path) -> tuple[float, int]:
    namespace = build_parser().parse_args(["-r", "ERROR", str(tree)])
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(cwd=ROOT, stdout=out, stderr=err, stdin=io.StringIO(""))
    start = time.perf_counter()
    code = grep(namespace, ctx)
    return time.perf_counter() - start, out.getvalue().count("\n")


def run_gnu(tree: Path) -> float:
    exe = shutil.which("grep")
    start = time.perf_counter()
    subprocess.run(
        [exe, "-r", "ERROR", str(tree)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return time.perf_counter() - start


def main() -> int:
    lines: list[str] = []

    def say(text: str) -> None:
        lines.append(text)
        print(text)

    tree = DATA / "tree"
    if not tree.exists():
        build_tree(tree)

    say("== 同一棵树连跑三次（第一次可能是冷的）==")
    for i in range(1, 4):
        elapsed, count = run_serial(tree)
        say(f"  第{i}次 本项目: {elapsed:.3f}s lines={count}")

    say("== 新建一棵树后第一次跑（新的冷文件）==")
    fresh = DATA / "tree_fresh"
    count = build_tree(fresh)
    say(f"  新树文件数={count}")
    elapsed, hits = run_serial(fresh)
    say(f"  第一次 本项目: {elapsed:.3f}s lines={hits}")
    elapsed, hits = run_serial(fresh)
    say(f"  第二次 本项目: {elapsed:.3f}s lines={hits}")

    say("== GNU grep 在同一棵新树上的耗时（它也会被扫描，只是它不做正则编译缓存以外的事）==")
    say(f"  GNU: {run_gnu(fresh):.3f}s")

    DATA.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"\nreport -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
