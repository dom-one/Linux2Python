#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""差分对照：w2l 的 sed 实现 vs Git Bash 的 GNU sed 4.9。

脚本用 -f 传（绕开 MSYS 运行时对命令行反斜杠的改写），选项放在 -f 之前
（GNU sed 遇到第一个非选项参数就停止解析选项）。

用法：python AI/脚本/_t1001_probe_sed_diff.py
产物：AI/数据/sed_demo/ 下的夹具 + AI/数据/sed_probe_report.txt
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "sed_probe_report.txt"
FIXDIR = ROOT / "AI" / "数据" / "sed_demo"
sys.path.insert(0, str(ROOT))

from w2l.commands.sed import run_sed  # noqa: E402

FIXTURE = b"alpha\nbravo\ncharlie\ndelta\necho\n"
NUMFIX = b"1 one\n2 two\n3 three\n4 four\n5 five\n"
NONL = b"no trailing newline"
CRLF = b"one\r\ntwo\r\nthree\r\n"
BLANK = b"first\n\nthird\n"


def find_sed() -> str:
    return shutil.which("sed") or r"C:\Program Files\Git\usr\bin\sed.exe"


# (分组, 脚本, 选项, 文件列表)
CASES: list[tuple[str, str, list[str], list[str]]] = [
    # ---- BRE 翻译：未转义元字符当字面量 ----
    ("BRE", "s/a/b/", [], ["a.txt"]),
    ("BRE", "s/(a)/X/", [], ["a.txt"]),
    ("BRE", "s/(a)(b)/X/", [], ["a.txt"]),
    ("BRE", "s/a|b/X/", [], ["a.txt"]),
    ("BRE", "s/a\\|b/X/", [], ["a.txt"]),
    ("BRE", "s/a\\+b/X/", [], ["a.txt"]),
    ("BRE", "s/ab\\?c/X/", [], ["a.txt"]),
    ("BRE", "s/a\\{2\\}/X/", [], ["a.txt"]),
    ("BRE", "s/a{2}/X/", [], ["a.txt"]),
    ("BRE", "s/\\(a\\|b\\)/X/", [], ["a.txt"]),
    ("BRE", "s/^*/X/", [], ["a.txt"]),
    ("BRE", "s/\\(.\\)/\\1!/g", [], ["a.txt"]),
    ("BRE", "s/\\(a\\)\\(l\\)/\\2\\1/", [], ["a.txt"]),
    ("BRE", "s/[0-9]\\{2\\}/N/", [], ["num.txt"]),
    ("BRE", "s/^\\([0-9]*\\) /\\1:/", [], ["num.txt"]),
    ("BRE", "s/\\(.*\\) \\(.*\\)/\\2 \\1/", [], ["num.txt"]),
    ("BRE", "s/[[:alpha:]]/Y/g", [], ["a.txt"]),
    ("BRE", "s/[[:digit:]]/Y/g", [], ["num.txt"]),
    ("BRE", "s/[[:space:]]/_/g", [], ["a.txt"]),
    ("BRE", "s/[[:alnum:]]/Y/g", [], ["num.txt"]),
    ("BRE", "s/[[:upper:]]/Y/g", [], ["a.txt"]),
    ("BRE", "s/[[:punct:]]/Y/g", [], ["a.txt"]),
    ("BRE", "s/x\\{0,1\\}/Y/", [], ["a.txt"]),
    ("BRE", "s/\\w\\+/Y/g", [], ["a.txt"]),
    ("BRE", "s/\\balpha\\b/X/", [], ["a.txt"]),
    # ---- ERE：-r 切换 ----
    ("ERE", "s/(a)(l)/\\2\\1/", ["-r"], ["a.txt"]),
    ("ERE", "s/a|o/X/", ["-r"], ["a.txt"]),
    ("ERE", "s/a|o/X/", [], ["a.txt"]),
    ("ERE", "s/(a)+/X/", ["-r"], ["a.txt"]),
    ("ERE", "s/a{2}/X/", ["-r"], ["a.txt"]),
    ("ERE", "s/^(alpha|bravo)$/X/", ["-r"], ["a.txt"]),
    # ---- 替换标志 ----
    ("FLAG", "s/a/b/", [], ["a.txt"]),
    ("FLAG", "s/a/b/g", [], ["a.txt"]),
    ("FLAG", "s/a/A/2", [], ["a.txt"]),
    ("FLAG", "s/a/A/3", [], ["a.txt"]),
    ("FLAG", "s/a/A/9", [], ["a.txt"]),
    ("FLAG", "s/A/alpha/I", [], ["a.txt"]),
    ("FLAG", "s/A/alpha/i", [], ["a.txt"]),
    ("FLAG", "s/a/b/p", [], ["a.txt"]),
    ("FLAG", "s/a/b/gp", [], ["a.txt"]),
    ("FLAG", "s/a/b/gp", ["-n"], ["a.txt"]),
    ("FLAG", "s/a/&b/", [], ["a.txt"]),
    ("FLAG", "s/a/&&/", [], ["a.txt"]),
    ("FLAG", "s/.*/X/", [], ["a.txt"]),
    ("FLAG", "s/.*/X/g", [], ["a.txt"]),
    ("FLAG", "s/^/>/", [], ["a.txt"]),
    ("FLAG", "s/$/</", [], ["a.txt"]),
    ("FLAG", "s/\\(.\\)\\(.\\)/\\2\\1/", [], ["a.txt"]),
    ("FLAG", "s/\\(a\\)/\\1\\1/g", [], ["a.txt"]),
    # ---- 大小写修饰 ----
    ("CASE", "s/a/\\Uab/", [], ["a.txt"]),
    ("CASE", "s/A/\\Lab/", [], ["a.txt"]),
    ("CASE", "s/a/\\Uab\\Ecd/", [], ["a.txt"]),
    ("CASE", "s/alpha/\\u&/", [], ["a.txt"]),
    ("CASE", "s/ALPHA/\\l&/", [], ["a.txt"]),
    ("CASE", "s/alpha/\\U&/", [], ["a.txt"]),
    ("CASE", "s/alpha/\\L&/", [], ["a.txt"]),
    ("CASE", "s/alpha/\\u&\\l&/", [], ["a.txt"]),
    ("CASE", "s/alpha/\\U&\\E&/", [], ["a.txt"]),
    # ---- 转义 ----
    ("ESC", "s/a/\\n/", [], ["a.txt"]),
    ("ESC", "s/a/\\t/", [], ["a.txt"]),
    ("ESC", "s/a/\\\\/", [], ["a.txt"]),
    ("ESC", "s/a/\\d/", [], ["a.txt"]),
    ("ESC", "s/a/\\r/", [], ["a.txt"]),
    # ---- 地址 ----
    ("ADDR", "$p", ["-n"], ["a.txt"]),
    ("ADDR", "2,3p", ["-n"], ["a.txt"]),
    ("ADDR", "2,2p", ["-n"], ["a.txt"]),
    ("ADDR", "/bravo/,/charlie/p", ["-n"], ["a.txt"]),
    ("ADDR", "/bravo/,/zzz/p", ["-n"], ["a.txt"]),
    ("ADDR", "/zzz/,/echo/p", ["-n"], ["a.txt"]),
    ("ADDR", "/bravo/,4p", ["-n"], ["a.txt"]),
    ("ADDR", "2,+2p", ["-n"], ["a.txt"]),
    ("ADDR", "2,+0p", ["-n"], ["a.txt"]),
    ("ADDR", "2,+3p", ["-n"], ["a.txt"]),
    ("ADDR", "1~2p", ["-n"], ["a.txt"]),
    ("ADDR", "2~2p", ["-n"], ["a.txt"]),
    ("ADDR", "0,/bravo/p", ["-n"], ["a.txt"]),
    ("ADDR", "99p", ["-n"], ["a.txt"]),
    ("ADDR", "1,99p", ["-n"], ["a.txt"]),
    ("ADDR", "1,3p", ["-n"], ["a.txt"]),
    ("ADDR", "/bravo/,+2p", ["-n"], ["a.txt"]),
    ("ADDR", "/bravo/,~2p", ["-n"], ["a.txt"]),
    ("ADDR", "/bravo/p", ["-n"], ["a.txt"]),
    ("ADDR", "2!d", [], ["a.txt"]),
    ("ADDR", "/bravo/!d", [], ["a.txt"]),
    ("ADDR", "2,4!p", ["-n"], ["a.txt"]),
    # ---- 命令块 ----
    ("BLOCK", "/bravo/{p;d}", ["-n"], ["a.txt"]),
    ("BLOCK", "/a/{s/a/A/}", [], ["a.txt"]),
    ("BLOCK", "1,3{s/a/A/}", [], ["a.txt"]),
    ("BLOCK", "$!{s/a/A/}", [], ["a.txt"]),
    ("BLOCK", "/bravo/{s/a/X/;t end}\np\n:end", ["-n"], ["a.txt"]),
    ("BLOCK", "/bravo/{s/zzz/X/;t end}\np\n:end", ["-n"], ["a.txt"]),
    ("BLOCK", "/bravo/{s/a/X/;T end}\np\n:end", ["-n"], ["a.txt"]),
    ("BLOCK", "/bravo/b end\np\n:end", ["-n"], ["a.txt"]),
    ("BLOCK", ":a\nN\n$!ba\ns/\\n/-/\np", ["-n"], ["a.txt"]),
    ("BLOCK", "/bravo/{n;d}", ["-n"], ["a.txt"]),
    # ---- 追加插入替换 ----
    ("TEXT", "1a\\inserted", [], ["a.txt"]),
    ("TEXT", "1a inserted", [], ["a.txt"]),
    ("TEXT", "1i\\inserted", [], ["a.txt"]),
    ("TEXT", "1i inserted", [], ["a.txt"]),
    ("TEXT", "1c\\changed", [], ["a.txt"]),
    ("TEXT", "1c changed", [], ["a.txt"]),
    ("TEXT", "1a\\inserted", ["-n"], ["a.txt"]),
    ("TEXT", "1i\\inserted", ["-n"], ["a.txt"]),
    ("TEXT", "1c\\changed", ["-n"], ["a.txt"]),
    ("TEXT", "$a\\end", [], ["a.txt"]),
    ("TEXT", "1a\\one\\ntwo", [], ["a.txt"]),
    ("TEXT", "1i\\one\\ntwo", [], ["a.txt"]),
    ("TEXT", "1c\\one\\ntwo", [], ["a.txt"]),
    # ---- 下一行 ----
    ("NEXT", "n;p", ["-n"], ["a.txt"]),
    ("NEXT", "N;p", ["-n"], ["a.txt"]),
    ("NEXT", "N;s/\\n/-/;p", ["-n"], ["a.txt"]),
    ("NEXT", "n", [], ["a.txt"]),
    ("NEXT", "N", [], ["a.txt"]),
    ("NEXT", "n;d", [], ["a.txt"]),
    # ---- 打印与退出 ----
    ("QUIT", "p", ["-n"], ["a.txt"]),
    ("QUIT", "=", ["-n"], ["a.txt"]),
    ("QUIT", "=;p", ["-n"], ["a.txt"]),
    ("QUIT", "2q", [], ["a.txt"]),
    ("QUIT", "q", [], ["a.txt"]),
    ("QUIT", "2Q", [], ["a.txt"]),
    ("QUIT", "q;p", [], ["a.txt"]),
    ("QUIT", "2q;p", [], ["a.txt"]),
    ("QUIT", "Q;p", [], ["a.txt"]),
    ("QUIT", "$!d", [], ["a.txt"]),
    # ---- 转写 ----
    ("TRANS", "y/abc/xyz/", [], ["a.txt"]),
    ("TRANS", "y/aeiou/AEIOU/", [], ["a.txt"]),
    ("TRANS", "y/aeiou/12345/", [], ["a.txt"]),
    # ---- 多文件与 -s ----
    ("MULTI", "s/alpha/A/", [], ["m1.txt", "m2.txt"]),
    ("MULTI", "=", ["-n"], ["m1.txt", "m2.txt"]),
    ("MULTI", "=", ["-n", "-s"], ["m1.txt", "m2.txt"]),
    ("MULTI", "s/alpha/A/", ["-s"], ["m1.txt", "m2.txt"]),
    # ---- 分隔符 ----
    ("DELIM", "s|alpha|ALPHA|", [], ["a.txt"]),
    ("DELIM", "s#alpha#ALPHA#", [], ["a.txt"]),
    ("DELIM", "s,alpha,ALPHA,", [], ["a.txt"]),
    ("DELIM", "s/a\\/b/X/", [], ["a.txt"]),
    ("DELIM", r"\|bravo|p", ["-n"], ["a.txt"]),
    ("DELIM", r"\%bravo%p", ["-n"], ["a.txt"]),
    ("DELIM", r"\?bravo?p", ["-n"], ["a.txt"]),
    ("DELIM", r"\#bravo#p", ["-n"], ["a.txt"]),
    ("DELIM", r"\|bravo|,2p", ["-n"], ["a.txt"]),
    # ---- 其它 ----
    ("MISC", "", [], ["a.txt"]),
    ("MISC", "# only comment", [], ["a.txt"]),
    ("MISC", "s/one/1/", [], ["crlf.txt"]),
    ("MISC", "s/$/!/", [], ["crlf.txt"]),
    ("MISC", "/^$/p", ["-n"], ["crlf.txt"]),
    ("MISC", "s/no/NOT/", [], ["nonl.txt"]),
    ("MISC", "p", ["-n"], ["nonl.txt"]),
    ("MISC", "s/one/1/", [], ["num.txt"]),
    ("MISC", "s/^[0-9]* //", [], ["num.txt"]),
    ("MISC", "s/one/1/", ["-b"], ["crlf.txt"]),
    ("MISC", "s/$/!/", ["-b"], ["crlf.txt"]),
    ("MISC", "/^$/p", ["-n"], ["blank.txt"]),
    ("MISC", "s/a/b/;s/b/c/", [], ["a.txt"]),
    ("MISC", "s/a/b/;;s/b/c/", [], ["a.txt"]),
    ("MISC", "  s/a/b/  ", [], ["a.txt"]),
    ("MISC", "s/a/b/ ; s/b/c/", [], ["a.txt"]),
    ("MISC", "p;d", [], ["a.txt"]),
]


def main() -> int:
    sed = find_sed()
    FIXDIR.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="sedprobe_"))

    (tmp / "a.txt").write_bytes(FIXTURE)
    (tmp / "num.txt").write_bytes(NUMFIX)
    (tmp / "nonl.txt").write_bytes(NONL)
    (tmp / "crlf.txt").write_bytes(CRLF)
    (tmp / "blank.txt").write_bytes(BLANK)
    (tmp / "m1.txt").write_bytes(b"1 alpha\n")
    (tmp / "m2.txt").write_bytes(b"2 alpha\n")

    # 固定夹具也写到 AI/数据/sed_demo/，教程里直接引用它
    for name, data in (
        ("a.txt", FIXTURE),
        ("num.txt", NUMFIX),
        ("nonl.txt", NONL),
        ("crlf.txt", CRLF),
        ("blank.txt", BLANK),
        ("m1.txt", b"1 alpha\n"),
        ("m2.txt", b"2 alpha\n"),
    ):
        (FIXDIR / name).write_bytes(data)

    report: list[str] = []
    same = 0
    diff = 0
    err_both = 0
    by_group: dict[str, list[int]] = {}

    for index, (group, script, options, files) in enumerate(CASES, 1):
        script_path = tmp / "s.sed"
        script_path.write_bytes(script.encode("utf-8"))
        gnu = subprocess.run(
            [sed, *options, "-f", "s.sed", *files],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(tmp),
        )
        # 本实现对脚本错误抛 UsageError，不能让一条坏用例炸掉整个探针
        try:
            mine = run_sed([*options, script, *files], cwd=tmp)
            my_out = mine[1].encode("utf-8")
            my_code = mine[0]
            my_err = mine[2]
        except Exception as exc:  # noqa: BLE001 - 探针要记录任何失败
            my_out = b""
            my_code = -1
            my_err = f"{type(exc).__name__}: {exc}"

        gnu_out = gnu.stdout
        # 两边都报错，且本实现没产出任何输出 —— 归为「两边都拒绝」，
        # 不算输出差异，但要在报告里单列（GNU 的报错文案与退出码都不同）
        mine_failed = my_code == -1
        gnu_failed = gnu.returncode != 0 and not gnu_out
        if mine_failed and gnu_failed:
            err_both += 1
            by_group.setdefault(group, []).append(1)
            report.append(f"--- 用例 {index} [{group}] 两边都报错（不计入输出差异）")
            report.append(f"脚本={script!r}")
            report.append(f"GNU   exit={gnu.returncode} err={gnu.stderr.decode('utf-8', 'replace').strip()!r}")
            report.append(f"本实现 {my_err!r}")
            report.append("")
            continue

        out_same = gnu_out == my_out
        code_same = gnu.returncode == my_code
        if out_same:
            same += 1
            by_group.setdefault(group, []).append(1)
        else:
            diff += 1
            by_group.setdefault(group, []).append(0)
            report.append(f"### 用例 {index} [{group}]")
            report.append(f"脚本={script!r}")
            report.append(f"选项={options!r} 文件={files!r}")
            report.append(f"GNU   exit={gnu.returncode} out={gnu_out!r}")
            report.append(f"本实现 exit={my_code} out={my_out!r}")
            report.append(f"本实现 stderr={my_err!r}")
            report.append(f"退出码一致={code_same}")
            report.append("")

    print(f"[result] 脚本用例 {len(CASES)}：输出一致 {same}，输出不一致 {diff}，两边都报错 {err_both}")
    for group in sorted(by_group):
        vals = by_group[group]
        print(f"[result]   {group}: {sum(vals)}/{len(vals)} 一致")

    # ---- 原地编辑：比的是文件内容 ----
    ip_same = 0
    ip_diff = 0
    IP_CASES = [
        ("s/a/A/g", [], "ip.txt"),
        ("2d", [], "ip.txt"),
        ("/a/d", [], "ip.txt"),
        ("s/one/1/", [], "ipcrlf.txt"),
        ("s/a/A/", [], "ipnonl.txt"),
        ("$a\\end", [], "ip.txt"),
        ("1i\\first", [], "ip.txt"),
        ("s/$/!/", [], "ip.txt"),
        ("s/a/A/g", ["-b"], "ipcrlf.txt"),
    ]
    for index, (script, options, filename) in enumerate(IP_CASES, 1):
        script_path = tmp / "s.sed"
        script_path.write_bytes(script.encode("utf-8"))
        base = b"alpha\nbravo\ncharlie\ndelta\necho\n"
        gnu_file = tmp / "gnu_target.txt"
        gnu_file.write_bytes(base)
        subprocess.run(
            [sed, *options, "-i", "-f", "s.sed", gnu_file.name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(tmp),
        )
        mine_file = tmp / "mine_target.txt"
        mine_file.write_bytes(base)
        run_sed([*options, "-i", script, mine_file.name], cwd=tmp)
        gnu_bytes = gnu_file.read_bytes()
        my_bytes = mine_file.read_bytes()
        if gnu_bytes == my_bytes:
            ip_same += 1
        else:
            ip_diff += 1
            report.append(f"### 原地用例 {index}")
            report.append(f"脚本={script!r} 选项={options!r}")
            report.append(f"GNU   内容={gnu_bytes!r}")
            report.append(f"本实现 内容={my_bytes!r}")
            report.append("")

    print(f"[result] 原地用例 {len(IP_CASES)}：一致 {ip_same}，不一致 {ip_diff}")

    # ---- 标准输入 ----
    stdin_same = 0
    stdin_diff = 0
    STDIN_CASES = [
        ("s/a/b/", FIXTURE),
        ("/a/d", FIXTURE),
        ("p", FIXTURE),
        ("2q", FIXTURE),
        ("s/a/b/g", NUMFIX),
        ("N;s/\\n/-/;p", FIXTURE),
    ]
    for index, (script, data) in enumerate(STDIN_CASES, 1):
        script_path = tmp / "s.sed"
        script_path.write_bytes(script.encode("utf-8"))
        gnu = subprocess.run(
            [sed, "-f", "s.sed"],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(tmp),
        )
        mine = run_sed([script], cwd=tmp, stdin_text=data.decode("utf-8"))
        if gnu.stdout == mine[1].encode("utf-8"):
            stdin_same += 1
        else:
            stdin_diff += 1
            report.append(f"### 标准输入用例 {index}")
            report.append(f"脚本={script!r}")
            report.append(f"GNU   exit={gnu.returncode} out={gnu.stdout!r}")
            report.append(f"本实现 exit={mine[0]} out={mine[1].encode('utf-8')!r}")
            report.append("")

    print(f"[result] 标准输入用例 {len(STDIN_CASES)}：一致 {stdin_same}，不一致 {stdin_diff}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    header = [
        f"脚本用例 {len(CASES)}：输出一致 {same}，不一致 {diff}，两边都报错 {err_both}",
        f"原地用例 {len(IP_CASES)}：一致 {ip_same}，不一致 {ip_diff}",
        f"标准输入用例 {len(STDIN_CASES)}：一致 {stdin_same}，不一致 {stdin_diff}",
        "",
    ]
    OUT.write_text("\n".join(header + report), encoding="utf-8", newline="\n")
    print(f"[result] 报告已写入 {OUT}")
    print(f"[result] 夹具目录 {FIXDIR}")
    print(f"[result] 临时语料目录 {tmp}")
    return 0 if diff == 0 and ip_diff == 0 and stdin_diff == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
