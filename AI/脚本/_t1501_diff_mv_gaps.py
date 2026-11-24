"""差分对照（第二轮）：mv 的选项形态与交互应答，攻 _t510 没覆盖的角落。

_t510_diff_mv.py 覆盖 68 组、_t1312 覆盖 10 组，两轮都是「跑得通」的用例。
本脚本专打三类前者没碰的角度：

一、**-i 的应答解析**：_t510 只喂了 "y" / "n" / 空行 / EOF 四种。
    GNU 的 mv 对应答的判定是「第一个字符是不是 y/Y」，
    本实现是 strip().lower() 之后整个串精确匹配 "y" / "yes"。
    ⇒ "yeah"、"yes please"、" y"（前导空格）这三种会分叉。

二、**选项的写法形态**：_t510 全用分离式短选项（"-t destdir"），
    没测 GNU getopt 允许的附着式（"-tdestdir"）与长选项（"--target-directory=dir"）。
    也没测 "--backup=numbered" / "--backup=none" 这类 GNU 独有的取值。

三、**互斥选项的组合冲突**：GNU 在某些组合下直接报「不能同时指定」并退 1，
    本实现没有这类前置校验，冲突时靠执行期的判定顺序静默兜住。
"""

from __future__ import annotations

import hashlib
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
DATA = ROOT / "AI" / "数据" / "mv_diff2"

sys.path.insert(0, str(ROOT))

from w2l.commands.mv import build_parser, mv  # noqa: E402
from w2l.context import RunContext  # noqa: E402

GNU_MV = shutil.which("mv")
if GNU_MV is None:
    raise SystemExit("本机找不到 GNU mv")


def _load_t510():
    spec = importlib.util.spec_from_file_location("_t510_diff_mv", HERE / "_t510_diff_mv.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


T510 = _load_t510()

PAIR_RE = T510.PAIR_RE
BACKUP_RE = T510.BACKUP_RE
_FIXED_MTIME = T510._FIXED_MTIME
_NEWER_MTIME = T510._NEWER_MTIME


# ---------- 夹具 ----------

def build_fixture(root: Path) -> None:
    (root / "a.txt").write_bytes(b"hello mv\r\nsecond line\r\n")
    (root / "b.txt").write_bytes(b"old content\r\n")
    (root / "-weird.txt").write_bytes(b"leading dash\r\n")
    d = root / "dir1"
    d.mkdir()
    (d / "inner.txt").write_bytes(b"inner\r\n")
    sub = d / "sub"
    sub.mkdir()
    (sub / "deep.txt").write_bytes(b"deep\r\n")
    dest = root / "destdir"
    dest.mkdir()
    (dest / "b.txt").write_bytes(b"existing in destdir\r\n")
    (root / "emptydir").mkdir()


def apply_extras(root: Path, extras: list[str]) -> None:
    for extra in extras:
        if extra == "backup-exists":
            (root / "b.txt~").write_bytes(b"stale backup\r\n")
        elif extra == "backup-exists-dir":
            backup = root / "b.txt~"
            backup.mkdir()
            (backup / "inside.txt").write_bytes(b"inside backup\r\n")
        elif extra == "backup-exists-dir-nonempty":
            backup = root / "b.txt~"
            backup.mkdir()
            (backup / "inside.txt").write_bytes(b"inside backup\r\n")
        elif extra == "readonly-b":
            (root / "b.txt").chmod(0o444)
        elif extra == "destdir-b-readonly":
            (root / "destdir" / "b.txt").chmod(0o444)


def pin_timestamps(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        os_utime(path)
    os_utime(root)
    os_utime(root / "a.txt")
    os_utime(root / "b.txt")


def os_utime(path: Path) -> None:
    import os

    os.utime(path, (_FIXED_MTIME, _FIXED_MTIME))


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
    try:
        namespace = build_parser().parse_args(list(argv))
    except SystemExit as exc:
        return {"rc": 2, "out": "", "err": f"[argparse 退出 {exc.code}]"}
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(
        cwd=cwd,
        stdout=out,
        stderr=err,
        stdin=io.StringIO(stdin_text) if stdin_text is not None else io.StringIO(""),
    )
    try:
        code = mv(namespace, ctx)
    except SystemExit as exc:
        code = 2
        err.write(f"[运行期 SystemExit {exc.code}]")
    return {"rc": code, "out": out.getvalue(), "err": err.getvalue()}


# name, argv, stdin, extras
CASES: list[tuple[str, list[str], str | None, list[str]]] = [
    # ---------- 一、-i 的应答解析 ----------
    ("i-answer-Y", ["-i", "a.txt", "b.txt"], "Y\n", []),
    ("i-answer-yes", ["-i", "a.txt", "b.txt"], "yes\n", []),
    ("i-answer-YES", ["-i", "a.txt", "b.txt"], "YES\n", []),
    ("i-answer-yeah", ["-i", "a.txt", "b.txt"], "yeah\n", []),
    ("i-answer-yes-space", ["-i", "a.txt", "b.txt"], "yes please\n", []),
    ("i-answer-leading-space-y", ["-i", "a.txt", "b.txt"], " y\n", []),
    ("i-answer-leading-space-yes", ["-i", "a.txt", "b.txt"], " yes\n", []),
    ("i-answer-n", ["-i", "a.txt", "b.txt"], "n\n", []),
    ("i-answer-N", ["-i", "a.txt", "b.txt"], "N\n", []),
    ("i-answer-no", ["-i", "a.txt", "b.txt"], "no\n", []),
    ("i-answer-tab-y", ["-i", "a.txt", "b.txt"], "\ty\n", []),
    ("i-answer-empty-line", ["-i", "a.txt", "b.txt"], "\n", []),
    ("i-answer-eof", ["-i", "a.txt", "b.txt"], "", []),
    ("i-answer-y-then-more", ["-i", "a.txt", "b.txt", "c.txt"], "y\n", []),
    # ---------- 二、选项的写法形态 ----------
    ("suffix-attached", ["-S.bak", "a.txt", "b.txt"], None, []),
    ("suffix-long-eq", ["--suffix=.bak", "a.txt", "b.txt"], None, []),
    ("suffix-long-space", ["--suffix", ".bak", "a.txt", "b.txt"], None, []),
    ("target-dir-attached", ["-tdestdir", "a.txt"], None, []),
    ("target-dir-long-eq", ["--target-directory=destdir", "a.txt"], None, []),
    ("target-dir-long-space", ["--target-directory", "destdir", "a.txt"], None, []),
    ("no-target-dir-long", ["--no-target-directory", "a.txt", "destdir"], None, []),
    ("backup-numbered", ["--backup=numbered", "a.txt", "b.txt"], None, []),
    ("backup-none", ["--backup=none", "a.txt", "b.txt"], None, []),
    ("backup-simple", ["--backup=simple", "a.txt", "b.txt"], None, []),
    ("backup-long", ["--backup", "a.txt", "b.txt"], None, []),
    ("force-long", ["--force", "a.txt", "b.txt"], None, []),
    ("update-long", ["--update", "old.txt", "new.txt"], None, []),
    ("verbose-long", ["--verbose", "a.txt", "copy.txt"], None, []),
    ("noclobber-long", ["--no-clobber", "a.txt", "b.txt"], None, []),
    ("interactive-long", ["--interactive", "a.txt", "b.txt"], "y\n", []),
    # ---------- 三、互斥组合的冲突 ----------
    ("backup-and-noclobber", ["-b", "-n", "a.txt", "b.txt"], None, []),
    ("noclobber-and-backup", ["-n", "-b", "a.txt", "b.txt"], None, []),
    ("backup-and-interactive", ["-b", "-i", "a.txt", "b.txt"], "y\n", []),
    ("force-and-noclobber", ["-f", "-n", "a.txt", "b.txt"], None, []),
    ("noclobber-and-force", ["-n", "-f", "a.txt", "b.txt"], None, []),
    ("force-and-interactive", ["-f", "-i", "a.txt", "b.txt"], "y\n", []),
    ("target-dir-and-no-target-dir", ["-t", "destdir", "-T", "a.txt"], None, []),
    ("no-target-dir-and-target-dir", ["-T", "-t", "destdir", "a.txt"], None, []),
    # ---------- 四、备份目标已存在 ----------
    ("backup-existing-file", ["-b", "a.txt", "b.txt"], None, ["backup-exists"]),
    ("backup-existing-dir", ["-b", "a.txt", "b.txt"], None, ["backup-exists-dir"]),
    ("backup-existing-dir-nonempty", ["-b", "a.txt", "b.txt"], None, ["backup-exists-dir-nonempty"]),
    ("backup-existing-verbose", ["-b", "-v", "a.txt", "b.txt"], None, ["backup-exists"]),
    # ---------- 五、其它边角 ----------
    ("dashdash-file", ["--", "-weird.txt", "copy.txt"], None, []),
    ("dashdash-file-to-dir", ["--", "-weird.txt", "destdir"], None, []),
    ("readonly-dest-in-dir", ["a.txt", "destdir/b.txt"], None, ["destdir-b-readonly"]),
    ("readonly-dest-in-dir-force", ["-f", "a.txt", "destdir/b.txt"], None, ["destdir-b-readonly"]),
    ("multi-one-missing-into-dir", ["a.txt", "nosuch.txt", "destdir"], None, []),
    ("multi-one-missing-then-ok", ["nosuch.txt", "a.txt", "destdir"], None, []),
    ("empty-dir-onto-empty-dir", ["emptydir", "destdir"], None, []),
    ("dir-onto-empty-dir-same-name", ["dir1", "destdir/dir1"], None, []),
    ("verbose-and-backup-and-i", ["-v", "-b", "-i", "a.txt", "b.txt"], "y\n", []),
    ("update-equal-mtime", ["-u", "a.txt", "b.txt"], None, []),
]


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    sandbox_root = Path(tempfile.mkdtemp(prefix="mvdiff2_", dir=str(DATA)))

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
        gnu_pairs = PAIR_RE.findall(gnu["out"])
        mine_pairs = PAIR_RE.findall(mine["out"])
        if gnu_pairs != mine_pairs:
            problems.append(f"verbose 不同: GNU={gnu_pairs} 本实现={mine_pairs}")
        gnu_backup = BACKUP_RE.findall(gnu["out"])
        mine_backup = BACKUP_RE.findall(mine["out"])
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
                "gnu": gnu,
                "mine": mine,
                "problems": problems,
            }
        )

        flag = "OK " if not problems else "DIFF"
        print(f"[{flag}] {name}  argv={' '.join(argv)} stdin={stdin_text!r}")
        for problem in problems:
            print("       -", problem)

    out_path = DATA / "diff_mv2.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 66)
    print(f"总用例 {len(CASES)}，不一致 {mismatches}")
    print("详细结果:", out_path)
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
