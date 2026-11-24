"""补查 mv 的三个边角：目标尾斜杠、-v 输出的换行符、s29 的 GNU 对照。

_t1501/_t1502 查出 5 处差异后，这里再补三件事：

一、**目标带尾斜杠**：GNU 的 mv 把「目标以 / 结尾」当成「目标必须是已存在的目录」，
    目标不存在时报错；本实现用 Path(operand) 解析，pathlib 把尾斜杠吃掉，
    尾斜杠这个信号就丢了。这是 cp 那一轮查出的同一类缺陷（cp 的第 3 条），
    这里要确认 mv 有没有同款问题。

二、**-v 输出的换行符**：Windows 上 Python 文本流默认把 \n 翻译成 \r\n，
    所以 -v 打印的那一行是 CRLF。GNU 是 LF。
    ⇒ 「mv -v ... | grep -x "renamed ..."」这种比较会因 \r 对不上。

三、**用文件覆盖已存在的目录**（s29）：确认两边都是「搬进目录里」而不是报错。
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
DATA = ROOT / "AI" / "数据" / "mv_extra"

sys.path.insert(0, str(ROOT))

from w2l.commands.mv import build_parser, mv  # noqa: E402
from w2l.context import RunContext  # noqa: E402

GNU_MV = shutil.which("mv")
if GNU_MV is None:
    raise SystemExit("本机找不到 GNU mv")


def fixture(root: Path) -> None:
    (root / "a.txt").write_bytes(b"hello mv\r\nsecond line\r\n")
    (root / "b.txt").write_bytes(b"old content\r\n")
    (root / "dir1").mkdir()
    (root / "dir1" / "inner.txt").write_bytes(b"inner\r\n")


def dump_tree(root: Path) -> str:
    lines = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            lines.append(f"    {rel}/")
        else:
            data = path.read_bytes()
            lines.append(f"    {rel}  ({len(data)} 字节, sha={hashlib.sha256(data).hexdigest()[:10]})")
    if not lines:
        lines.append("    (空)")
    return "\n".join(lines)


def run_gnu(argv: list[str], cwd: Path) -> dict:
    proc = subprocess.run(
        [GNU_MV, *argv], cwd=str(cwd),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return {"rc": proc.returncode,
            "out": proc.stdout.decode("utf-8", "replace"),
            "err": proc.stderr.decode("utf-8", "replace").strip()}


def run_mine(argv: list[str], cwd: Path) -> dict:
    try:
        namespace = build_parser().parse_args(list(argv))
    except SystemExit as exc:
        return {"rc": 2, "out": "", "err": f"[argparse 退出 {exc.code}]"}
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(cwd=cwd, stdout=out, stderr=err, stdin=io.StringIO(""))
    code = mv(namespace, ctx)
    return {"rc": code, "out": out.getvalue(), "err": err.getvalue().strip()}


def one(title: str, argv: list[str]) -> None:
    base = Path(tempfile.mkdtemp(prefix="mvextra_", dir=str(DATA)))
    gnu_dir = base / "gnu"
    mine_dir = base / "mine"
    for target in (gnu_dir, mine_dir):
        target.mkdir()
        fixture(target)

    gnu = run_gnu(argv, gnu_dir)
    mine = run_mine(argv, mine_dir)

    print("=" * 72)
    print(f"### {title}")
    print(f"命令: mv {' '.join(argv)}")
    print(f"[GNU]     退出码 {gnu['rc']}  stdout={gnu['out']!r}  stderr={gnu['err']!r}")
    print("  落地:")
    print(dump_tree(gnu_dir))
    print(f"[本实现]  退出码 {mine['rc']}  stdout={mine['out']!r}  stderr={mine['err']!r}")
    print("  落地:")
    print(dump_tree(mine_dir))
    print()


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)

    print("#" * 72)
    print("# 一、目标带尾斜杠")
    print("#" * 72)
    one("目标是不存在的目录名 + 尾斜杠", ["a.txt", "newdir/"])
    one("目标是已存在的目录 + 尾斜杠", ["a.txt", "dir1/"])

    print("#" * 72)
    print("# 二、用文件覆盖已存在的目录")
    print("#" * 72)
    one("a.txt -> dir1（dir1 是已存在的目录）", ["a.txt", "dir1"])

    print("#" * 72)
    print("# 三、-v 输出的换行符")
    print("#" * 72)
    base = Path(tempfile.mkdtemp(prefix="mvextra_", dir=str(DATA)))
    mine_dir = base / "mine"
    mine_dir.mkdir()
    fixture(mine_dir)
    mine = run_mine(["-v", "a.txt", "a.renamed.txt"], mine_dir)
    print(f"本实现 stdout 的 repr: {mine['out']!r}")
    print(f"  含 CRLF: {chr(13) + chr(10) in mine['out']}")
    gnu_dir = base / "gnu"
    gnu_dir.mkdir()
    fixture(gnu_dir)
    gnu = run_gnu(["-v", "a.txt", "a.renamed.txt"], gnu_dir)
    print(f"GNU     stdout 的 repr: {gnu['out']!r}")
    print(f"  含 CRLF: {chr(13) + chr(10) in gnu['out']}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
