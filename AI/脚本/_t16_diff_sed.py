#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""差分对照：本实现 vs Git Bash 的 GNU sed。

脚本用 -f 传（绕开 MSYS 运行时对命令行反斜杠的改写），选项放在 -f 之前
（GNU sed 遇到第一个非选项参数就停止解析选项）。

用法：python AI/脚本/_t16_diff_sed.py
产物：AI/数据/sed_diff.txt
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "数据" / "sed_diff.txt"
sys.path.insert(0, str(ROOT))

from w2l.commands.sed import run_sed  # noqa: E402

FIXTURE = b"alpha\nbravo\ncharlie\ndelta\necho\n"
NUMFIX = b"1 one\n2 two\n3 three\n4 four\n5 five\n"
NONL = b"no trailing newline"
CRLF = b"one\r\ntwo\r\nthree\r\n"


def find_sed() -> str:
    return shutil.which("sed") or r"C:\Program Files\Git\usr\bin\sed.exe"


# (脚本, 选项, 文件列表)
CASES: list[tuple[str, list[str], list[str]]] = [
    # ---- 替换 ----
    ("s/a/b/", [], ["a.txt"]),
    ("s/a/b/g", [], ["a.txt"]),
    ("s/a/A/2", [], ["a.txt"]),
    ("s/a/A/9", [], ["a.txt"]),
    ("s/A/alpha/I", [], ["a.txt"]),
    ("s/A/alpha/i", [], ["a.txt"]),
    ("s/a/b/p", [], ["a.txt"]),
    ("s/a/b/gp", [], ["a.txt"]),
    ("s/a/&b/", [], ["a.txt"]),
    ("s/a/&&/", [], ["a.txt"]),
    ("s/\\(a\\)\\(l\\)/\\2\\1/", [], ["a.txt"]),
    ("s/\\(a\\)/\\1\\1/g", [], ["a.txt"]),
    ("s/(a)(l)/\\2\\1/", ["-r"], ["a.txt"]),
    ("s/a|o/X/", [], ["a.txt"]),
    ("s/a|o/X/", ["-r"], ["a.txt"]),
    ("s/a\\|o/X/", [], ["a.txt"]),
    ("s|alpha|ALPHA|", [], ["a.txt"]),
    ("s#alpha#ALPHA#", [], ["a.txt"]),
    ("s,alpha,ALPHA,", [], ["a.txt"]),
    ("s/a\\/b/X/", [], ["a.txt"]),
    ("s/^a/A/", [], ["a.txt"]),
    ("s/e$/E/", [], ["a.txt"]),
    ("s/\\balpha\\b/X/", [], ["a.txt"]),
    ("s/\\(.\\)/\\1!/g", [], ["a.txt"]),
    ("s/[aeiou]/_/g", [], ["a.txt"]),
    ("s/^$/EMPTY/", [], ["a.txt"]),
    ("s/a/A/g;s/b/B/g", [], ["a.txt"]),
    ("s/a/A/;s/b/B/", [], ["a.txt"]),
    # ---- 大小写修饰 ----
    ("s/a/\\Uab/", [], ["a.txt"]),
    ("s/A/\\Lab/", [], ["a.txt"]),
    ("s/a/\\Uab\\Ecd/", [], ["a.txt"]),
    ("s/alpha/\\u&/", [], ["a.txt"]),
    ("s/ALPHA/\\l&/", [], ["a.txt"]),
    ("s/alpha/\\U&/", [], ["a.txt"]),
    ("s/alpha/\\L&/", [], ["a.txt"]),
    ("s/\\(alpha\\)/\\u&/", [], ["a.txt"]),
    # ---- 转义 ----
    ("s/a/\\n/", [], ["a.txt"]),
    ("s/a/\\t/", [], ["a.txt"]),
    ("s/a/\\\\/", [], ["a.txt"]),
    ("s/a/\\d/", [], ["a.txt"]),
    # ---- 选择与删除 ----
    ("p", [], ["a.txt"]),
    ("p", ["-n"], ["a.txt"]),
    ("2p", ["-n"], ["a.txt"]),
    ("/bravo/p", ["-n"], ["a.txt"]),
    ("/bravo/d", [], ["a.txt"]),
    ("2d", [], ["a.txt"]),
    ("/bravo/{p;d}", ["-n"], ["a.txt"]),
    ("=;p", ["-n"], ["a.txt"]),
    ("2q", [], ["a.txt"]),
    ("q", [], ["a.txt"]),
    ("2Q", [], ["a.txt"]),
    # ---- 追加插入替换 ----
    ("1a\\inserted", [], ["a.txt"]),
    ("1a inserted", [], ["a.txt"]),
    ("1i\\inserted", [], ["a.txt"]),
    ("1i inserted", [], ["a.txt"]),
    ("1c\\changed", [], ["a.txt"]),
    ("1c changed", [], ["a.txt"]),
    ("1a\\inserted", ["-n"], ["a.txt"]),
    ("1i\\inserted", ["-n"], ["a.txt"]),
    ("1c\\changed", ["-n"], ["a.txt"]),
    ("$a\\end", [], ["a.txt"]),
    # ---- 下一行 ----
    ("n;p", ["-n"], ["a.txt"]),
    ("N;p", ["-n"], ["a.txt"]),
    ("N;s/\\n/-/;p", ["-n"], ["a.txt"]),
    ("n", [], ["a.txt"]),
    ("N", [], ["a.txt"]),
    # ---- 地址 ----
    ("$p", ["-n"], ["a.txt"]),
    ("2,3p", ["-n"], ["a.txt"]),
    ("2,2p", ["-n"], ["a.txt"]),
    ("/bravo/,/charlie/p", ["-n"], ["a.txt"]),
    ("/bravo/,/zzz/p", ["-n"], ["a.txt"]),
    ("/zzz/,/echo/p", ["-n"], ["a.txt"]),
    ("2,+2p", ["-n"], ["a.txt"]),
    ("2,+0p", ["-n"], ["a.txt"]),
    ("1~2p", ["-n"], ["a.txt"]),
    ("0,/bravo/p", ["-n"], ["a.txt"]),
    ("/bravo/,4p", ["-n"], ["a.txt"]),
    ("99p", ["-n"], ["a.txt"]),
    ("1,99p", ["-n"], ["a.txt"]),
    # ---- 分支 ----
    (":a\nN\n$!ba\ns/\\n/-/\np", ["-n"], ["a.txt"]),
    ("/bravo/{s/a/X/;t end}\np\n:end", ["-n"], ["a.txt"]),
    ("/bravo/b end\np\n:end", ["-n"], ["a.txt"]),
    ("/bravo/{s/zzz/X/;t end}\np\n:end", ["-n"], ["a.txt"]),
    ("/bravo/{s/a/X/;T end}\np\n:end", ["-n"], ["a.txt"]),
    # ---- 转写 ----
    ("y/abc/xyz/", [], ["a.txt"]),
    ("y/aeiou/AEIOU/", [], ["a.txt"]),
    # ---- 多文件 ----
    ("s/alpha/A/", [], ["m1.txt", "m2.txt"]),
    ("=", ["-n"], ["m1.txt", "m2.txt"]),
    ("=", ["-n", "-s"], ["m1.txt", "m2.txt"]),
    # ---- 其它 ----
    ("", [], ["a.txt"]),
    ("# only comment", [], ["a.txt"]),
    ("s/one/1/", [], ["crlf.txt"]),
    ("s/$/!/", [], ["crlf.txt"]),
    ("/^$/p", [], ["crlf.txt"]),
    ("s/no/NOT/", [], ["nonl.txt"]),
    ("p", ["-n"], ["nonl.txt"]),
    ("s/one/1/", [], ["num.txt"]),
    ("s/^[0-9]* //", [], ["num.txt"]),
    # ---- 地址分隔符的各种写法 ----
    (r"\|bravo|p", ["-n"], ["a.txt"]),
    (r"\%bravo%p", ["-n"], ["a.txt"]),
    (r"\?bravo?p", ["-n"], ["a.txt"]),
    (r"\#bravo#p", ["-n"], ["a.txt"]),
    (r"\|bravo|d", [], ["a.txt"]),
    (r"\|bravo|,2p", ["-n"], ["a.txt"]),
    # ---- 第二批：正则细节 ----
    ("s/[0-9]\\{2\\}/N/", [], ["num.txt"]),
    ("s/[0-9]\\{2\\}/N/g", [], ["num.txt"]),
    ("s/[0-9][0-9]/N/", [], ["num.txt"]),
    ("s/[0-9][0-9]/N/g", [], ["num.txt"]),
    ("s/^\\([0-9]*\\) /\\1:/", [], ["num.txt"]),
    ("s/\\(.*\\) \\(.*\\)/\\2 \\1/", [], ["num.txt"]),
    ("s/o\\{2\\}/X/", [], ["a.txt"]),
    ("s/o\\+/X/", [], ["a.txt"]),
    ("s/o\\?X/X/", [], ["a.txt"]),
    ("s/o\\?X/X/g", [], ["a.txt"]),
    ("s/a\\|b/X/", [], ["a.txt"]),
    ("s/alpha\\|bravo/X/", [], ["a.txt"]),
    ("s/\\(alpha\\|bravo\\)/X/", [], ["a.txt"]),
    ("s/\\(.\\)\\(.\\)/\\2\\1/", [], ["a.txt"]),
    ("s/.*/X/", [], ["a.txt"]),
    ("s/.*/X/g", [], ["a.txt"]),
    ("s/^/>/", [], ["a.txt"]),
    ("s/$/</", [], ["a.txt"]),
    ("s/^\\s*//", [], ["a.txt"]),
    ("s/x\\{0,1\\}/Y/", [], ["a.txt"]),
    ("s/\\w\\+/Y/g", [], ["a.txt"]),
    ("s/[[:alpha:]]/Y/g", [], ["a.txt"]),
    # ---- 第二批：指令与地址 ----
    ("s/a/b/;s/b/c/", [], ["a.txt"]),
    ("/a/{s/a/A/}", [], ["a.txt"]),
    ("/a/,/c/{s/a/A/}", [], ["a.txt"]),
    ("1,3{s/a/A/}", [], ["a.txt"]),
    ("$!{s/a/A/}", [], ["a.txt"]),
    ("/a/!d", [], ["a.txt"]),
    ("/a/!p", ["-n"], ["a.txt"]),
    ("2,4!p", ["-n"], ["a.txt"]),
    ("1!d", [], ["a.txt"]),
    ("p;d", [], ["a.txt"]),
    ("=;p", [], ["a.txt"]),
    ("q;p", [], ["a.txt"]),
    ("2q;p", [], ["a.txt"]),
    ("Q;p", [], ["a.txt"]),
    ("$!d", [], ["a.txt"]),
    ("3q", [], ["a.txt"]),
    ("y/aeiou/12345/", [], ["a.txt"]),
    ("1a\\one\\ntwo", [], ["a.txt"]),
    ("1i\\one\\ntwo", [], ["a.txt"]),
    ("1c\\one\\ntwo", [], ["a.txt"]),
    ("s/a/b/;;s/b/c/", [], ["a.txt"]),
    ("  s/a/b/  ", [], ["a.txt"]),
    ("s/a/b/ ; s/b/c/", [], ["a.txt"]),
    # ---- 第二批：多文件与 -s ----
    ("s/1/X/", [], ["m1.txt", "m2.txt"]),
    ("=", ["-n"], ["m1.txt", "m2.txt"]),
    ("s/alpha/A/", ["-s"], ["m1.txt", "m2.txt"]),
    ("=", ["-n", "-s"], ["m1.txt", "m2.txt"]),
]

# 原地编辑用例：(脚本, 选项, 文件名)
INPLACE_CASES: list[tuple[str, list[str], str]] = [
    ("s/a/A/g", [], "ip.txt"),
    ("s/a/A/g", [], "ip.txt"),
    ("s/alpha/ALPHA/", [], "ip.txt"),
    ("2d", [], "ip.txt"),
    ("/a/d", [], "ip.txt"),
    ("s/one/1/", [], "ipcrlf.txt"),
    ("s/a/A/", [], "ipnonl.txt"),
    ("$a\\end", [], "ip.txt"),
    ("1i\\first", [], "ip.txt"),
    ("s/$/!/", [], "ip.txt"),
]


def main() -> int:
    sed = find_sed()
    tmp = Path(tempfile.mkdtemp(prefix="seddiff_"))
    (tmp / "a.txt").write_bytes(FIXTURE)
    (tmp / "num.txt").write_bytes(NUMFIX)
    (tmp / "nonl.txt").write_bytes(NONL)
    (tmp / "crlf.txt").write_bytes(CRLF)
    (tmp / "m1.txt").write_bytes(b"1 alpha\n")
    (tmp / "m2.txt").write_bytes(b"2 alpha\n")

    lines: list[str] = []
    same = 0
    diff = 0
    for index, (script, options, files) in enumerate(CASES, 1):
        script_path = tmp / "s.sed"
        script_path.write_bytes(script.encode("utf-8"))
        gnu = subprocess.run(
            [sed, *options, "-f", "s.sed", *files],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(tmp),
        )
        mine = run_sed([*options, script, *files], cwd=tmp)

        gnu_out = gnu.stdout
        my_out = mine[1].encode("utf-8")
        ok = gnu_out == my_out and gnu.returncode == mine[0]
        if ok:
            same += 1
            continue
        diff += 1
        lines.append(f"### 用例 {index}")
        lines.append(f"脚本={script!r}")
        lines.append(f"选项={options!r} 文件={files!r}")
        lines.append(f"GNU   exit={gnu.returncode} out={gnu_out!r}")
        lines.append(f"本实现 exit={mine[0]} out={my_out!r}")
        lines.append("")

    # ---- 原地编辑：比的是文件内容 ----
    ip_same = 0
    ip_diff = 0
    ip_base = b"alpha\nbravo\ncharlie\ndelta\necho\n"
    for index, (script, options, filename) in enumerate(INPLACE_CASES, 1):
        script_path = tmp / "s.sed"
        script_path.write_bytes(script.encode("utf-8"))
        gnu_file = tmp / "gnu_target.txt"
        gnu_file.write_bytes(ip_base)
        subprocess.run(
            [sed, *options, "-i", "-f", "s.sed", gnu_file.name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(tmp),
        )
        mine_file = tmp / "mine_target.txt"
        mine_file.write_bytes(ip_base)
        mine = run_sed([*options, "-i", script, mine_file.name], cwd=tmp)
        gnu_bytes = gnu_file.read_bytes()
        my_bytes = mine_file.read_bytes()
        if gnu_bytes == my_bytes:
            ip_same += 1
            continue
        ip_diff += 1
        lines.append(f"### 原地用例 {index}")
        lines.append(f"脚本={script!r} 选项={options!r}")
        lines.append(f"GNU   内容={gnu_bytes!r}")
        lines.append(f"本实现 内容={my_bytes!r}")
        lines.append("")

    # ---- 标准输入 ----
    stdin_same = 0
    stdin_diff = 0
    stdin_cases = [
        ("s/a/b/", FIXTURE),
        ("/a/d", FIXTURE),
        ("p", FIXTURE),
        ("2q", FIXTURE),
        ("s/a/b/g", NUMFIX),
    ]
    for index, (script, data) in enumerate(stdin_cases, 1):
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
        if gnu.stdout == mine[1].encode("utf-8") and gnu.returncode == mine[0]:
            stdin_same += 1
            continue
        stdin_diff += 1
        lines.append(f"### 标准输入用例 {index}")
        lines.append(f"脚本={script!r}")
        lines.append(f"GNU   exit={gnu.returncode} out={gnu.stdout!r}")
        lines.append(f"本实现 exit={mine[0]} out={mine[1].encode('utf-8')!r}")
        lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    report = [
        f"脚本用例 {len(CASES)}，一致 {same}，不一致 {diff}",
        f"原地用例 {len(INPLACE_CASES)}，一致 {ip_same}，不一致 {ip_diff}",
        f"标准输入用例 {len(stdin_cases)}，一致 {stdin_same}，不一致 {stdin_diff}",
        "",
    ]
    report.extend(lines)
    OUT.write_text("\n".join(report), encoding="utf-8")
    print(f"[result] 脚本用例 {len(CASES)}：一致 {same}，不一致 {diff}")
    print(f"[result] 原地用例 {len(INPLACE_CASES)}：一致 {ip_same}，不一致 {ip_diff}")
    print(f"[result] 标准输入用例 {len(stdin_cases)}：一致 {stdin_same}，不一致 {stdin_diff}")
    print(f"[result] 报告已写入 {OUT}")
    print(f"[result] 临时语料目录 {tmp}")
    return 0 if diff == 0 and ip_diff == 0 and stdin_diff == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
