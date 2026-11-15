"""探针：实测 GNU cp 8.32 在本机的行为，作为 cp 指令的对照基线。

只读探查，不改项目源码。产物落在 AI/数据/ 下。

重点探清：
- 目标存在/不存在、是不是目录时的落点规则
- -r / -a / -p / -i / -n / -u / -f / -v / -t / -T / --parents / -S 的确切行为
- 报错文案与退出码
- -v 与 -i 的输出格式
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "cp_probe"

CP = shutil.which("cp")
if CP is None:
    raise SystemExit("本机找不到 cp 可执行文件")

SAMPLE = "hello cp\nsecond line\n"


def build_fixture(tmp: Path) -> None:
    (tmp / "a.txt").write_text(SAMPLE, encoding="utf-8")
    (tmp / "b.txt").write_text("old content\n", encoding="utf-8")
    (tmp / "bin.dat").write_bytes(bytes(range(256)))
    (tmp / "empty.txt").write_text("", encoding="utf-8")
    d = tmp / "dir1"
    d.mkdir()
    (d / "inner.txt").write_text("inner\n", encoding="utf-8")
    (d / "sub").mkdir()
    (d / "sub" / "deep.txt").write_text("deep\n", encoding="utf-8")
    dst = tmp / "destdir"
    dst.mkdir()
    (dst / "b.txt").write_text("existing in destdir\n", encoding="utf-8")


def tree_state(root: Path) -> dict:
    """把目录内容拍成可比较的结构。"""
    state: dict = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            state[rel] = "DIR"
        else:
            data = path.read_bytes()
            state[rel] = f"FILE {len(data)}B {data[:40]!r}"
    return state


def run(argv: list[str], cwd: Path, stdin_text: str | None = None) -> dict:
    proc = subprocess.run(
        [CP, *argv],
        cwd=str(cwd),
        input=stdin_text.encode("utf-8") if stdin_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "argv": argv,
        "rc": proc.returncode,
        "out": proc.stdout.decode("utf-8", "replace"),
        "err": proc.stderr.decode("utf-8", "replace"),
    }


# 每组用例：一次性的独立沙箱，跑完记录目录状态
CASES: list[tuple[str, list[str], str | None]] = [
    # ---- 基本落点 ----
    ("file-to-new-file", ["a.txt", "copy.txt"], None),
    ("file-over-file", ["a.txt", "b.txt"], None),
    ("file-into-existing-dir", ["a.txt", "destdir"], None),
    ("file-into-existing-dir-slash", ["a.txt", "destdir/"], None),
    ("file-to-nonexistent-path", ["a.txt", "newdir"], None),
    ("binary-copy", ["bin.dat", "bin.copy"], None),
    ("empty-copy", ["empty.txt", "empty.copy"], None),
    # ---- 目录 ----
    ("dir-no-r", ["dir1", "destdir"], None),
    ("dir-r-into-existing", ["-r", "dir1", "destdir"], None),
    ("dir-r-trailing-slash", ["-r", "dir1/", "destdir"], None),
    ("dir-r-to-nonexistent", ["-r", "dir1", "newdest"], None),
    ("dir-r-trailing-slash-to-nonexistent", ["-r", "dir1/", "newdest"], None),
    ("dir-r-multi", ["-r", "dir1", "destdir", "a.txt"], None),
    ("dir-R-upper", ["-R", "dir1", "destdir"], None),
    ("dir-a", ["-a", "dir1", "destdir"], None),
    ("dir-a-trailing-slash", ["-a", "dir1/", "destdir"], None),
    # ---- 报错 ----
    ("missing-source", ["nosuch.txt", "copy.txt"], None),
    ("missing-source-dir", ["nosuchdir", "copy.txt"], None),
    ("missing-source-multi", ["a.txt", "nosuch.txt", "copy.txt"], None),
    ("no-operands", [], None),
    ("one-operand", ["a.txt"], None),
    ("dest-not-dir-multi-src", ["a.txt", "b.txt", "destdir"], None),
    ("dest-is-file-multi-src", ["a.txt", "b.txt", "copy.txt"], None),
    # ---- -v ----
    ("verbose-new", ["-v", "a.txt", "copy.txt"], None),
    ("verbose-existing", ["-v", "a.txt", "b.txt"], None),
    ("verbose-dir", ["-v", "-r", "dir1", "destdir"], None),
    ("verbose-2files", ["-v", "a.txt", "b.txt", "destdir"], None),
    # ---- -n ----
    ("noclobber-new", ["-n", "a.txt", "copy.txt"], None),
    ("noclobber-existing", ["-n", "a.txt", "b.txt"], None),
    ("noclobber-dir", ["-n", "-r", "dir1", "destdir"], None),
    # ---- -u ----
    ("update-newer-src", ["-u", "a.txt", "b.txt"], None),
    ("update-older-src", ["-u", "b.txt", "a.txt"], None),
    # ---- -i ----
    ("interactive-yes", ["-i", "a.txt", "b.txt"], "y\n"),
    ("interactive-no", ["-i", "a.txt", "b.txt"], "n\n"),
    ("interactive-new", ["-i", "a.txt", "copy.txt"], "y\n"),
    # ---- -f ----
    ("force-existing", ["-f", "a.txt", "b.txt"], None),
    # ---- -p / --preserve ----
    ("preserve", ["-p", "a.txt", "copy.txt"], None),
    ("preserve-mode", ["--preserve=mode,timestamps", "a.txt", "copy.txt"], None),
    ("no-preserve", ["--no-preserve", "a.txt", "copy.txt"], None),
    # ---- -t / -T ----
    ("target-directory", ["-t", "destdir", "a.txt"], None),
    ("target-directory-missing", ["-t", "nosuchdir", "a.txt"], None),
    ("target-directory-multi", ["-t", "destdir", "a.txt", "b.txt"], None),
    ("no-target-directory", ["-T", "a.txt", "destdir"], None),
    ("no-target-directory-dir", ["-T", "-r", "dir1", "destdir"], None),
    # ---- --parents ----
    ("parents", ["--parents", "dir1/inner.txt", "destdir"], None),
    ("parents-multi", ["--parents", "a.txt", "dir1/inner.txt", "destdir"], None),
    # ---- -S ----
    ("suffix", ["-S", ".bak", "a.txt", "b.txt"], None),
    # ---- --remove-destination ----
    ("remove-destination", ["--remove-destination", "a.txt", "b.txt"], None),
    # ---- 其它 ----
    ("recursive-empty-dir", ["-r", "emptydir", "destdir"], None),
    ("same-file", ["a.txt", "a.txt"], None),
    ("dash-dash", ["--", "a.txt", "copy.txt"], None),
    ("dot-source", ["./a.txt", "copy.txt"], None),
]


def main() -> int:
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)

    report: list[dict] = []

    for name, argv, stdin_text in CASES:
        tmp = Path(tempfile.mkdtemp(prefix="cpprobe_", dir=str(DATA)))
        build_fixture(tmp)
        (tmp / "emptydir").mkdir()

        before = tree_state(tmp)
        result = run(argv, tmp, stdin_text)
        after = tree_state(tmp)

        diff: dict = {}
        for key in sorted(set(before) | set(after)):
            if before.get(key) != after.get(key):
                diff[key] = {"before": before.get(key), "after": after.get(key)}

        report.append(
            {
                "name": name,
                "argv": argv,
                "stdin": stdin_text,
                "rc": result["rc"],
                "out": result["out"],
                "err": result["err"],
                "diff": diff,
            }
        )

    # 单独看 mtime 是否被 -p 保住
    mt = Path(tempfile.mkdtemp(prefix="cpmtime_", dir=str(DATA)))
    build_fixture(mt)
    os.utime(mt / "a.txt", (1000000000, 1000000000))
    src_stat = (mt / "a.txt").stat()
    run(["-p", "a.txt", "copy.txt"], mt)
    dst_stat = (mt / "copy.txt").stat()
    run(["a.txt", "copy2.txt"], mt)
    dst2_stat = (mt / "copy2.txt").stat()
    report.append(
        {
            "name": "mtime",
            "src_mtime": src_stat.st_mtime,
            "with_p_mtime": dst_stat.st_mtime,
            "without_p_mtime": dst2_stat.st_mtime,
            "src_mode": oct(src_stat.st_mode),
            "with_p_mode": oct(dst_stat.st_mode),
            "without_p_mode": oct(dst2_stat.st_mode),
        }
    )

    out_path = DATA / "probe_cp.json"
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for item in report:
        print("=" * 70)
        if item["name"] == "mtime":
            print("MTIME:", json.dumps(item, ensure_ascii=False))
            continue
        print("CASE:", item["name"], "| argv:", " ".join(item["argv"]))
        print("RC  :", item["rc"])
        if item["out"]:
            print("OUT :", repr(item["out"]))
        if item["err"]:
            print("ERR :", repr(item["err"]))
        for key, val in item["diff"].items():
            print(f"  DIFF {key}: {val['before']}  ->  {val['after']}")

    print("\n完整结果:", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
