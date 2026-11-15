"""差分对照：把本实现的 cp 与 Git Bash 的 GNU cp 8.32 逐组比对。

每组用例在两个一模一样的沙箱里各跑一次：
- 沙箱 A 跑 GNU /usr/bin/cp
- 沙箱 B 跑本实现 w2l/commands/cp.py

比三样：落地后的目录树（路径 + 字节内容）、成功/失败、verbose 的
「'src' -> 'dst'」对序列。报错文案两边语言不同（GNU 英文、本实现中文），
只比对「有没有报错」这一层。
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "cp_probe"

sys.path.insert(0, str(ROOT))

from w2l.commands.cp import build_parser, cp  # noqa: E402
from w2l.context import RunContext  # noqa: E402

GNU_CP = shutil.which("cp")
if GNU_CP is None:
    raise SystemExit("本机找不到 GNU cp")

PAIR_RE = re.compile(r"'([^']*)' -> '([^']*)'")
_FIXED_MTIME = 1_000_000_000


def build_fixture(root: Path) -> None:
    (root / "a.txt").write_bytes(b"hello cp\r\nsecond line\r\n")
    (root / "b.txt").write_bytes(b"old content\r\n")
    (root / "bin.dat").write_bytes(bytes(range(256)))
    (root / "empty.txt").write_bytes(b"")
    d = root / "dir1"
    d.mkdir()
    (d / "inner.txt").write_bytes(b"inner\r\n")
    (d / "only.txt").write_bytes(b"only here\r\n")
    sub = d / "sub"
    sub.mkdir()
    (sub / "deep.txt").write_bytes(b"deep\r\n")
    dest = root / "destdir"
    dest.mkdir()
    (dest / "b.txt").write_bytes(b"existing in destdir\r\n")
    # 把时间戳钉死：两个沙箱的源必须一模一样，mtime 才能直接跨沙箱比。
    for path in sorted(root.rglob("*"), reverse=True):
        os.utime(path, (_FIXED_MTIME, _FIXED_MTIME))
    os.utime(root, (_FIXED_MTIME, _FIXED_MTIME))


def tree_state(root: Path) -> dict:
    state: dict = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            state[rel] = "DIR"
        else:
            data = path.read_bytes()
            state[rel] = f"FILE {len(data)} {hashlib.sha256(data).hexdigest()[:16]}"
    return state


def mtime_state(root: Path) -> dict:
    """把 mtime 归成两类：保住源时间戳的算 "preserved"，复制时刻算 "fresh"。

    两个沙箱的「复制时刻」本来就差几毫秒，直接比数值没有意义；
    要比的是「这个条目的时间戳有没有被原样搬过来」。
    """
    state: dict = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        try:
            stamp = path.stat().st_mtime
        except OSError:
            state[rel] = "missing"
            continue
        state[rel] = "preserved" if abs(stamp - _FIXED_MTIME) < 0.5 else "fresh"
    return state


def run_gnu(argv: list[str], cwd: Path, stdin_text: str | None) -> dict:
    proc = subprocess.run(
        [GNU_CP, *argv],
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
    namespace = build_parser().parse_args(list(argv))
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(
        cwd=cwd,
        stdout=out,
        stderr=err,
        stdin=io.StringIO(stdin_text) if stdin_text is not None else io.StringIO(""),
    )
    code = cp(namespace, ctx)
    return {"rc": code, "out": out.getvalue(), "err": err.getvalue()}


CASES: list[tuple[str, list[str], str | None, bool]] = [
    # 名字, argv, stdin, 是否比对 mtime
    ("file-to-new", ["a.txt", "copy.txt"], None, False),
    ("file-over-file", ["a.txt", "b.txt"], None, False),
    ("file-into-dir", ["a.txt", "destdir"], None, False),
    ("file-into-dir-slash", ["a.txt", "destdir/"], None, False),
    ("file-to-new-path", ["a.txt", "newdir"], None, False),
    ("binary", ["bin.dat", "bin.copy"], None, False),
    ("empty", ["empty.txt", "empty.copy"], None, False),
    ("dir-no-r", ["dir1", "destdir"], None, False),
    ("dir-r-into-dir", ["-r", "dir1", "destdir"], None, False),
    ("dir-r-trailing-slash", ["-r", "dir1/", "destdir"], None, False),
    ("dir-r-to-new", ["-r", "dir1", "newdest"], None, False),
    ("dir-r-multi", ["-r", "dir1", "destdir", "a.txt"], None, False),
    ("dir-R", ["-R", "dir1", "destdir"], None, False),
    ("dir-a", ["-a", "dir1", "destdir"], None, True),
    ("missing-src", ["nosuch.txt", "copy.txt"], None, False),
    ("missing-src-multi", ["a.txt", "nosuch.txt", "copy.txt"], None, False),
    ("no-operand", [], None, False),
    ("one-operand", ["a.txt"], None, False),
    ("dest-not-dir-multi", ["a.txt", "b.txt", "destdir"], None, False),
    ("dest-is-file-multi", ["a.txt", "b.txt", "copy.txt"], None, False),
    ("three-operands-new-target", ["a.txt", "b.txt", "newtarget"], None, False),
    ("verbose-new", ["-v", "a.txt", "copy.txt"], None, False),
    ("verbose-over", ["-v", "a.txt", "b.txt"], None, False),
    ("verbose-dir", ["-v", "-r", "dir1", "destdir"], None, False),
    ("verbose-dir-new", ["-v", "-r", "dir1", "newdest"], None, False),
    ("verbose-two-into-dir", ["-v", "a.txt", "b.txt", "destdir"], None, False),
    ("noclobber-new", ["-n", "a.txt", "copy.txt"], None, False),
    ("noclobber-over", ["-n", "a.txt", "b.txt"], None, False),
    ("noclobber-dir", ["-n", "-r", "dir1", "destdir"], None, False),
    ("update-newer", ["-u", "b.txt", "a.txt"], None, False),
    ("update-older", ["-u", "a.txt", "b.txt"], None, False),
    ("force", ["-f", "a.txt", "b.txt"], None, False),
    ("interactive-yes", ["-i", "a.txt", "b.txt"], "y\n", False),
    ("interactive-no", ["-i", "a.txt", "b.txt"], "n\n", False),
    ("interactive-new", ["-i", "a.txt", "copy.txt"], "y\n", False),
    ("preserve", ["-p", "a.txt", "copy.txt"], None, True),
    ("preserve-dir", ["-p", "-r", "dir1", "destdir"], None, True),
    ("archive-file", ["-a", "a.txt", "copy.txt"], None, True),
    ("target-dir", ["-t", "destdir", "a.txt"], None, False),
    ("target-dir-missing", ["-t", "nosuchdir", "a.txt"], None, False),
    ("target-dir-multi", ["-t", "destdir", "a.txt", "b.txt"], None, False),
    ("target-dir-is-file", ["-t", "a.txt", "a.txt"], None, False),
    ("no-target-dir-file", ["-T", "a.txt", "destdir"], None, False),
    ("no-target-dir-dir", ["-T", "-r", "dir1", "destdir"], None, False),
    ("no-target-dir-three", ["-T", "a.txt", "b.txt", "c.txt"], None, False),
    ("parents", ["--parents", "dir1/inner.txt", "destdir"], None, False),
    ("parents-multi", ["--parents", "a.txt", "dir1/inner.txt", "destdir"], None, False),
    ("parents-missing-target", ["--parents", "a.txt", "newdir"], None, False),
    ("suffix", ["-S", ".bak", "a.txt", "b.txt"], None, False),
    ("same-file", ["a.txt", "a.txt"], None, False),
    ("dot-source", ["./a.txt", "copy.txt"], None, False),
    ("dir-src-dest-file", ["-r", "dir1", "a.txt"], None, False),
    ("dir-src-dest-file-nor", ["dir1", "a.txt"], None, False),
    ("missing-parent", ["a.txt", "nodir/out.txt"], None, False),
    ("missing-parent-dir", ["-r", "dir1", "nodir/out"], None, False),
    ("remove-destination", ["--remove-destination", "a.txt", "b.txt"], None, False),
    ("recursive-empty", ["-r", "emptydir", "destdir"], None, False),
]


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    sandbox_root = Path(tempfile.mkdtemp(prefix="cpdiff_", dir=str(DATA)))

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
        gnu_pairs = PAIR_RE.findall(gnu["out"])
        mine_pairs = PAIR_RE.findall(mine["out"])

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
        if gnu_pairs != mine_pairs:
            # GNU 的遍历顺序是 readdir 顺序（两个沙箱的目录项顺序本来就不同），
            # 本实现走的是排序后的顺序，所以只比集合不比先后。
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

    out_path = DATA / "diff_cp.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 66)
    print(f"总用例 {len(CASES)}，不一致 {mismatches}")
    print("详细结果:", out_path)
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
