#!/usr/bin/env python
"""awk-lite 与 GNU awk 5.3.2 的差分对拍（语义层）。

用法：
    python AI/脚本/_t1301_probe_awk_diff.py

产出：
    AI/产物/awk-diff/cases.json  逐条结果

关键设计（第一版踩过的坑）：
- GNU awk 是 MSYS 程序。原生 Windows 父进程 spawn 它时，MSYS 运行时会对
  **未加引号的** argv 元素做花括号展开：`{print}` 被改成 `print`，`{a,b}` 被
  拆成两个元素。第一版把程序直接放在 argv 里，于是 GNU 侧收到的是残缺的程序，
  报出一堆「语义差异」——那是假差异。
- 绕法：把 GNU 的程序写进文件，用 `awk -f prog.awk` 传，程序就不经过 argv。
- 本项目是原生 Windows 程序（python.exe），argv 不经 MSYS 运行时，原样到达。
- 输出先把 CRLF 归一成 LF 再比；换行符差异单独记账。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "AI" / "产物" / "awk-diff"


def find_awk() -> str | None:
    candidates = []
    which = shutil.which("awk")
    if which:
        candidates.append(which)
    candidates.append(r"E:\software\Git\Git\usr\bin\awk.exe")
    for path in candidates:
        if path and Path(path).exists():
            return str(Path(path).resolve())
    return None


AWK = find_awk()

FIXTURES: dict[str, bytes] = {
    "app.log": b"INFO start app\nERROR failed db\nwarn  retry queue\nERROR again db\n",
    "two.log": b"INFO second file\nERROR tail error\n",
    "semi.log": b"a;b;c\nd;e;f\n",
    "gap.log": b"a;;c\n",
    "empty.log": b"",
    "blank.log": b"\n\nx y\n",
    "nonl.log": b"one two",
    "multi.txt": b"aXXbXXc\n",
    "dot.txt": b"a.b.c\n",
    "sp.txt": b"a  b   c\n",
    "tab.txt": b"a\tb\n",
    "crlf.log": b"a b\r\nc d\r\n",
    "gbk.log": "INFO 开始\nERROR 失败\n".encode("gb18030"),
}


# ---------------------------------------------------------------- 用例表
# 每条：(名字, 选项, 程序, 文件, 标准输入)
# 项目侧 argv = [python, main.py, awk-lite] + 选项 + [程序] + 文件
# GNU 侧  argv = [awk] + 选项 + ["-f", 程序文件] + 文件

CASES: list[tuple[str, list[str], str, list[str], bytes | None]] = [
    # --- 基本字段投影 ---
    ("字段取值 $1", [], "{print $1}", ["app.log"], None),
    ("字段取值 $2", [], "{print $2}", ["app.log"], None),
    ("末字段 $NF", [], "{print $NF}", ["app.log"], None),
    ("裸 print", [], "{print}", ["app.log"], None),
    ("$0 整行", [], "{print $0}", ["app.log"], None),
    ("两个字段", [], "{print $1, $2}", ["app.log"], None),
    ("越界字段", [], "{print $9}", ["app.log"], None),
    ("NF 字段数", [], "{print NF}", ["app.log"], None),
    ("NR 与 NF", [], "{print NR, NF}", ["app.log"], None),
    ("FNR 每文件重算", [], "{print FNR}", ["app.log", "two.log"], None),
    ("FILENAME", [], "{print FILENAME}", ["app.log"], None),
    ("NR 跨文件连续", [], "{print NR, $1}", ["app.log", "two.log"], None),
    ("字符串常量", [], '{print "x", $1}', ["app.log"], None),
    ("print 带括号", [], "{print($1, $2)}", ["app.log"], None),
    ("print 带分号", [], "{print $1;}", ["app.log"], None),
    ("print 无空格", [], "{print$1}", ["app.log"], None),
    ("数字常量", [], "{print 42}", ["app.log"], None),
    ("相邻字符串拼接", [], '{print "a" "b"}', ["app.log"], None),
    ("字段与字符串拼接", [], '{print $1 "\\t" $2}', ["app.log"], None),
    ("字符串里的逗号", [], '{print "a,b", $1}', ["app.log"], None),
    ("转义制表符字符串", [], '{print "a\\tb"}', ["app.log"], None),
    # --- 模式 ---
    ("纯模式", [], "/ERROR/", ["app.log"], None),
    ("模式加动作", [], "/ERROR/ {print $2}", ["app.log"], None),
    ("模式不命中", [], "/nomatch/", ["app.log"], None),
    ("行首锚点", [], "/^a/ {print}", ["semi.log"], None),
    ("或运算", [], "/ERROR|warn/ {print $1}", ["app.log"], None),
    ("字符类", [], "/[0-9]/ {print $1}", ["app.log"], None),
    ("空正则", [], "//", ["app.log"], None),
    ("模式里的转义斜杠", [], "/a\\/b/ {print}", ["app.log"], None),
    ("模式里带空格", [], "/failed db/ {print $1}", ["app.log"], None),
    # --- 分隔符 ---
    ("-F 分号", ["-F;"], "{print $2}", ["semi.log"], None),
    ("-F 逗号", ["-F,"], "{print $2}", ["semi.log"], None),
    ("-F 单字符按字面", ["-F."], "{print $2}", ["dot.txt"], None),
    ("-F 多字符按正则", ["-F[XY]+"], "{print $2}", ["multi.txt"], None),
    ("-F 两个字符", ["-FXX"], "{print $2}", ["multi.txt"], None),
    ("-F 空格等于默认", ["-F "], "{print NF}", ["sp.txt"], None),
    ("-F 转义制表符", ["-F\\t"], "{print $2}", ["tab.txt"], None),
    ("-F 空串", ["-F", ""], "{print NF}", ["app.log"], None),
    ("-F 能匹配空串", ["-Fx*"], "{print NF}", ["app.log"], None),
    ("-F 正则两端空白", ["-F , "], "{print NF}", ["sp.txt"], None),
    ("-F 竖线", ["-F|"], "{print $2}", ["multi.txt"], None),
    # --- 变量 ---
    ("变量当字段号", ["-v", "n=2"], "{print $n}", ["app.log"], None),
    ("变量当值", ["-v", "tag=INFO"], "{print tag}", ["app.log"], None),
    ("OFS 改连接符", ["-v", "OFS=;"], "{print $1, $2}", ["app.log"], None),
    ("ORS 改行结束符", ["-v", "ORS=;"], "{print $1}", ["app.log"], None),
    ("-v 给 FS", ["-v", "FS=;"], "{print $2}", ["semi.log"], None),
    ("-F 在前 -v FS 在后", ["-F;", "-v", "FS=,"], "{print $2}", ["semi.log"], None),
    ("-v FS 在前 -F 在后", ["-v", "FS=,", "-F;"], "{print $2}", ["semi.log"], None),
    ("数字变量去前导零", ["-v", "x=007"], "{print x}", ["app.log"], None),
    ("科学计数变量", ["-v", "x=1e3"], "{print x}", ["app.log"], None),
    ("小数变量", ["-v", "x=1.5"], "{print x}", ["app.log"], None),
    ("未赋值变量", [], "{print foo}", ["app.log"], None),
    ("未赋值变量当字段", [], "{print $foo}", ["app.log"], None),
    ("变量值带等号", ["-v", "a=b=c"], "{print a}", ["app.log"], None),
    # --- 数字格式 ---
    ("整数常量", [], "{print 10000000}", ["app.log"], None),
    ("长整数常量", [], "{print 100000000000000000}", ["app.log"], None),
    ("浮点常量", [], "{print 3.14159265358979}", ["app.log"], None),
    ("CONVFMT 边界 1e16", [], "{print 10000000000000000}", ["app.log"], None),
    ("CONVFMT 边界 1e15", [], "{print 1000000000000000}", ["app.log"], None),
    ("CONVFMT 边界 1e17", [], "{print 100000000000000000}", ["app.log"], None),
    ("小数零头", [], "{print 0.1}", ["app.log"], None),
    ("负数", [], "{print -5}", ["app.log"], None),
    # --- 文件与流 ---
    ("读标准输入", [], "{print $1}", [], b"a b\nc d\n"),
    ("破折号读标准输入", [], "{print $1}", ["-"], b"a b\nc d\n"),
    ("文件与标准输入混排", [], "{print NR, $1}", ["app.log", "-"], b"x y\n"),
    ("标准输入的 FILENAME", [], "{print FILENAME}", [], b"a b\n"),
    ("空文件", [], "{print $1}", ["empty.log"], None),
    ("空行", [], "{print NF}", ["blank.log"], None),
    ("末行无换行", [], "{print $2}", ["nonl.log"], None),
    ("CRLF 文件", [], "{print $2}", ["crlf.log"], None),
    ("文件不存在", [], "{print $1}", ["nope.log"], None),
    ("中间文件不存在", [], "{print $1}", ["app.log", "nope.log", "two.log"], None),
    ("目录当文件", [], "{print $1}", ["subdir"], None),
    ("GBK 文件", [], "{print $2}", ["gbk.log"], None),
    # --- 错误路径 ---
    ("空程序", [], "", ["app.log"], None),
    ("没有大括号", [], "print $1", ["app.log"], None),
    ("大括号没闭合", [], "{print $1", ["app.log"], None),
    ("printf 不支持", [], '{printf "%s", $1}', ["app.log"], None),
    ("算术不支持", [], "{print $1 + $2}", ["app.log"], None),
    ("正则没收尾", [], "/ERROR", ["app.log"], None),
    ("BEGIN 不支持", [], "BEGIN {print 1}", ["app.log"], None),
    ("END 不支持", [], "END {print 1}", ["app.log"], None),
]


def build_workdir() -> Path:
    work = OUT / "work"
    work.mkdir(parents=True, exist_ok=True)
    for name, data in FIXTURES.items():
        (work / name).write_bytes(data)
    (work / "subdir").mkdir(exist_ok=True)
    return work


def env() -> dict[str, str]:
    e = dict(os.environ)
    e["MSYS_NO_PATHCONV"] = "1"
    e["LC_ALL"] = "C"
    return e


def run_project(opts, program, files, work, stdin):
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "awk-lite", *opts, program, *files],
        cwd=str(work),
        input=stdin if stdin is not None else b"",
        capture_output=True,
        env=env(),
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_gnu(opts, program, files, work, stdin, progfile):
    proc = subprocess.run(
        [AWK, *opts, "-f", str(progfile), *files],
        cwd=str(work),
        input=stdin if stdin is not None else b"",
        capture_output=True,
        env=env(),
    )
    return proc.returncode, proc.stdout, proc.stderr


def norm(data: bytes) -> str:
    text = data.replace(b"\r\n", b"\n")
    try:
        return text.decode("utf-8")
    except UnicodeDecodeError:
        return text.decode("latin-1")


def main() -> int:
    if not AWK:
        print("找不到 GNU awk，无法对拍")
        return 2

    work = build_workdir()
    OUT.mkdir(parents=True, exist_ok=True)
    progfile = OUT / "prog.awk"

    rows = []
    diffs = []
    for name, opts, program, files, stdin in CASES:
        progfile.write_text(program + "\n", encoding="utf-8")
        pcode, pout, perr = run_project(opts, program, files, work, stdin)
        gcode, gout, gerr = run_gnu(opts, program, files, work, stdin, progfile)

        p_text, g_text = norm(pout), norm(gout)
        same_out = p_text == g_text
        same_code = pcode == gcode
        crlf = b"\r\n" in pout and b"\r\n" not in gout

        row = {
            "name": name,
            "opts": opts,
            "program": program,
            "files": files,
            "stdin": stdin.decode("utf-8", "replace") if stdin else None,
            "proj_code": pcode,
            "gnu_code": gcode,
            "same_out": same_out,
            "same_code": same_code,
            "proj_out": p_text,
            "gnu_out": g_text,
            "proj_err": perr.decode("utf-8", "replace").strip(),
            "gnu_err": gerr.decode("utf-8", "replace").strip(),
            "crlf_only": crlf,
        }
        rows.append(row)
        if not (same_out and same_code):
            diffs.append(row)

    (OUT / "cases.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"GNU awk: {AWK}")
    print(f"用例总数 {len(rows)}，不一致 {len(diffs)}")
    print("=" * 74)
    for row in diffs:
        print(f"[差异] {row['name']}")
        print(f"  选项   {row['opts']}  程序 {row['program']!r}  文件 {row['files']}")
        print(f"  退出码 项目 {row['proj_code']} / GNU {row['gnu_code']}")
        print(f"  项目输出 {row['proj_out']!r}")
        print(f"  GNU 输出 {row['gnu_out']!r}")
        if row["proj_err"]:
            print(f"  项目错误 {row['proj_err']}")
        if row["gnu_err"]:
            print(f"  GNU 错误 {row['gnu_err']}")
        print("-" * 74)

    crlf_rows = [r["name"] for r in rows if r["crlf_only"]]
    print(f"仅换行符不同（项目 CRLF / GNU LF）的用例数：{len(crlf_rows)}")
    code_only = [r["name"] for r in rows if r["same_out"] and not r["same_code"]]
    print(f"输出一致但退出码不同：{code_only}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
