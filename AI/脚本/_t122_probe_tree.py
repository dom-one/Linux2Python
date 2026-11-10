"""tree 指令的取证脚本：把要写进文档的行为逐条实测一遍。

产出 AI/数据/_t122_tree_probe.txt，纯文本、可直接读。
只读项目源码 + 在临时目录造语料，不改项目文件。

本机没有 GNU tree（Git Bash 只带 cmd 的 tree.exe，格式完全不同），
所以行为基准来自上游源码 tree.c / list.c / unix.c / color.c 的逐行推演，
本脚本负责把本实现实际输出打出来，供人工核对。
"""

from __future__ import annotations

import io
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from w2l.commands.tree import build_parser, tree  # noqa: E402
from w2l.context import RunContext  # noqa: E402
from w2l.errors import UsageError  # noqa: E402

OUT = ROOT / "AI" / "数据" / "_t122_tree_probe.txt"

lines: list[str] = []


def emit(text: str = "") -> None:
    lines.append(text)


def run(argv, cwd):
    namespace = build_parser().parse_args(list(argv))
    out, err = io.StringIO(), io.StringIO()
    ctx = RunContext(cwd=Path(cwd), stdout=out, stderr=err, stdin=io.StringIO(""))
    try:
        code = tree(namespace, ctx)
    except UsageError as exc:
        code = f"UsageError({exc})"
    except SystemExit as exc:
        code = f"SystemExit({exc.code})"
    return code, out.getvalue(), err.getvalue()


def show(title: str, argv, cwd) -> None:
    code, out, err = run(argv, cwd)
    emit(f"===== {title} =====")
    emit(f"$ tree {' '.join(argv)}")
    emit(f"[退出码] {code}")
    emit("[标准输出]")
    for line in out.splitlines():
        emit(f"  |{line}")
    if err:
        emit("[标准错误]")
        for line in err.splitlines():
            emit(f"  !{line}")
    emit()


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="tree_probe_"))
    try:
        (base / "alpha").mkdir()
        (base / "alpha" / "one.txt").write_text("one\n", encoding="utf-8")
        (base / "alpha" / "two.txt").write_text("two\n", encoding="utf-8")
        (base / "beta").mkdir()
        (base / "beta" / "deep").mkdir()
        (base / "beta" / "deep" / "three.md").write_text("three\n", encoding="utf-8")
        (base / "root.txt").write_text("root\n", encoding="utf-8")
        (base / ".hidden").write_text("hidden\n", encoding="utf-8")
        (base / "zeta.log").write_text("z" * 2048, encoding="utf-8")
        (base / "empty").mkdir()

        emit("########## 环境事实 ##########")
        emit(f"st_dev（本目录）= {os.stat(base).st_dev}")
        emit(f"st_dev（系统盘）= {os.stat('C:/Windows').st_dev}")
        for probe in ("E:/", "D:/"):
            if os.path.exists(probe):
                try:
                    emit(f"st_dev（{probe}）= {os.stat(probe).st_dev}")
                except OSError as exc:
                    emit(f"st_dev（{probe}）= 取不到（{exc}）")
        emit(f"st_ino（本目录）= {os.stat(base).st_ino}")
        try:
            os.symlink(base / "alpha", base / "link_to_alpha")
            emit("符号链接：可以创建")
        except OSError as exc:
            emit(f"符号链接：不能创建（{exc}）")
        emit()

        emit("########## 基准输出 ##########")
        show("默认", ["."], base)
        show("带操作数", ["alpha"], base)
        show("多个操作数", ["alpha", "beta"], base)
        show("隐藏文件 -a", ["-a", "."], base)
        show("只列目录 -d", ["-d", "."], base)
        show("完整路径 -f", ["-f", "."], base)
        show("限制层数 -L 1", ["-L", "1", "."], base)
        show("限制层数 -L 2", ["-L", "2", "."], base)
        show("不画缩进 -i", ["-i", "."], base)
        show("ASCII 画线", ["--charset=ascii", "."], base)
        show("目录在前 --dirsfirst", ["--dirsfirst", "."], base)
        show("反序 -r", ["-r", "."], base)
        show("忽略 -I", ["-I", "*.txt", "."], base)
        show("只列匹配 -P", ["-P", "*.txt", "."], base)
        show("大小 -s", ["-s", "."], base)
        show("人-readable -h", ["-h", "."], base)
        show("权限 -p", ["-p", "."], base)
        show("修改时间 -D", ["-D", "."], base)
        show("类型标记 -F", ["-F", "."], base)
        show("不打统计 --noreport", ["--noreport", "."], base)
        show("空目录", ["empty"], base)
        show("不存在的路径", ["nope"], base)
        show("文件当操作数", ["root.txt"], base)
        show("非法层数 -L 0", ["-L", "0", "."], base)
        show("非法字符集", ["--charset=gbk", "."], base)
        show("带元信息", ["-p", "-s", "-D", "."], base)
    finally:
        shutil.rmtree(base, ignore_errors=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已写出 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
