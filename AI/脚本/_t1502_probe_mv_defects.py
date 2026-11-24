"""逐条坐实 mv 的 5 处与 GNU 的差异（_t1501 差分脚本查出的）。

_1501 用 52 组用例对拍，查出 13 处不一致。这里逐条把「现象、两边原文、
落地树、退出码」摊开，确认哪些是真缺陷、哪些是 GNU 独有能力。

要坐实的五条：
1. -i 的应答解析：GNU 只看这一行的**第一个字符**是不是 y/Y；
   本实现是 strip().lower() 之后整串精确匹配 "y"/"yes"。
   ⇒ "yeah" / "yes please" 分叉，" y" / "\\ty" 反向分叉。
   （w2l/commands/rm.py 的 confirm() 已经是对的，mv.py 与 cp.py 用错了。）
2. --backup 带取值：GNU 的 --backup=CONTROL 认 numbered/none/simple，
   本实现的 -b 是 store_true，argparse 直接报 "ignored explicit argument"。
3. --backup 与 --no-clobber 互斥：GNU 规划阶段就报错退 1，本实现没有这项检查。
4. --no-clobber 与 --force 互斥且「后给的那个赢」：
   `-n -f` 在 GNU 是 -f 赢（照搬），本实现是 -n 赢（静默跳过）。
5. 备份目标已存在且是个目录：GNU 报 "cannot backup ... Is a directory" 退 1 且不动任何东西；
   本实现的 _backup() 先 _remove_path() 把那个目录整个 rmtree 掉再改名，
   ⇒ 用户原有的备份目录连同内容被删掉了。
"""

from __future__ import annotations

import hashlib
import io
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "mv_defects"

sys.path.insert(0, str(ROOT))

from w2l.commands.mv import build_parser, mv  # noqa: E402
from w2l.context import RunContext  # noqa: E402

GNU_MV = shutil.which("mv")
if GNU_MV is None:
    raise SystemExit("本机找不到 GNU mv")


def fixture(root: Path) -> None:
    (root / "a.txt").write_bytes(b"hello mv\r\nsecond line\r\n")
    (root / "b.txt").write_bytes(b"old content\r\n")


def dump_tree(root: Path) -> str:
    lines = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            lines.append(f"    {rel}/  (目录)")
        else:
            data = path.read_bytes()
            lines.append(
                f"    {rel}  ({len(data)} 字节, sha256={hashlib.sha256(data).hexdigest()[:12]})"
            )
    if not lines:
        lines.append("    (空)")
    return "\n".join(lines)


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
        return {"rc": 2, "out": "", "err": f"[argparse 以退出码 {exc.code} 结束]"}
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(
        cwd=cwd,
        stdout=out,
        stderr=err,
        stdin=io.StringIO(stdin_text) if stdin_text is not None else io.StringIO(""),
    )
    code = mv(namespace, ctx)
    return {"rc": code, "out": out.getvalue(), "err": err.getvalue()}


def one(title: str, argv: list[str], stdin_text: str | None = None, extra=None) -> None:
    extra = extra or (lambda root: None)
    base = Path(tempfile.mkdtemp(prefix="mvdef_", dir=str(DATA)))
    gnu_dir = base / "gnu"
    mine_dir = base / "mine"
    for target in (gnu_dir, mine_dir):
        target.mkdir()
        fixture(target)
        extra(target)

    gnu = run_gnu(argv, gnu_dir, stdin_text)
    mine = run_mine(argv, mine_dir, stdin_text)

    print("=" * 72)
    print(f"### {title}")
    print(f"命令: mv {' '.join(argv)}" + (f"   <<< 应答 {stdin_text!r}" if stdin_text else ""))
    print("-" * 72)
    print(f"[GNU]        退出码 {gnu['rc']}")
    print(f"  stdout: {gnu['out']!r}")
    print(f"  stderr: {gnu['err'].strip()!r}")
    print("  落地:")
    print(dump_tree(gnu_dir))
    print(f"[本实现]     退出码 {mine['rc']}")
    print(f"  stdout: {mine['out']!r}")
    print(f"  stderr: {mine['err'].strip()!r}")
    print("  落地:")
    print(dump_tree(mine_dir))
    print()


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)

    # ---------- 差异一：-i 的应答解析 ----------
    print("#" * 72)
    print("# 差异一：-i 的应答解析（GNU 看首字符，本实现看整串精确匹配）")
    print("#" * 72)
    for answer in ["y\n", "yeah\n", "yes please\n", " y\n", "\ty\n", "Y\n", "yes\n"]:
        one(f"应答 {answer!r}", ["-i", "a.txt", "b.txt"], answer)

    # ---------- 差异二：--backup 带取值 ----------
    print("#" * 72)
    print("# 差异二：--backup=CONTROL（GNU 认 numbered/none/simple）")
    print("#" * 72)
    for value in ["simple", "numbered", "none"]:
        one(f"--backup={value}", [f"--backup={value}", "a.txt", "b.txt"])

    # ---------- 差异三：--backup 与 --no-clobber 互斥 ----------
    print("#" * 72)
    print("# 差异三：--backup 与 --no-clobber 互斥")
    print("#" * 72)
    one("-b -n 一起给", ["-b", "-n", "a.txt", "b.txt"])
    one("-n -b 一起给", ["-n", "-b", "a.txt", "b.txt"])
    one("-b -n 但缺操作数（看报错次序）", ["-b", "-n", "a.txt"])

    # ---------- 差异四：--no-clobber 与 --force 互斥，后给的赢 ----------
    print("#" * 72)
    print("# 差异四：-n 与 -f 一起给（GNU：后给的那个赢）")
    print("#" * 72)
    one("-n -f（GNU 应为 -f 赢：照搬）", ["-n", "-f", "a.txt", "b.txt"])
    one("-f -n（GNU 应为 -n 赢：跳过）", ["-f", "-n", "a.txt", "b.txt"])

    # ---------- 差异五：备份目标已存在且是目录 ----------
    print("#" * 72)
    print("# 差异五：备份目标已存在且是个目录（GNU 报错，本实现把目录删了）")
    print("#" * 72)

    def make_backup_dir(root: Path) -> None:
        backup = root / "b.txt~"
        backup.mkdir()
        (backup / "inside.txt").write_bytes(b"inside backup\r\n")

    one("-b 且 b.txt~ 已存在是个目录", ["-b", "a.txt", "b.txt"], None, make_backup_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
