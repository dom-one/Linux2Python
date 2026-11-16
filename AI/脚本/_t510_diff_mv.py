"""差分对照：把本实现的 mv 与 Git Bash 的 GNU mv 8.32 逐组比对。

每组用例在两个一模一样的沙箱里各跑一次：
- 沙箱 A 跑 GNU /usr/bin/mv
- 沙箱 B 跑本实现 w2l/commands/mv.py

比四样：落地后的目录树（路径 + 字节内容）、成功/失败、verbose 的
「renamed 'src' -> 'dst'」对序列、时间戳是「原样搬过来」还是「变了」。

两个度量坑（与 cp 那轮同源）：
① 沙箱的创建时刻不同，mtime 直接比数值必然假不一致 ⇒ 夹具时间戳用 os.utime
   钉死，比的时候归成「钉死的值 / 其它」两类再比；
② 目录的 mtime 会因为内容变动而变成「当前时刻」，两个沙箱差几毫秒 ⇒ 目录只比
   「是不是钉死的值」，不比具体数值。

报错文案两边语言不同（GNU 英文、本实现中文），只比对「有没有报错」这一层。
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
DATA = ROOT / "AI" / "数据" / "mv_diff"

sys.path.insert(0, str(ROOT))

from w2l.commands.mv import build_parser, mv  # noqa: E402
from w2l.context import RunContext  # noqa: E402

GNU_MV = shutil.which("mv")
if GNU_MV is None:
    raise SystemExit("本机找不到 GNU mv")

PAIR_RE = re.compile(r"renamed '([^']*)' -> '([^']*)'")
BACKUP_RE = re.compile(r"\(backup: '([^']*)'\)")
_FIXED_MTIME = 1_000_000_000
_NEWER_MTIME = 1_000_000_005


def build_fixture(root: Path) -> None:
    (root / "a.txt").write_bytes(b"hello mv\r\nsecond line\r\n")
    (root / "b.txt").write_bytes(b"old content\r\n")
    (root / "bin.dat").write_bytes(bytes(range(256)))
    (root / "empty.txt").write_bytes(b"")
    (root / "old.txt").write_bytes(b"older\r\n")
    (root / "new.txt").write_bytes(b"newer\r\n")
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
    (dest / "a.txt").write_bytes(b"existing a in destdir\r\n")
    (root / "emptydir").mkdir()


def apply_extras(root: Path, extras: list[str]) -> None:
    """按用例需要补预置内容，制造「目标已存在」的场景。"""
    for extra in extras:
        if extra == "dir1-nonempty":
            target = root / "destdir" / "dir1"
            target.mkdir(parents=True, exist_ok=True)
            (target / "inner.txt").write_bytes(b"OLD inner\r\n")
            (target / "stale.txt").write_bytes(b"stale\r\n")
        elif extra == "dir1-empty":
            (root / "destdir" / "dir1").mkdir(parents=True, exist_ok=True)
        elif extra == "dir1-is-file":
            (root / "destdir" / "dir1").write_bytes(b"i am a file\r\n")
        elif extra == "readonly-b":
            (root / "b.txt").chmod(0o444)


def pin_timestamps(root: Path) -> None:
    """把夹具的时间戳钉死：两个沙箱必须一模一样，mtime 才能跨沙箱比。"""
    for path in sorted(root.rglob("*"), reverse=True):
        os.utime(path, (_FIXED_MTIME, _FIXED_MTIME))
    os.utime(root, (_FIXED_MTIME, _FIXED_MTIME))
    # 这一对专门给 -u 用：new.txt 比 old.txt 新 5 秒。
    os.utime(root / "old.txt", (_FIXED_MTIME, _FIXED_MTIME))
    os.utime(root / "new.txt", (_NEWER_MTIME, _NEWER_MTIME))


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
    """时间戳归成三类：钉死的值 / 比钉死值新 / 拿不到。"""
    state: dict = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        try:
            stamp = path.stat().st_mtime
        except OSError:
            state[rel] = "missing"
            continue
        if abs(stamp - _FIXED_MTIME) < 0.5:
            state[rel] = "pinned"
        elif abs(stamp - _NEWER_MTIME) < 0.5:
            state[rel] = "pinned-newer"
        else:
            state[rel] = "changed"
    return state


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
    namespace = build_parser().parse_args(list(argv))
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(
        cwd=cwd,
        stdout=out,
        stderr=err,
        stdin=io.StringIO(stdin_text) if stdin_text is not None else io.StringIO(""),
    )
    code = mv(namespace, ctx)
    return {"rc": code, "out": out.getvalue(), "err": err.getvalue()}


# 名字, argv, stdin, 预置
CASES: list[tuple[str, list[str], str | None, list[str]]] = [
    ("file-to-new", ["a.txt", "copy.txt"], None, []),
    ("file-over-file", ["a.txt", "b.txt"], None, []),
    ("file-into-dir", ["a.txt", "destdir"], None, []),
    ("file-into-dir-slash", ["a.txt", "destdir/"], None, []),
    ("file-into-dir-overwrite", ["a.txt", "destdir/a.txt"], None, []),
    ("dir-into-dir", ["dir1", "destdir"], None, []),
    ("dir-into-dir-slash", ["dir1", "destdir/"], None, []),
    ("dir-to-new", ["dir1", "newdest"], None, []),
    ("dir-to-new-slash", ["dir1", "newdest/"], None, []),
    ("dir-merge-nonempty", ["dir1", "destdir"], None, ["dir1-nonempty"]),
    ("dir-merge-empty", ["dir1", "destdir"], None, ["dir1-empty"]),
    ("dir-merge-file-clash", ["dir1", "destdir"], None, ["dir1-is-file"]),
    ("dir-src-trailing-slash", ["dir1/", "destdir"], None, []),
    ("multi-into-dir", ["a.txt", "b.txt", "destdir"], None, []),
    ("multi-mixed-into-dir", ["dir1", "b.txt", "destdir"], None, []),
    ("multi-to-new", ["a.txt", "b.txt", "newtarget"], None, []),
    ("missing-src", ["nosuch.txt", "copy.txt"], None, []),
    ("missing-src-multi", ["a.txt", "nosuch.txt", "copy.txt"], None, []),
    ("src-parent-missing", ["nodir/a.txt", "copy.txt"], None, []),
    ("no-operand", [], None, []),
    ("one-operand", ["a.txt"], None, []),
    ("same-file", ["a.txt", "a.txt"], None, []),
    ("same-file-different-path", ["a.txt", "./a.txt"], None, []),
    ("dir-into-itself", ["dir1", "dir1/sub"], None, []),
    ("dir-onto-itself", ["dir1", "dir1"], None, []),
    ("dir-onto-file", ["dir1", "b.txt"], None, []),
    ("verbose-file", ["-v", "a.txt", "copy.txt"], None, []),
    ("verbose-over", ["-v", "a.txt", "b.txt"], None, []),
    ("verbose-into-dir", ["-v", "a.txt", "destdir"], None, []),
    ("verbose-dir", ["-v", "dir1", "destdir"], None, []),
    ("verbose-dir-new", ["-v", "dir1", "newdest"], None, []),
    ("verbose-multi", ["-v", "a.txt", "b.txt", "destdir"], None, []),
    ("verbose-backup", ["-b", "-v", "a.txt", "b.txt"], None, []),
    ("noclobber-new", ["-n", "a.txt", "copy.txt"], None, []),
    ("noclobber-over", ["-n", "a.txt", "b.txt"], None, []),
    ("noclobber-into-dir", ["-n", "a.txt", "destdir/a.txt"], None, []),
    ("noclobber-dir-merge", ["-n", "dir1", "destdir"], None, ["dir1-nonempty"]),
    ("noclobber-verbose", ["-n", "-v", "a.txt", "b.txt"], None, []),
    ("update-older", ["-u", "old.txt", "new.txt"], None, []),
    ("update-newer", ["-u", "new.txt", "old.txt"], None, []),
    ("update-same", ["-u", "old.txt", "b.txt"], None, []),
    ("force-over", ["-f", "a.txt", "b.txt"], None, []),
    ("readonly-dest", ["a.txt", "b.txt"], None, ["readonly-b"]),
    ("readonly-dest-force", ["-f", "a.txt", "b.txt"], None, ["readonly-b"]),
    ("interactive-yes", ["-i", "a.txt", "b.txt"], "y\n", []),
    ("interactive-no", ["-i", "a.txt", "b.txt"], "n\n", []),
    ("interactive-new", ["-i", "a.txt", "copy.txt"], "y\n", []),
    ("interactive-empty-answer", ["-i", "a.txt", "b.txt"], "\n", []),
    ("interactive-eof", ["-i", "a.txt", "b.txt"], "", []),
    ("ni-then-ni", ["-n", "-i", "a.txt", "b.txt"], "y\n", []),
    ("i-then-ni", ["-i", "-n", "a.txt", "b.txt"], "y\n", []),
    ("backup-default", ["-b", "a.txt", "b.txt"], None, []),
    ("backup-suffix", ["-b", "-S", ".bak", "a.txt", "b.txt"], None, []),
    ("suffix-alone", ["-S", ".bak", "a.txt", "b.txt"], None, []),
    ("backup-dir", ["-b", "dir1", "destdir"], None, ["dir1-empty"]),
    ("target-dir", ["-t", "destdir", "a.txt"], None, []),
    ("target-dir-missing", ["-t", "nosuchdir", "a.txt"], None, []),
    ("target-dir-multi", ["-t", "destdir", "a.txt", "b.txt"], None, []),
    ("no-target-dir", ["-T", "a.txt", "destdir"], None, []),
    ("no-target-dir-dir", ["-T", "dir1", "destdir"], None, []),
    ("no-target-dir-new", ["-T", "dir1", "newdest"], None, []),
    ("no-target-dir-three", ["-T", "a.txt", "b.txt", "c.txt"], None, []),
    ("binary", ["bin.dat", "bin.copy"], None, []),
    ("empty", ["empty.txt", "empty.copy"], None, []),
    ("dot-source", ["./a.txt", "copy.txt"], None, []),
    ("empty-dir", ["emptydir", "destdir"], None, []),
    ("into-missing-parent", ["a.txt", "nodir/out.txt"], None, []),
    ("dest-parent-missing-dir", ["dir1", "nodir/out"], None, []),
]


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    sandbox_root = Path(tempfile.mkdtemp(prefix="mvdiff_", dir=str(DATA)))

    report: list[dict] = []
    mismatches = 0

    for index, (name, argv, stdin_text, extras) in enumerate(CASES):
        base = sandbox_root / f"case{index:03d}"
        base.mkdir(parents=True)
        gnu_dir = base / "gnu"
        mine_dir = base / "mine"
        for target in (gnu_dir, mine_dir):
            target.mkdir()
            build_fixture(target)
            apply_extras(target, extras)
            pin_timestamps(target)

        gnu = run_gnu(argv, gnu_dir, stdin_text)
        mine = run_mine(argv, mine_dir, stdin_text)

        gnu_tree = tree_state(gnu_dir)
        mine_tree = tree_state(mine_dir)
        gnu_pairs = PAIR_RE.findall(gnu["out"])
        mine_pairs = PAIR_RE.findall(mine["out"])
        gnu_backup = BACKUP_RE.findall(gnu["out"])
        mine_backup = BACKUP_RE.findall(mine["out"])

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
            problems.append(f"verbose 不同: GNU={gnu_pairs} 本实现={mine_pairs}")
        if gnu_backup != mine_backup:
            problems.append(f"备份提示不同: GNU={gnu_backup} 本实现={mine_backup}")
        gnu_mt = mtime_state(gnu_dir)
        mine_mt = mtime_state(mine_dir)
        if gnu_mt != mine_mt:
            diff = {
                k: (gnu_mt.get(k), mine_mt.get(k))
                for k in set(gnu_mt) | set(mine_mt)
                if gnu_mt.get(k) != mine_mt.get(k)
            }
            problems.append(f"时间戳类别不同: {diff}")

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

    out_path = DATA / "diff_mv.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 66)
    print(f"总用例 {len(CASES)}，不一致 {mismatches}")
    print("详细结果:", out_path)
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
