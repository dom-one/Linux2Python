"""采集教程 22 需要的每条命令的真实输出。

跑法跟核对器 AI/脚本/_t12_verify_teach.py 一致:
    cd <仓库根> && { <命令> ; } > 临时文件 2>&1
输出重定向到文件后按字节读回, 避免控制台把连续空格吃掉。

分组采:
- 项目自己的行为
- GNU coreutils 8.32 的同一批输入(对照)
- 多文件列宽分歧(用临时目录造样本)
- 目录操作数在单列/多列下的表现
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "AI", "产物", "wc_tutorial_commands.txt")
BASH = r"E:\software\Git\Git\bin\bash.exe"


def run_bash(command: str, cwd: str) -> tuple[int, bytes]:
    """按核对器的方式跑一条 bash 命令, 返回 (退出码, 合并后的原始字节)。"""
    handle, outpath = tempfile.mkstemp(suffix=".txt")
    os.close(handle)
    try:
        script = 'cd "%s" && { %s ; } > "%s" 2>&1' % (cwd, command, outpath)
        proc = subprocess.run([BASH, "-c", script], capture_output=True)
        with open(outpath, "rb") as fh:
            raw = fh.read()
        return proc.returncode, raw.replace(b"\r\n", b"\n")
    finally:
        for _ in range(3):
            try:
                os.remove(outpath)
                break
            except OSError:
                pass


def show(lines: list[str], tag: str, command: str, cwd: str) -> None:
    code, raw = run_bash(command, cwd)
    lines.append("-" * 70)
    lines.append("$ %s" % command)
    lines.append("  [退出码] %d" % code)
    lines.append("  [原始字节] %r" % raw)
    lines.append("  [按行]")
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if line:
            lines.append("    |%s|" % line)


def main() -> None:
    lines: list[str] = []
    base = tempfile.mkdtemp(prefix="wc_tut_")
    try:
        # 造两个样本文件: 一个含制表符(显示宽度远大于字节数), 一个极短
        with open(os.path.join(base, "wide.dat"), "wb") as fh:
            fh.write(b"a\tb\tc\n")
        with open(os.path.join(base, "small.dat"), "wb") as fh:
            fh.write(b"x\n")

        project_cmds = [
            ("默认三列", "printf 'hello world\\n' | python main.py wc"),
            ("单列 -l", "printf 'a b\\nc\\n' | python main.py wc -l"),
            ("五列全开", "printf 'a b\\nc\\n' | python main.py wc -lwc -m -L"),
            ("选项顺序不影响列序", "printf 'a b\\nc\\n' | python main.py wc -wlc"),
            ("末行无换行", "printf 'a\\nb' | python main.py wc -lwc"),
            ("空输入", "printf '' | python main.py wc -lwc"),
            ("片段夹控制字符", "printf 'a\\001b\\n' | python main.py wc -lw"),
            ("整段无可打印字符", "printf '\\001\\002\\003\\n' | python main.py wc -lw"),
            ("制表符宽度", "printf 'a\\tb\\tc\\n' | python main.py wc -L"),
            ("回车清零", "printf 'abc\\rdef\\n' | python main.py wc -L"),
            ("行内最大列", "printf 'abcdef\\rxy\\n' | python main.py wc -L"),
            ("UTF-8 中文", "printf '\\xe4\\xb8\\xad\\xe6\\x96\\x87\\x0a' | python main.py wc -lwc -m -L"),
            ("GBK 中文", "printf '\\xd6\\xd0\\xce\\xc4\\x0a' | python main.py wc -lwc -m -L"),
            ("多文件 + total", "python main.py wc w2l/errors.py w2l/context.py"),
            ("标准输入带名字", "printf 'x\\n' | python main.py wc -"),
            ("重复的 -", "printf 'x\\n' | python main.py wc -lw - -"),
            ("缺文件", "python main.py wc -l nonexistent.txt"),
            ("目录 + 缺文件", "python main.py wc -lwc w2l nonexistent.txt"),
            ("目录单列", "python main.py wc -l w2l"),
            ("目录两列", "python main.py wc -lL w2l"),
            ("高位字节 词数", "printf '\\x80\\x80\\x80' | python main.py wc -w"),
            ("高位字节 字符数", "printf '\\x80\\x80\\x80' | python main.py wc -m"),
            ("组合重音 字符数/宽度", "printf '\\x65\\xcc\\x81\\x0a' | python main.py wc -m -L"),
        ]
        for title, cmd in project_cmds:
            lines.append("=" * 70)
            lines.append("### 项目 · %s" % title)
            show(lines, "项目", cmd, ROOT)

        gnu_cmds = [
            ("默认区域设置 词数", "printf '\\x80\\x80\\x80' | wc -w"),
            ("C 区域设置 词数", "printf '\\x80\\x80\\x80' | env LC_ALL=C wc -w"),
            ("C.utf8 区域设置 词数", "printf '\\x80\\x80\\x80' | env LC_ALL=C.utf8 wc -w"),
            ("控制字符 词数", "printf '\\001\\002\\003\\n' | env LC_ALL=C wc -w"),
            ("组合重音 C", "printf '\\x65\\xcc\\x81\\x0a' | env LC_ALL=C wc -m -L"),
            ("组合重音 C.utf8", "printf '\\x65\\xcc\\x81\\x0a' | env LC_ALL=C.utf8 wc -m -L"),
            ("GBK 中文 C", "printf '\\xd6\\xd0\\xce\\xc4\\x0a' | env LC_ALL=C wc -m -L"),
            ("GBK 中文 C.utf8", "printf '\\xd6\\xd0\\xce\\xc4\\x0a' | env LC_ALL=C.utf8 wc -m -L"),
            ("GBK 中文 zh_CN", "printf '\\xd6\\xd0\\xce\\xc4\\x0a' | env LC_ALL=zh_CN wc -m -L"),
            ("UTF-8 中文 C.utf8", "printf '\\xe4\\xb8\\xad\\xe6\\x96\\x87\\x0a' | env LC_ALL=C.utf8 wc -m -L"),
            ("目录单列", "wc -l w2l"),
            ("目录两列", "wc -lL w2l"),
        ]
        for title, cmd in gnu_cmds:
            lines.append("=" * 70)
            lines.append("### GNU · %s" % title)
            show(lines, "GNU", cmd, ROOT)

        # 多文件列宽分歧: 在临时目录里造两个文件, 同一个命令分别跑 GNU 与项目
        lines.append("=" * 70)
        lines.append("### 多文件列宽分歧(临时目录里的两个文件)")
        for title, argv in [
            ("-lL 两个文件", "-lL wide.dat small.dat"),
            ("-lL 三个文件", "-lL wide.dat small.dat wide.dat"),
        ]:
            for who, cmd in [
                ("GNU ", "wc " + argv),
                ("项目", '"%s" wc %s' % (os.path.join(ROOT, "main.py"), argv)),
            ]:
                code, raw = run_bash(cmd, base)
                lines.append("  %s %s -> %r" % (who, argv, raw))

        # 项目在临时目录里怎么调: 记录一个可复制的写法
        lines.append("=" * 70)
        lines.append("### 临时目录里怎么调项目(相对路径写法)")
        cmd = 'm=$(pwd)/main.py && d=$(mktemp -d) && cd "$d" && printf \'a\\tb\\tc\\n\' > wide.dat && printf \'x\\n\' > small.dat && python "$m" wc -lL wide.dat small.dat'
        show(lines, "项目", cmd, ROOT)

        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        print("写入 %s" % OUT)
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
