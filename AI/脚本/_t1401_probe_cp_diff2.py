"""cp 指令的第二轮差分：专打开发任务那 57 组没覆盖到的角落。

开发任务在 tick #11 落地 cp 时留了 AI/脚本/_t410_diff_cp.py，57 组用例全绿。
本脚本补的是那一轮没问的问题：

1. `--preserve` 裸写时 argparse 会不会把下一个操作数吃掉
2. `--preserve` / `--no-preserve` 的组合与交集
3. `--suffix` 与 `--remove-destination` 的先后
4. 目标路径带尾部斜杠（GNU 当目录，本实现当文件？）
5. `-i` 与 `-n` 同时给、`-i` 读到 EOF
6. `--parents` 配绝对路径、配 `-t`、配 `-T`
7. Windows 目录联接（junction）落在被拷目录里时，两边怎么处理
8. 目标只读时的 `-f` 与不加 `-f`
9. `--` 分隔符、选项顺序（`-n` 在 `-i` 前 / 在 `-i` 后）

每组用例在两个一模一样的沙箱里各跑一次：
- 沙箱 A 跑 GNU /usr/bin/cp（coreutils 8.32）
- 沙箱 B 跑本实现 `python main.py cp`

比四样：成功与否、有无报错、落地后的目录树（路径 + 内容摘要）、
verbose 的「'src' -> 'dst'」对序列。报错文案两边语言不同，只比「有没有」。

用法:
    python AI/脚本/_t1401_probe_cp_diff2.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "cp_probe2"
MAIN = ROOT / "main.py"

GNU_CP = shutil.which("cp")
if GNU_CP is None:
    raise SystemExit("本机找不到 GNU cp")

PAIR_RE = re.compile(r"'([^']*)' -> '([^']*)'")
_FIXED_MTIME = 1_000_000_000
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


# ---------- 沙箱 ----------


def build_fixture(root: Path) -> None:
    """两个沙箱必须一模一样，mtime 才能跨沙箱比。"""
    (root / "a.txt").write_bytes(b"hello cp\r\nsecond line\r\n")
    (root / "b.txt").write_bytes(b"old content\r\n")
    (root / "bin.dat").write_bytes(bytes(range(256)))
    d = root / "dir1"
    d.mkdir()
    (d / "inner.txt").write_bytes(b"inner\r\n")
    sub = d / "sub"
    sub.mkdir()
    (sub / "deep.txt").write_bytes(b"deep\r\n")
    dest = root / "destdir"
    dest.mkdir()
    (dest / "b.txt").write_bytes(b"existing in destdir\r\n")
    for path in sorted(root.rglob("*"), reverse=True):
        os.utime(path, (_FIXED_MTIME, _FIXED_MTIME))
    os.utime(root, (_FIXED_MTIME, _FIXED_MTIME))


def make_junction(link: Path, target: Path) -> bool:
    """用 cmd 的 mklink /J 建目录联接（不需要管理员权限）。"""
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc.returncode == 0


def tree_state(root: Path) -> dict:
    """不跟随符号链接也不钻联接地扫一遍树。"""
    state: dict[str, str] = {}

    def walk(current: Path) -> None:
        try:
            entries = sorted(os.scandir(current), key=lambda e: e.name)
        except OSError:
            return
        for entry in entries:
            path = Path(entry.path)
            rel = path.relative_to(root).as_posix()
            if entry.is_symlink():
                state[rel] = "LINK"
                continue
            try:
                attrs = entry.stat(follow_symlinks=False).st_file_attributes
            except (OSError, AttributeError):
                attrs = 0
            if attrs & _REPARSE:
                state[rel] = "JUNC"
                continue
            if entry.is_dir(follow_symlinks=False):
                state[rel] = "DIR"
                walk(path)
            else:
                try:
                    data = path.read_bytes()
                except OSError:
                    state[rel] = "FILE ?"
                    continue
                state[rel] = f"FILE {len(data)} {hashlib.sha256(data).hexdigest()[:16]}"

    walk(root)
    return state


def mtime_state(root: Path) -> dict:
    """mtime 归两类：搬过来的算 preserved，复制时刻算 fresh。"""
    state: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        try:
            stamp = path.stat().st_mtime
        except OSError:
            state[rel] = "missing"
            continue
        state[rel] = "preserved" if abs(stamp - _FIXED_MTIME) < 0.5 else "fresh"
    return state


# ---------- 跑 ----------

_run = subprocess.run


def _kill_tree(proc: subprocess.Popen) -> None:
    subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run_gnu(argv: list[str], cwd: Path, stdin_text: str | None, timeout: int = 30) -> dict:
    try:
        proc = _run(
            [GNU_CP, *argv],
            cwd=str(cwd),
            input=stdin_text.encode() if stdin_text is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"rc": -9, "out": "", "err": "<timeout>", "timeout": True}
    return {
        "rc": proc.returncode,
        "out": proc.stdout.decode("utf-8", "replace"),
        "err": proc.stderr.decode("utf-8", "replace"),
        "timeout": False,
    }


def run_mine(argv: list[str], cwd: Path, stdin_text: str | None, timeout: int = 30) -> dict:
    try:
        proc = _run(
            [sys.executable, str(MAIN), "cp", *argv],
            cwd=str(cwd),
            input=stdin_text.encode() if stdin_text is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"rc": -9, "out": "", "err": "<timeout>", "timeout": True}
    return {
        "rc": proc.returncode,
        "out": proc.stdout.decode("utf-8", "replace"),
        "err": proc.stderr.decode("utf-8", "replace"),
        "timeout": False,
    }


# ---------- 用例 ----------


def setup_plain(root: Path) -> None:
    return None


def setup_readonly_target(root: Path) -> None:
    (root / "ro.txt").write_bytes(b"read only\r\n")
    (root / "ro.txt").chmod(stat.S_IREAD)
    (root / "rodir").mkdir()
    (root / "rodir" / "keep.txt").write_bytes(b"keep\r\n")


def setup_junction(root: Path) -> None:
    """src/real/file.txt，src/link -> src/real（目录联接）。"""
    src = root / "src"
    (src / "real").mkdir(parents=True)
    (src / "real" / "file.txt").write_bytes(b"real content\r\n")
    if not make_junction(src / "link", src / "real"):
        raise RuntimeError("mklink /J 失败")


def setup_loop_junction(root: Path) -> None:
    """src/file.txt，src/loop -> src（自引用联接）。"""
    src = root / "src"
    src.mkdir()
    (src / "file.txt").write_bytes(b"loop content\r\n")
    if not make_junction(src / "loop", src):
        raise RuntimeError("mklink /J 失败")


CASES: list[tuple[str, list[str], str | None, str, bool]] = [
    # 名字, argv, stdin, 额外布置, 是否比对 mtime
    ("preserve-bare-then-operand", ["--preserve", "a.txt", "copy.txt"], None, "plain", False),
    ("preserve-bare-at-end", ["a.txt", "copy.txt", "--preserve"], None, "plain", True),
    ("preserve-eq-all", ["--preserve=all", "a.txt", "copy.txt"], None, "plain", True),
    ("preserve-eq-mode", ["--preserve=mode", "a.txt", "copy.txt"], None, "plain", True),
    (
        "preserve-twice-union",
        ["--preserve=mode", "--preserve=timestamps", "a.txt", "copy.txt"],
        None,
        "plain",
        True,
    ),
    ("preserve-all-then-no-preserve", ["--preserve=all", "--no-preserve=timestamps", "a.txt", "copy.txt"], None, "plain", True),
    ("p-then-no-preserve-mode", ["-p", "--no-preserve=mode", "a.txt", "copy.txt"], None, "plain", True),
    ("no-preserve-invalid", ["--no-preserve=bogus", "a.txt", "copy.txt"], None, "plain", False),
    ("preserve-ownership-only", ["--preserve=ownership", "a.txt", "copy.txt"], None, "plain", False),
    ("noclobber-then-interactive", ["-n", "-i", "a.txt", "b.txt"], "y\n", "plain", False),
    ("interactive-then-noclobber", ["-i", "-n", "a.txt", "b.txt"], "y\n", "plain", False),
    ("interactive-eof", ["-i", "a.txt", "b.txt"], "", "plain", False),
    ("interactive-yes-word", ["-i", "a.txt", "b.txt"], "yes\n", "plain", False),
    ("interactive-garbage", ["-i", "a.txt", "b.txt"], "maybe\n", "plain", False),
    ("suffix-and-remove-destination", ["-S", ".bak", "--remove-destination", "a.txt", "b.txt"], None, "plain", False),
    ("suffix-and-force", ["-S", ".bak", "-f", "a.txt", "b.txt"], None, "plain", False),
    ("remove-destination-and-suffix", ["--remove-destination", "-S", ".bak", "a.txt", "b.txt"], None, "plain", False),
    ("dest-trailing-slash-new", ["a.txt", "newdir/"], None, "plain", False),
    ("dest-trailing-slash-existing", ["a.txt", "destdir/"], None, "plain", False),
    ("parents-absolute", ["--parents", "ABS:a.txt", "destdir"], None, "plain", False),
    ("parents-with-target-dir", ["-t", "destdir", "--parents", "dir1/inner.txt"], None, "plain", False),
    ("parents-with-no-target-dir", ["-T", "--parents", "a.txt", "destdir"], None, "plain", False),
    ("parents-verbose", ["-v", "--parents", "dir1/inner.txt", "destdir"], None, "plain", False),
    ("parents-dot-slash", ["--parents", "./a.txt", "destdir"], None, "plain", False),
    ("double-dash", ["--", "a.txt", "copy.txt"], None, "plain", False),
    ("update-equal-mtime", ["-u", "a.txt", "b.txt"], None, "plain", False),
    ("readonly-target-no-force", ["a.txt", "ro.txt"], None, "readonly", False),
    ("readonly-target-force", ["-f", "a.txt", "ro.txt"], None, "readonly", False),
    ("readonly-dest-dir", ["-f", "a.txt", "rodir"], None, "readonly", False),
    ("dir-into-itself", ["-r", "dir1", "dir1"], None, "plain", False),
    ("dir-into-own-subdir", ["-r", "dir1", "dir1/sub"], None, "plain", False),
    ("same-file-different-case", ["a.txt", "A.TXT"], None, "plain", False),
    ("junction-in-tree", ["-r", "src", "destdir"], None, "junction", False),
    ("junction-in-tree-archive", ["-a", "src", "destdir"], None, "junction", False),
    ("loop-junction", ["-r", "src", "destdir"], None, "loop_junction", False),
    ("verbose-dir-trailing-slash", ["-v", "-r", "dir1/", "destdir"], None, "plain", False),
    ("verbose-dir-trailing-slash-file", ["-v", "a.txt", "destdir/"], None, "plain", False),
]


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    sandbox_root = Path(tempfile.mkdtemp(prefix="cpdiff2_", dir=str(DATA)))

    report: list[dict] = []
    mismatches = 0

    for index, (name, argv, stdin_text, setup, check_mtime) in enumerate(CASES):
        base = sandbox_root / f"case{index:03d}"
        base.mkdir(parents=True)
        gnu_dir = base / "gnu"
        mine_dir = base / "mine"
        for target in (gnu_dir, mine_dir):
            target.mkdir()
            build_fixture(target)
            if setup == "readonly":
                setup_readonly_target(target)
            elif setup == "junction":
                setup_junction(target)
            elif setup == "loop_junction":
                setup_loop_junction(target)

        real_argv = [str(gnu_dir / a[4:]) if a.startswith("ABS:") else a for a in argv]

        gnu = run_gnu(real_argv, gnu_dir, stdin_text)
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
                f"有无报错不同: GNU err={gnu['err'].strip()[:160]!r} 本实现 err={mine['err'].strip()[:160]!r}"
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
                "setup": setup,
                "gnu": gnu,
                "mine": mine,
                "problems": problems,
            }
        )

        flag = "OK  " if not problems else "DIFF"
        print(f"[{flag}] {name}  argv={' '.join(argv)}")
        for problem in problems:
            print("       -", problem)

    out_path = DATA / "diff_cp2.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 70)
    print(f"总用例 {len(CASES)}，不一致 {mismatches}")
    print("详细结果:", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
