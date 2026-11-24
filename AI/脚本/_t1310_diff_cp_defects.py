"""差分对照（第二轮）：只针对本轮修的 4 处 GNU 偏差逐组比对。

比法与 _t410_diff_cp.py 一致：两个一模一样的沙箱各跑一次，
比「成功与否 / 有无报错 / 落地目录树 / verbose 对序 / mtime 归类」。

本轮新增的四组语义：
1. -i 与 -n 的先后：后给的那个赢，且取**最后一次**出现。
2. --preserve：裸写 = --preserve=all 且不吃后面的操作数；重复给是并集。
3. 目标带尾斜杠：必须是目录，报错次序也与 GNU 一致。
4. -T 与 --parents 冲突；--backup(= -S) 与 --no-clobber 冲突。
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "cp_defect_probe"

sys.path.insert(0, str(ROOT))


def _load_t410():
    """复用 _t410_diff_cp.py 里的沙箱/比对助手，避免两份实现漂移。"""
    spec = importlib.util.spec_from_file_location("_t410_diff_cp", HERE / "_t410_diff_cp.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


T410 = _load_t410()
build_fixture = T410.build_fixture
tree_state = T410.tree_state
mtime_state = T410.mtime_state
run_gnu = T410.run_gnu

from w2l.commands.cp import build_parser, cp  # noqa: E402
from w2l.context import RunContext  # noqa: E402


def run_mine(argv: list[str], cwd: Path, stdin_text: str | None) -> dict:
    """跑一次本实现的 cp；argparse 自己报错时也要落成一次失败而不是崩掉。"""
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
    code = cp(namespace, ctx)
    return {"rc": code, "out": out.getvalue(), "err": err.getvalue()}


CASES: list[tuple[str, list[str], str | None, bool]] = [
    # ---------- 1. -i / -n 的先后 ----------
    ("n-then-i", ["-n", "-i", "a.txt", "b.txt"], "y\n", False),
    ("i-then-n", ["-i", "-n", "a.txt", "b.txt"], "y\n", False),
    ("n-i-n", ["-n", "-i", "-n", "a.txt", "b.txt"], "y\n", False),
    ("i-n-i", ["-i", "-n", "-i", "a.txt", "b.txt"], "y\n", False),
    ("combined-ni", ["-ni", "a.txt", "b.txt"], "y\n", False),
    ("combined-in", ["-in", "a.txt", "b.txt"], "y\n", False),
    ("n-only", ["-n", "a.txt", "b.txt"], None, False),
    ("i-only-yes", ["-i", "a.txt", "b.txt"], "y\n", False),
    ("i-only-no", ["-i", "a.txt", "b.txt"], "n\n", False),
    ("n-dir", ["-n", "-r", "dir1", "destdir"], None, False),
    # ---------- 2. --preserve 的形态 ----------
    ("preserve-bare", ["--preserve", "a.txt", "b.txt"], None, True),
    ("preserve-mode", ["--preserve=mode", "a.txt", "copy.txt"], None, True),
    ("preserve-timestamps", ["--preserve=timestamps", "a.txt", "copy.txt"], None, True),
    ("preserve-union", ["--preserve=mode", "--preserve=timestamps", "a.txt", "copy.txt"], None, True),
    ("preserve-all", ["--preserve=all", "a.txt", "copy.txt"], None, True),
    ("preserve-then-nopreserve", ["--preserve=all", "--no-preserve=mode", "a.txt", "copy.txt"], None, True),
    ("preserve-bogus", ["--preserve=bogus", "a.txt", "b.txt"], None, False),
    ("no-preserve-bogus", ["--no-preserve=bogus", "a.txt", "b.txt"], None, False),
    ("preserve-bare-not-eat", ["--preserve", "a.txt", "copy.txt"], None, True),
    # ---------- 3. 目标带尾斜杠 ----------
    ("file-slash-missing", ["a.txt", "nosuch/"], None, False),
    ("file-slash-existing-dir", ["a.txt", "destdir/"], None, False),
    ("file-slash-existing-file", ["a.txt", "plain.txt/"], None, False),
    ("dir-slash-missing-r", ["-r", "dir1", "nosuch/"], None, False),
    ("dir-slash-existing-dir-r", ["-r", "dir1", "destdir/"], None, False),
    ("dir-slash-existing-file-r", ["-r", "dir1", "plain.txt/"], None, False),
    ("multi-slash-missing", ["a.txt", "plain.txt", "nosuch/"], None, False),
    ("multi-slash-existing-file", ["a.txt", "plain.txt", "plain.txt/"], None, False),
    ("multi-slash-existing-dir", ["a.txt", "plain.txt", "destdir/"], None, False),
    # ---------- 4. -T / --parents 与 --backup / --no-clobber ----------
    ("T-parents-normal", ["-T", "--parents", "a.txt", "destdir"], None, False),
    ("T-parents-no-operand", ["-T", "--parents"], None, False),
    ("T-parents-one-operand", ["-T", "--parents", "a.txt"], None, False),
    ("parents-missing-target", ["--parents", "a.txt", "newdir"], None, False),
    ("parents-existing-dir", ["--parents", "a.txt", "destdir"], None, False),
    ("T-slash-missing", ["-T", "a.txt", "nosuch/"], None, False),
    ("T-slash-existing-dir", ["-T", "a.txt", "destdir/"], None, False),
    ("backup-and-noclobber", ["-S", ".bak", "-n", "a.txt", "b.txt"], None, False),
    ("backup-and-noclobber-no-operand", ["-S", ".bak", "-n"], None, False),
    ("backup-only", ["-S", ".bak", "a.txt", "b.txt"], None, False),
]


def main() -> int:
    import shutil
    import tempfile

    DATA.mkdir(parents=True, exist_ok=True)
    sandbox_root = Path(tempfile.mkdtemp(prefix="cpdefect_", dir=str(DATA)))

    report: list[dict] = []
    mismatches = 0

    for index, (name, argv, stdin_text, check_mtime) in enumerate(CASES):
        base = sandbox_root / f"case{index:03d}"
        base.mkdir(parents=True)
        gnu_dir = base / "gnu"
        mine_dir = base / "mine"
        for target in (gnu_dir, mine_dir):
            target.mkdir()
            build_fixture(target)
            (target / "emptydir").mkdir()

        gnu = run_gnu(argv, gnu_dir, stdin_text)
        mine = run_mine(argv, mine_dir, stdin_text)

        gnu_tree = tree_state(gnu_dir)
        mine_tree = tree_state(mine_dir)
        gnu_pairs = T410.PAIR_RE.findall(gnu["out"])
        mine_pairs = T410.PAIR_RE.findall(mine["out"])

        problems: list[str] = []
        if (gnu["rc"] == 0) != (mine["rc"] == 0):
            problems.append(f"成功与否不同: GNU rc={gnu['rc']} 本实现 rc={mine['rc']}")
        if bool(gnu["err"].strip()) != bool(mine["err"].strip()):
            problems.append(
                f"有无报错不同: GNU err={gnu['err'].strip()!r} 本实现 err={mine['err'].strip()!r}"
            )
        if gnu_tree != mine_tree:
            only_gnu = {k: v for k, v in gnu_tree.items() if mine_tree.get(k) != v}
            only_mine = {k: v for k, v in mine_tree.items() if gnu_tree.get(k) != v}
            problems.append(f"目录树不同 GNU侧={only_gnu} 本实现侧={only_mine}")
        if sorted(gnu_pairs) != sorted(mine_pairs):
            problems.append(f"verbose 不同: GNU={gnu_pairs} 本实现={mine_pairs}")
        if check_mtime:
            gnu_mt = mtime_state(gnu_dir)
            mine_mt = mtime_state(mine_dir)
            if gnu_mt != mine_mt:
                diff = {
                    k: (gnu_mt.get(k), mine_mt.get(k))
                    for k in set(gnu_mt) | set(mine_mt)
                    if gnu_mt.get(k) != mine_mt.get(k)
                }
                problems.append(f"mtime 不同: {diff}")

        if problems:
            mismatches += 1

        report.append(
            {
                "name": name,
                "argv": argv,
                "stdin": stdin_text,
                "gnu": {"rc": gnu["rc"], "out": gnu["out"], "err": gnu["err"]},
                "mine": {"rc": mine["rc"], "out": mine["out"], "err": mine["err"]},
                "problems": problems,
            }
        )

        flag = "OK " if not problems else "DIFF"
        print(f"[{flag}] {name}  argv={' '.join(argv)}")
        for problem in problems:
            print("       -", problem)

    out_path = DATA / "diff_cp_defects.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 66)
    print(f"总用例 {len(CASES)}，不一致 {mismatches}")
    print("详细结果:", out_path)
    shutil.rmtree(sandbox_root, ignore_errors=True)
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
