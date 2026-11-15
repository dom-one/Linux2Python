"""探针 2：补 GNU cp 8.32 的边角语义。

覆盖第一轮没探到的：
- 目录合并（目标已存在同名目录）
- 源是目录、目标是已存在文件时的报错
- 多源里有一个失败时的退出码与续做
- 父目录不存在的报错
- -i 多个文件时的提示次数
- -t / --parents / -T 的组合
- 符号链接（MSYS 能不能造）
- 只读目标文件
- -p 对目录的 mtime
- -v 若干形态的确切文案
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "cp_probe"

CP = shutil.which("cp")
LN = shutil.which("ln")
if CP is None:
    raise SystemExit("本机找不到 cp 可执行文件")


def build_fixture(tmp: Path) -> None:
    (tmp / "a.txt").write_bytes(b"hello cp\r\n")
    (tmp / "b.txt").write_bytes(b"second file\r\n")
    d = tmp / "dir1"
    d.mkdir()
    (d / "inner.txt").write_bytes(b"inner\r\n")
    (d / "only-here.txt").write_bytes(b"only here\r\n")
    dst = tmp / "destdir"
    dst.mkdir()
    (dst / "b.txt").write_bytes(b"existing in destdir\r\n")


def tree_state(root: Path) -> dict:
    state: dict = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            state[rel] = "DIR"
        elif path.is_symlink():
            state[rel] = f"LINK -> {os.readlink(path)}"
        else:
            state[rel] = f"FILE {path.stat().st_size}B {path.read_bytes()[:30]!r}"
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


CASES: list[tuple[str, list[str], str | None]] = [
    # 目录合并
    ("merge-existing-dir", ["-r", "dir1", "destdir"], None),
    ("merge-existing-dir-v", ["-v", "-r", "dir1", "destdir"], None),
    ("merge-partial", ["-r", "dir1", "destdir"], None),  # 第二次跑，destdir/dir1 已存在
    # 目标是已存在文件，源是目录
    ("dir-src-dest-file", ["-r", "dir1", "a.txt"], None),
    ("dir-src-dest-file-nor", ["dir1", "a.txt"], None),
    # 多个源里有一个失败
    ("multi-one-missing", ["a.txt", "nosuch.txt", "destdir"], None),
    ("multi-one-missing-v", ["-v", "a.txt", "nosuch.txt", "destdir"], None),
    # 父目录不存在
    ("missing-parent", ["a.txt", "nodir/out.txt"], None),
    ("missing-parent-r", ["-r", "dir1", "nodir/out"], None),
    # -i 多个文件
    ("interactive-multi", ["-i", "a.txt", "b.txt", "destdir"], "y\ny\n"),
    ("interactive-multi-partial", ["-i", "a.txt", "b.txt", "destdir"], "y\nn\n"),
    # -t 组合
    ("target-dir-and-parents", ["-t", "destdir", "--parents", "dir1/inner.txt"], None),
    ("target-dir-missing-plus-parents", ["-t", "nosuchdir", "--parents", "a.txt"], None),
    # -T 多源
    ("no-target-dir-multi", ["-T", "a.txt", "b.txt"], None),
    # 只读目标
    ("readonly-dest", ["a.txt", "ro.txt"], None),
    # -p 目录 mtime
    ("preserve-dir-mtime", ["-p", "-r", "dir1", "destdir"], None),
    # -v 形态
    ("verbose-dir-to-new", ["-v", "-r", "dir1", "newdest"], None),
    ("verbose-into-dir-slash", ["-v", "a.txt", "destdir/"], None),
    ("verbose-noclobber", ["-v", "-n", "a.txt", "b.txt"], None),
    # --parents 绝对路径
    ("parents-absolute", ["--parents", "/etc/hostname", "destdir"], None),
    ("parents-dotdot", ["--parents", "../outside.txt", "destdir"], None),
    # 覆盖已存在只读文件（先创建）
    ("readonly-overwrite", ["a.txt", "ro2.txt"], None),
    # 源是已存在目录、目标同名已存在目录（不递归）
    ("dir-to-same-name", ["-r", "dir1", "dir1"], None),
    # -f 强制覆盖只读
    ("force-readonly", ["-f", "a.txt", "ro3.txt"], None),
]


def main() -> int:
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)

    report: list[dict] = []

    for name, argv, stdin_text in CASES:
        tmp = Path(tempfile.mkdtemp(prefix="cpprobe2_", dir=str(DATA)))
        build_fixture(tmp)
        # 只读目标文件
        (tmp / "ro.txt").write_bytes(b"readonly\r\n")
        (tmp / "ro.txt").chmod(stat.S_IREAD)
        (tmp / "ro2.txt").write_bytes(b"readonly2\r\n")
        (tmp / "ro2.txt").chmod(stat.S_IREAD)
        (tmp / "ro3.txt").write_bytes(b"readonly3\r\n")
        (tmp / "ro3.txt").chmod(stat.S_IREAD)
        # 造一个已存在的同名目录，测合并
        (tmp / "destdir" / "dir1").mkdir()
        (tmp / "destdir" / "dir1" / "inner.txt").write_bytes(b"OLD inner\r\n")
        (tmp / "destdir" / "dir1" / "stale.txt").write_bytes(b"stale\r\n")

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
                "rc": result["rc"],
                "out": result["out"],
                "err": result["err"],
                "diff": diff,
            }
        )

    # 符号链接能不能造
    link_info: dict = {}
    if LN:
        tmp = Path(tempfile.mkdtemp(prefix="cplink_", dir=str(DATA)))
        build_fixture(tmp)
        proc = subprocess.run(
            [LN, "-s", "a.txt", "link.txt"], cwd=str(tmp),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        link_info["ln_rc"] = proc.returncode
        link_info["ln_err"] = proc.stderr.decode("utf-8", "replace")
        link_info["is_link"] = (tmp / "link.txt").is_symlink()
        if link_info["is_link"]:
            for argv in (["link.txt", "copy.txt"], ["-a", "link.txt", "copy2.txt"], ["-P", "link.txt", "copy3.txt"]):
                r = run(argv, tmp)
                link_info[f"cp_{'_'.join(argv)}"] = {
                    "rc": r["rc"], "out": r["out"], "err": r["err"],
                }
                target = tmp / argv[-1]
                if target.exists():
                    link_info[f"cp_{'_'.join(argv)}"]["is_symlink"] = target.is_symlink()
    report.append({"name": "symlink", **link_info})

    out_path = DATA / "probe_cp2.json"
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for item in report:
        print("=" * 70)
        if item["name"] == "symlink":
            print("SYMLINK:", json.dumps(item, ensure_ascii=False))
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
