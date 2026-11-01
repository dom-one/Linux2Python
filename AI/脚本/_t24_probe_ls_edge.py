"""核对 ls 的边界行为，把真实输出打印出来供写教程时引用。

只读为主：仅在 AI/数据/ 下建临时目录，不碰仓库源码与 teach/。
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "AI" / "数据"


def run(argv: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """跑一次 main.py ls，返回 (退出码, stdout, stderr)。"""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "ls", *argv],
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def show(title: str, argv: list[str], cwd: Path | None = None) -> None:
    code, out, err = run(argv, cwd)
    print("=== %s ===" % title)
    print("命令: python main.py ls %s" % " ".join(argv))
    print("退出码: %d" % code)
    print("stdout: %r" % out)
    print("stderr: %r" % err)
    print()


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="_t24_ls_", dir=str(DATA)))

    empty = tmp / "empty"
    empty.mkdir()
    (tmp / "plain.txt").write_text("hello\n", encoding="utf-8")
    (tmp / ".hidden").write_text("h\n", encoding="utf-8")
    sub = tmp / "sub"
    sub.mkdir()
    (sub / "deep.txt").write_text("deep\n", encoding="utf-8")

    show("空目录（无结果）", [str(empty)])
    show("不存在的路径", [str(tmp / "不存在")])
    show("多个操作数：文件 + 目录", [str(tmp / "plain.txt"), str(sub)])
    show("多操作数：目录 + 目录", [str(sub), str(empty)])
    show("-a 空目录", ["-a", str(empty)])
    show("默认列当前目录（cwd=tmp）", [], cwd=tmp)
    show("-d 列目录本身", ["-d", str(sub)])
    show("-R 递归", ["-R", str(sub)])
    show("文件操作数按原样打印", [str(tmp / "plain.txt")])
    show("-F 类型标记", ["-F", str(tmp)])

    # 清理临时目录
    for path in sorted(tmp.rglob("*"), reverse=True):
        if path.is_dir():
            os.rmdir(path)
        else:
            path.unlink()
    os.rmdir(tmp)
    print("临时目录已清理: %s" % tmp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
