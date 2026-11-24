"""差分对照：mv 的 -i / -n 先后顺序（含重复给）是否与 GNU 一致。

mv 复用 w2l/flags.py 的 resolve_exclusive，判据是「最后一次出现者赢」。
旧差分脚本 _t510_diff_mv.py 只覆盖了 -n -i 与 -i -n 两种，
这里补上重复给（-n -i -n / -i -n -i）与合并短选项（-ni / -in）。
"""

from __future__ import annotations

import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "mv_diff"

sys.path.insert(0, str(ROOT))


def _load_t510():
    spec = importlib.util.spec_from_file_location("_t510_diff_mv", HERE / "_t510_diff_mv.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


T510 = _load_t510()

from w2l.commands.mv import build_parser, mv  # noqa: E402
from w2l.context import RunContext  # noqa: E402

GNU_MV = shutil.which("mv")
if GNU_MV is None:
    raise SystemExit("本机找不到 GNU mv")

CASES: list[tuple[str, list[str], str | None]] = [
    ("n-then-i", ["-n", "-i", "a.txt", "b.txt"], "y\n"),
    ("i-then-n", ["-i", "-n", "a.txt", "b.txt"], "y\n"),
    ("n-i-n", ["-n", "-i", "-n", "a.txt", "b.txt"], "y\n"),
    ("i-n-i", ["-i", "-n", "-i", "a.txt", "b.txt"], "y\n"),
    ("combined-ni", ["-ni", "a.txt", "b.txt"], "y\n"),
    ("combined-in", ["-in", "a.txt", "b.txt"], "y\n"),
    ("n-only", ["-n", "a.txt", "b.txt"], None),
    ("i-only-yes", ["-i", "a.txt", "b.txt"], "y\n"),
    ("i-only-no", ["-i", "a.txt", "b.txt"], "n\n"),
]


def run_gnu(argv: list[str], cwd: Path, stdin_text: str | None) -> dict:
    proc = subprocess.run(
        [GNU_MV, *argv],
        cwd=str(cwd),
        input=stdin_text.encode() if stdin_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "rc": proc.returncode,
        "out": proc.stdout.decode("utf-8", "replace"),
        "err": proc.stderr.decode("utf-8", "replace"),
    }


def run_mine(argv: list[str], cwd: Path, stdin_text: str | None) -> dict:
    out, err = io.StringIO(), io.StringIO()
    try:
        namespace = build_parser().parse_args(list(argv))
    except SystemExit as exc:
        return {"rc": int(exc.code or 0), "out": "", "err": f"argparse 退出 {exc.code}\n"}
    ctx = RunContext(
        cwd=cwd,
        stdout=out,
        stderr=err,
        stdin=io.StringIO(stdin_text) if stdin_text is not None else io.StringIO(""),
    )
    code = mv(namespace, ctx)
    return {"rc": code, "out": out.getvalue(), "err": err.getvalue()}


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    sandbox_root = Path(tempfile.mkdtemp(prefix="mvorder_", dir=str(DATA)))

    report: list[dict] = []
    mismatches = 0

    for index, (name, argv, stdin_text) in enumerate(CASES):
        base = sandbox_root / f"case{index:03d}"
        base.mkdir(parents=True)
        gnu_dir = base / "gnu"
        mine_dir = base / "mine"
        for target in (gnu_dir, mine_dir):
            target.mkdir()
            T510.build_fixture(target)

        gnu = run_gnu(argv, gnu_dir, stdin_text)
        mine = run_mine(argv, mine_dir, stdin_text)

        problems: list[str] = []
        if (gnu["rc"] == 0) != (mine["rc"] == 0):
            problems.append(f"成功与否不同: GNU rc={gnu['rc']} 本实现 rc={mine['rc']}")
        if bool(gnu["err"].strip()) != bool(mine["err"].strip()):
            problems.append(
                f"有无报错不同: GNU err={gnu['err'].strip()!r} 本实现 err={mine['err'].strip()!r}"
            )
        gnu_tree = T510.tree_state(gnu_dir)
        mine_tree = T510.tree_state(mine_dir)
        if gnu_tree != mine_tree:
            problems.append(
                f"目录树不同 GNU侧={ {k: v for k, v in gnu_tree.items() if mine_tree.get(k) != v} } "
                f"本实现侧={ {k: v for k, v in mine_tree.items() if gnu_tree.get(k) != v} }"
            )

        if problems:
            mismatches += 1
        report.append(
            {
                "name": name,
                "argv": argv,
                "gnu": {"rc": gnu["rc"], "out": gnu["out"], "err": gnu["err"]},
                "mine": {"rc": mine["rc"], "out": mine["out"], "err": mine["err"]},
                "problems": problems,
            }
        )
        flag = "OK " if not problems else "DIFF"
        print(f"[{flag}] {name}  argv={' '.join(argv)}")
        for problem in problems:
            print("       -", problem)

    out_path = DATA / "diff_mv_flag_order.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 66)
    print(f"总用例 {len(CASES)}，不一致 {mismatches}")
    print("详细结果:", out_path)
    shutil.rmtree(sandbox_root, ignore_errors=True)
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
