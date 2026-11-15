"""探针 3：补齐 cp 的最后一批语义点。

- 三个操作数、目标是文件/不存在时的报错
- -n 递归合并时是否跳过已存在文件
- -u 的相等 mtime 判定
- -p 覆盖已存在目标时是否保住 mtime；目录 mtime 是否也保住
- -a 对普通文件是否保住 mtime
- -i 的应答字符串认哪些
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "cp_probe"

CP = shutil.which("cp")
if CP is None:
    raise SystemExit("本机找不到 cp 可执行文件")


def build(tmp: Path) -> None:
    (tmp / "a.txt").write_bytes(b"hello cp\r\n")
    (tmp / "b.txt").write_bytes(b"second file\r\n")
    d = tmp / "dir1"
    d.mkdir()
    (d / "inner.txt").write_bytes(b"inner\r\n")
    (d / "sub").mkdir()
    (d / "sub" / "deep.txt").write_bytes(b"deep\r\n")
    dst = tmp / "destdir"
    dst.mkdir()
    (dst / "b.txt").write_bytes(b"existing in destdir\r\n")


def run(argv: list[str], cwd: Path, stdin_text: str | None = None) -> dict:
    proc = subprocess.run(
        [CP, *argv],
        cwd=str(cwd),
        input=stdin_text.encode("utf-8") if stdin_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "rc": proc.returncode,
        "out": proc.stdout.decode("utf-8", "replace"),
        "err": proc.stderr.decode("utf-8", "replace"),
    }


def mt(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def force_rmtree(path: Path) -> None:
    """删目录前先把只读位去掉，否则 Windows 上 PermissionError。"""
    if not path.exists():
        return
    for item in path.rglob("*"):
        try:
            os.chmod(item, 0o700)
        except OSError:
            pass
    shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    if DATA.exists():
        force_rmtree(DATA)
    DATA.mkdir(parents=True)
    report: list[dict] = []

    def case(name: str, argv: list[str], stdin_text: str | None = None, setup=None):
        tmp = Path(tempfile.mkdtemp(prefix="cpprobe3_", dir=str(DATA)))
        build(tmp)
        if setup:
            setup(tmp)
        r = run(argv, tmp, stdin_text)
        report.append({"name": name, "argv": argv, "rc": r["rc"], "out": r["out"], "err": r["err"]})
        print("=" * 70)
        print("CASE:", name, "|", " ".join(argv))
        print("RC  :", r["rc"])
        if r["out"]:
            print("OUT :", repr(r["out"]))
        if r["err"]:
            print("ERR :", repr(r["err"]))
        return tmp

    # 1. 三个操作数，目标不存在
    case("three-operands-new-target", ["a.txt", "b.txt", "newtarget"])

    # 2. -n 递归合并
    def setup_existing(tmp: Path):
        (tmp / "destdir" / "dir1").mkdir()
        (tmp / "destdir" / "dir1" / "inner.txt").write_bytes(b"OLD inner\r\n")

    tmp = case("noclobber-merge", ["-n", "-r", "dir1", "destdir"], None, setup_existing)
    print("   merge 结果:", (tmp / "destdir/dir1/inner.txt").read_bytes())

    tmp = case("noclobber-merge-v", ["-n", "-v", "-r", "dir1", "destdir"], None, setup_existing)

    # 3. -u 相等 mtime
    def setup_same_mtime(tmp: Path):
        t = 1000000000
        os.utime(tmp / "a.txt", (t, t))
        os.utime(tmp / "b.txt", (t, t))

    case("update-equal-mtime", ["-u", "a.txt", "b.txt"], None, setup_same_mtime)

    # 4. -p 覆盖已存在目标，是否保住 mtime
    def setup_old_dest(tmp: Path):
        t = 1000000000
        os.utime(tmp / "a.txt", (t, t))
        os.utime(tmp / "b.txt", (t + 500, t + 500))

    tmp = case("preserve-overwrite-existing", ["-p", "a.txt", "b.txt"], None, setup_old_dest)
    print("   源 mtime:", mt(tmp / "a.txt"), " 目标 mtime:", mt(tmp / "b.txt"))

    # 5. 不带 -p 覆盖已有目标
    tmp = case("no-preserve-overwrite-existing", ["a.txt", "b.txt"], None, setup_old_dest)
    print("   源 mtime:", mt(tmp / "a.txt"), " 目标 mtime:", mt(tmp / "b.txt"))

    # 6. 目录 mtime 是否被 -p 保住
    def setup_dir_mtime(tmp: Path):
        t = 1000000000
        os.utime(tmp / "dir1", (t, t))

    tmp = case("preserve-dir-mtime", ["-p", "-r", "dir1", "destdir"], None, setup_dir_mtime)
    print("   源目录 mtime:", mt(tmp / "dir1"), " 目标目录 mtime:", mt(tmp / "destdir/dir1"))

    tmp = case("no-preserve-dir-mtime", ["-r", "dir1", "destdir"], None, setup_dir_mtime)
    print("   源目录 mtime:", mt(tmp / "dir1"), " 目标目录 mtime:", mt(tmp / "destdir/dir1"))

    # 7. -a 对普通文件
    def setup_file_mtime(tmp: Path):
        t = 1000000000
        os.utime(tmp / "a.txt", (t, t))

    tmp = case("archive-file-mtime", ["-a", "a.txt", "copy.txt"], None, setup_file_mtime)
    print("   源 mtime:", mt(tmp / "a.txt"), " 目标 mtime:", mt(tmp / "copy.txt"))

    # 8. -i 应答字符串
    for answer in ("y\n", "Y\n", "yes\n", "n\n", "N\n", "no\n", "\n"):
        tmp = Path(tempfile.mkdtemp(prefix="cpprobe3i_", dir=str(DATA)))
        build(tmp)
        r = run(["-i", "a.txt", "b.txt"], tmp, answer)
        changed = (tmp / "b.txt").read_bytes() == b"hello cp\r\n"
        report.append({"name": f"interactive-answer-{answer.strip()!r}", "rc": r["rc"],
                       "out": r["out"], "err": r["err"], "overwritten": changed})
        print(f"   应答 {answer.strip()!r}: 覆盖={changed} rc={r['rc']}")

    # 9. 空文件覆盖
    def setup_empty(tmp: Path):
        (tmp / "empty.txt").write_bytes(b"")

    tmp = case("empty-src-overwrite", ["empty.txt", "b.txt"], None, setup_empty)
    print("   目标内容:", (tmp / "b.txt").read_bytes())

    # 10. -v 递归时子目录是否打印（合并模式下新建子目录）
    def setup_merge_sub(tmp: Path):
        (tmp / "destdir" / "dir1").mkdir()

    case("verbose-merge-new-subdir", ["-v", "-r", "dir1", "destdir"], None, setup_merge_sub)

    out_path = DATA / "probe_cp3.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n完整结果:", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
