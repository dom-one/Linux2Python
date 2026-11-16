"""探针：摸清 Git Bash 的 GNU mv 的真实行为，作为实现 mv 的语义基线。

每组用例在全新沙箱里跑一次 GNU mv，记录：退出码、标准输出、标准错误、
以及跑完之后的目录树（路径 + 字节内容 + 是否目录）。

用法:
    python AI/脚本/_t500_probe_mv.py
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "mv_probe"

GNU_MV = shutil.which("mv")
if GNU_MV is None:
    raise SystemExit("本机找不到 GNU mv")


def build_fixture(root: Path) -> None:
    (root / "a.txt").write_bytes(b"hello mv\r\nsecond line\r\n")
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
    (dest / "a.txt").write_bytes(b"existing a in destdir\r\n")
    (root / "emptydir").mkdir()


def tree_state(root: Path) -> dict:
    state: dict = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            state[rel] = "DIR"
        else:
            data = path.read_bytes()
            state[rel] = f"FILE {len(data)} {hashlib.sha256(data).hexdigest()[:12]}"
    return state


CASES: list[tuple[str, list[str], str | None, list[str]]] = [
    # 名字, argv, stdin, 额外预置（相对沙箱根的路径）
    ("file-to-new", ["a.txt", "copy.txt"], None, []),
    ("file-over-file", ["a.txt", "b.txt"], None, []),
    ("file-into-dir", ["a.txt", "destdir"], None, []),
    ("file-into-dir-slash", ["a.txt", "destdir/"], None, []),
    ("file-into-dir-overwrite", ["a.txt", "destdir/a.txt"], None, []),
    ("dir-into-dir", ["dir1", "destdir"], None, []),
    ("dir-into-dir-slash", ["dir1", "destdir/"], None, []),
    ("dir-to-new", ["dir1", "newdest"], None, []),
    ("dir-to-new-slash", ["dir1", "newdest/"], None, []),
    ("dir-merge", ["dir1", "destdir"], None, ["destdir/dir1"]),
    ("dir-merge-file-clash", ["dir1", "destdir"], None, ["destdir/dir1"]),
    ("dir-src-trailing-slash", ["dir1/", "destdir"], None, []),
    ("multi-into-dir", ["a.txt", "b.txt", "destdir"], None, []),
    ("multi-to-new", ["a.txt", "b.txt", "newtarget"], None, []),
    ("missing-src", ["nosuch.txt", "copy.txt"], None, []),
    ("missing-src-multi", ["a.txt", "nosuch.txt", "copy.txt"], None, []),
    ("no-operand", [], None, []),
    ("one-operand", ["a.txt"], None, []),
    ("same-file", ["a.txt", "a.txt"], None, []),
    ("same-file-different-path", ["a.txt", "./a.txt"], None, []),
    ("dir-into-itself", ["dir1", "dir1/sub"], None, []),
    ("file-onto-dir", ["a.txt", "destdir"], None, []),
    ("dir-onto-file", ["dir1", "b.txt"], None, []),
    ("verbose-file", ["-v", "a.txt", "copy.txt"], None, []),
    ("verbose-over", ["-v", "a.txt", "b.txt"], None, []),
    ("verbose-into-dir", ["-v", "a.txt", "destdir"], None, []),
    ("verbose-dir", ["-v", "dir1", "destdir"], None, []),
    ("verbose-dir-new", ["-v", "dir1", "newdest"], None, []),
    ("verbose-dir-merge", ["-v", "dir1", "destdir"], None, ["destdir/dir1"]),
    ("verbose-multi", ["-v", "a.txt", "b.txt", "destdir"], None, []),
    ("noclobber-new", ["-n", "a.txt", "copy.txt"], None, []),
    ("noclobber-over", ["-n", "a.txt", "b.txt"], None, []),
    ("noclobber-into-dir", ["-n", "a.txt", "destdir/a.txt"], None, []),
    ("noclobber-dir-merge", ["-n", "dir1", "destdir"], None, ["destdir/dir1"]),
    ("update-older", ["-u", "a.txt", "b.txt"], None, []),
    ("update-newer", ["-u", "b.txt", "a.txt"], None, []),
    ("force-over", ["-f", "a.txt", "b.txt"], None, []),
    ("interactive-yes", ["-i", "a.txt", "b.txt"], "y\n", []),
    ("interactive-no", ["-i", "a.txt", "b.txt"], "n\n", []),
    ("interactive-new", ["-i", "a.txt", "copy.txt"], "y\n", []),
    ("backup-default", ["-b", "a.txt", "b.txt"], None, []),
    ("backup-suffix", ["-b", "-S", ".bak", "a.txt", "b.txt"], None, []),
    ("backup-dir", ["-b", "dir1", "destdir"], None, []),
    ("target-dir", ["-t", "destdir", "a.txt"], None, []),
    ("target-dir-missing", ["-t", "nosuchdir", "a.txt"], None, []),
    ("target-dir-multi", ["-t", "destdir", "a.txt", "b.txt"], None, []),
    ("no-target-dir", ["-T", "a.txt", "destdir"], None, []),
    ("no-target-dir-dir", ["-T", "dir1", "destdir"], None, []),
    ("no-target-dir-three", ["-T", "a.txt", "b.txt", "c.txt"], None, []),
    ("binary", ["bin.dat", "bin.copy"], None, []),
    ("empty", ["empty.txt", "empty.copy"], None, []),
    ("dot-source", ["./a.txt", "copy.txt"], None, []),
    ("empty-dir", ["emptydir", "destdir"], None, []),
    ("into-missing-parent", ["a.txt", "nodir/out.txt"], None, []),
]


def make_extra(root: Path, rel: str) -> None:
    """给沙箱补一份预置内容，用来制造「目标已存在」的场景。"""
    if rel.endswith("/dir1"):
        target = root / "destdir" / "dir1"
        target.mkdir(parents=True, exist_ok=True)
        (target / "inner.txt").write_bytes(b"OLD inner\r\n")
        (target / "stale.txt").write_bytes(b"stale\r\n")
    else:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"existing\r\n")


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    sandbox_root = Path(tempfile.mkdtemp(prefix="mvprobe_", dir=str(DATA)))

    print("GNU mv =", GNU_MV)
    version = subprocess.run(
        [GNU_MV, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    print(version.stdout.decode("utf-8", "replace").splitlines()[0])

    report: list[dict] = []
    for index, (name, argv, stdin_text, extras) in enumerate(CASES):
        base = sandbox_root / f"case{index:03d}"
        base.mkdir(parents=True)
        sandbox = base / "s"
        sandbox.mkdir()
        build_fixture(sandbox)
        for extra in extras:
            make_extra(sandbox, extra)

        proc = subprocess.run(
            [GNU_MV, *argv],
            cwd=str(sandbox),
            input=stdin_text.encode() if stdin_text is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        result = {
            "name": name,
            "argv": argv,
            "stdin": stdin_text,
            "rc": proc.returncode,
            "out": proc.stdout.decode("utf-8", "replace"),
            "err": proc.stderr.decode("utf-8", "replace"),
            "tree": tree_state(sandbox),
        }
        report.append(result)

        print("=" * 70)
        print(f"[{name}] argv={' '.join(argv)}")
        print(f"  rc  = {result['rc']}")
        print(f"  out = {result['out']!r}")
        print(f"  err = {result['err']!r}")
        print("  tree:")
        for key, value in result["tree"].items():
            print(f"    {key}  ->  {value}")

    out_path = DATA / "probe_mv.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=" * 70)
    print("详细结果:", out_path)
    print("沙箱:", sandbox_root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
