#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真跑教程里的每一条命令，把实际输出录下来，供誊进 markdown。

为什么要这一步：
预期输出凭印象写必错。这里把命令逐条跑一遍、输出落盘，
誊进文档时直接照抄录下来的结果。

用法：python AI/脚本/_t1011_capture_sed_tut.py
产物：AI/数据/sed_tut_capture.txt
"""
from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "sed_tut_capture.txt"
BASH = r"E:\software\Git\Git\bin\bash.exe"

sys.path.insert(0, str(ROOT))
from w2l.commands.sed import run_sed  # noqa: E402

FIX = "AI/数据/sed_demo"

# (编号, 说明, 命令 argv)
CASES: list[tuple[str, list[str]]] = [
    ("01 替换第一个匹配", ["s/a/b/", f"{FIX}/a.txt"]),
    ("02 全局替换", ["s/a/b/g", f"{FIX}/a.txt"]),
    ("03 第 N 个匹配", ["s/a/A/2", f"{FIX}/a.txt"]),
    ("04 忽略大小写", ["s/A/alpha/I", f"{FIX}/a.txt"]),
    ("05 -n 只打匹配行", ["-n", r"\|bravo\|p", f"{FIX}/a.txt"]),
    ("06 行号地址", ["-n", "2p", f"{FIX}/a.txt"]),
    ("07 范围地址", ["-n", "2,3p", f"{FIX}/a.txt"]),
    ("08 范围到文件末", ["-n", r"\|bravo\|,/echo/p", f"{FIX}/a.txt"]),
    ("09 起点不命中", ["-n", r"\|zzz\|,/echo/p", f"{FIX}/a.txt"]),
    ("10 相对范围 +N", ["-n", "2,+2p", f"{FIX}/a.txt"]),
    ("11 删除行", [r"\|bravo\|d", f"{FIX}/a.txt"]),
    ("12 行号与内容", ["-n", "=;p", f"{FIX}/a.txt"]),
    ("13 BRE 分组反向引用", [r"s/\(a\)\(l\)/\2\1/", f"{FIX}/a.txt"]),
    ("14 ERE 分组反向引用", ["-r", r"s/(a)(l)/\2\1/", f"{FIX}/a.txt"]),
    ("15 BRE 里裸括号是字面量", ["s/(a)/X/", f"{FIX}/a.txt"]),
    ("16 BRE 里裸竖线是字面量", ["s/a|o/X/", f"{FIX}/a.txt"]),
    ("17 转写 y", ["y/abc/xyz/", f"{FIX}/a.txt"]),
    ("18 追加文本", [r"1a\inserted", f"{FIX}/a.txt"]),
    ("19 插入文本", [r"1i\prepended", f"{FIX}/a.txt"]),
    ("20 替换文本", [r"1c\changed", f"{FIX}/a.txt"]),
    ("21 -n 下 a 照样输出", ["-n", r"1a\APPENDED", f"{FIX}/a.txt"]),
    ("22 大小写修饰 U", [r"s/a/\Uab/", f"{FIX}/a.txt"]),
    ("23 & 是整行匹配", ["s/a/&b/", f"{FIX}/a.txt"]),
    ("24 N 拼接下一行", ["-n", r"N;s/\n/-/;p", f"{FIX}/a.txt"]),
    ("25 标签跳转", ["-n", r"\|bravo\|/{s/a/X/;t end}\np\n:end", f"{FIX}/a.txt"]),
    ("26 无条件跳转", ["-n", r"\|bravo\|/b end\np\n:end", f"{FIX}/a.txt"]),
    ("27 多文件默认拼流", ["-n", "=", f"{FIX}/m1.txt", f"{FIX}/m2.txt"]),
    ("28 -s 各算各的行号", ["-n", "-s", "=", f"{FIX}/m1.txt", f"{FIX}/m2.txt"]),
    ("29 多条 -e", ["-e", "s/a/b/", "-e", "s/b/c/", f"{FIX}/a.txt"]),
    ("30 末行无换行不补", ["s/no/NOT/", f"{FIX}/nonl.txt"]),
    ("31 CRLF 文本模式去 CR", ["s/one/1/", f"{FIX}/crlf.txt"]),
    ("32 -b 保留 CR", ["-b", "s/one/1/", f"{FIX}/crlf.txt"]),
    ("33 POSIX 字符类", ["s/[[:alpha:]]/Y/g", f"{FIX}/a.txt"]),
    ("34 空行地址", ["-n", r"\|^$|p", f"{FIX}/blank.txt"]),
    ("35 q 指定退出码", ["q3", f"{FIX}/a.txt"]),
    ("36 未知指令", ["nosuchcmd", f"{FIX}/a.txt"]),
    ("37 不支持的指令 h", ["h", f"{FIX}/a.txt"]),
    ("38 脚本没闭合", ["s/a/b", f"{FIX}/a.txt"]),
    ("39 匹配序号为 0", ["s/a/b/0", f"{FIX}/a.txt"]),
    ("40 y 两串长度不同", ["y/abc/xy/", f"{FIX}/a.txt"]),
    ("41 文件不存在", ["s/a/b/", f"{FIX}/nosuch.txt"]),
    ("42 目录当文件用", ["s/a/b/", f"{FIX}"]),
    ("43 缺少脚本", []),
]

# 命令行整条跑的（走 main.py，验证真实入口）
CLI_CASES: list[tuple[str, list[str]]] = [
    ("C1 竖线地址", ["sed", "-n", r"\|bravo\|p", f"{FIX}/a.txt"]),
    ("C2 替换", ["sed", "s/a/b/g", f"{FIX}/a.txt"]),
    ("C3 -i 原地改", ["sed", "-i", "s/a/A/g", f"{FIX}/ip.txt"]),
    ("C4 GBK 文件", ["sed", r"s/一/ONE/", f"{FIX}/gbk.txt"]),
    ("C5 读标准输入", ["sed", "s/a/b/"]),
]


def capture_cli(argv: list[str], stdin: bytes = b"") -> tuple[int, bytes, bytes]:
    proc = subprocess.run(
        [sys.executable, "main.py", *argv],
        input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=str(ROOT),
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    out: list[str] = []

    out.append("=" * 70)
    out.append("一、run_sed 层的调用（走 w2l.commands.sed.run_sed）")
    out.append("=" * 70)
    for label, argv in CASES:
        try:
            code, so, se = run_sed(argv, cwd=ROOT)
            out.append(f"### {label}")
            out.append(f"argv={argv!r}")
            out.append(f"exit={code}")
            out.append(f"stdout={so!r}")
            out.append(f"stderr={se!r}")
            out.append("")
        except Exception as exc:  # noqa: BLE001
            out.append(f"### {label}")
            out.append(f"argv={argv!r}")
            out.append(f"异常: {type(exc).__name__}: {exc}")
            out.append("")

    out.append("=" * 70)
    out.append("二、走 main.py 真实入口")
    out.append("=" * 70)
    # -i 需要目标文件，先造一个
    ip = ROOT / FIX / "ip.txt"
    ip.write_bytes(b"alpha\nbravo\ncharlie\ndelta\necho\n")
    for label, argv in CLI_CASES:
        stdin = b"alpha\nbravo\n" if "标准输入" in label else b""
        code, so, se = capture_cli(argv, stdin)
        out.append(f"### {label}")
        out.append(f"argv={argv!r}")
        out.append(f"exit={code}")
        out.append(f"stdout={so!r}")
        out.append(f"stderr={se!r}")
        if label.startswith("C3"):
            out.append(f"文件内容={ip.read_bytes()!r}")
        out.append("")

    out.append("=" * 70)
    out.append("三、GNU sed 4.9 的对照（同一批脚本）")
    out.append("=" * 70)
    sed_exe = r"E:\software\Git\Git\bin\sed.exe"
    for label, argv in CASES[:36]:
        if not argv:
            continue
        # 只取脚本部分：argv[0] 是脚本（若给了 -n/-r 等选项则跳过）
        script = argv[0]
        opts = []
        idx = 0
        while idx < len(argv) and argv[idx].startswith("-"):
            opts.append(argv[idx])
            idx += 1
        if idx >= len(argv) or argv[idx].startswith("-"):
            continue
        script = argv[idx]
        files = argv[idx + 1:]
        tmp = ROOT / "AI" / "数据" / "sed_demo"
        script_file = tmp / "_cap.sed"
        script_file.write_text(script.replace("\n", "\n"), encoding="utf-8")
        try:
            proc = subprocess.run(
                [sed_exe, *opts, "-f", "_cap.sed", *files],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(ROOT),
            )
            out.append(f"### {label}")
            out.append(f"script={script!r} opts={opts!r}")
            out.append(f"exit={proc.returncode}")
            out.append(f"stdout={proc.stdout!r}")
            out.append(f"stderr={proc.stderr.decode('utf-8', 'replace').strip()!r}")
            out.append("")
        except Exception as exc:  # noqa: BLE001
            out.append(f"### {label}  GNU 侧失败: {exc}")
            out.append("")
    script_file = ROOT / "AI" / "数据" / "sed_demo" / "_cap.sed"
    if script_file.exists():
        script_file.unlink()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out), encoding="utf-8", newline="\n")
    print(f"[result] 已写入 {OUT}")
    print(f"[result] 共 {len(CASES) + len(CLI_CASES)} 条命令")
    return 0


if __name__ == "__main__":
    sys.exit(main())
