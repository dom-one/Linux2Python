"""把 teach/29 教程里准备用的命令逐条真跑一遍，记下实际输出。

用法:
    python AI/脚本/_t1407_capture_cp_tut.py

产出：AI/数据/cp_tut_capture.txt

为什么要单独写一个脚本：教程里每个命令块都要有「预期输出」，
预期输出必须来自真实运行，不能凭印象写。这个脚本按教程的步骤顺序
把命令跑一遍，输出就是可以照抄进教程的内容。

跑法与核对器一致：命令块去掉 cd 行，其余用 && 串起来在 Git Bash 里跑，
stdout 与 stderr 合并（2>&1）。
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "AI" / "数据" / "cp_tut_capture.txt"
BASH = r"E:\software\Git\Git\bin\bash.exe"

CASE = "AI/数据/cp_demo/case"
PREP = "python AI/脚本/_t1405_prep_cp_case.py"
MTIME = "python AI/脚本/_t1406_show_mtime.py"

BLOCKS: list[tuple[str, list[str]]] = [
    ("第1步 生成夹具", ["python AI/脚本/_t1403_make_cp_demo.py"]),
    ("第2步 文件拷到新名字", [
        f"{PREP} s2",
        f"python main.py cp {CASE}/s2/src/hello.txt {CASE}/s2/dst/hello.new.txt",
        f"python main.py ls {CASE}/s2/dst",
    ]),
    ("第3步 目标是已存在的目录", [
        f"{PREP} s3",
        f"python main.py cp -v {CASE}/s3/src/hello.txt {CASE}/s3/dst",
        f"python main.py ls {CASE}/s3/dst",
    ]),
    ("第4步 目标不存在就是新文件", [
        f"{PREP} s4",
        f"python main.py cp -v {CASE}/s4/src/hello.txt {CASE}/s4/dst/newname",
        f"python main.py ls {CASE}/s4/dst",
    ]),
    ("第5步 拷目录不给-r", [
        f"{PREP} s5",
        f"python main.py cp {CASE}/s5/src/project {CASE}/s5/dst",
    ]),
    ("第6步 -r 拷到已存在的目录", [
        f"{PREP} s6",
        f"python main.py cp -r -v {CASE}/s6/src/project {CASE}/s6/dst",
        f"python main.py find {CASE}/s6/dst -type f",
    ]),
    ("第7步 -r 拷到不存在的目标", [
        f"{PREP} s7",
        f"python main.py cp -r -v {CASE}/s7/src/project {CASE}/s7/dst/clone",
        f"python main.py find {CASE}/s7/dst/clone -type f",
    ]),
    ("第8步 源尾部的斜杠", [
        f"{PREP} s8",
        f"python main.py cp -r -v {CASE}/s8/src/project/ {CASE}/s8/dst",
    ]),
    ("第9步 多个源要求目标是目录", [
        f"{PREP} s9",
        f"python main.py cp {CASE}/s9/src/hello.txt {CASE}/s9/src/nosuch.txt {CASE}/s9/dst/out.txt",
    ]),
    ("第10步 多个源进已存在的目录", [
        f"{PREP} s10",
        f"python main.py cp -v {CASE}/s10/src/hello.txt {CASE}/s10/src/legacy.txt {CASE}/s10/dst",
        f"python main.py ls {CASE}/s10/dst",
    ]),
    ("第11步 -n 不覆盖", [
        f"{PREP} s11",
        f"python main.py cp -n -v {CASE}/s11/src/hello.txt {CASE}/s11/dst/old.txt",
        f"python main.py cat {CASE}/s11/dst/old.txt",
    ]),
    ("第12步 -u 目标更新就跳过", [
        f"{PREP} s12",
        f"python main.py cp -u -v {CASE}/s12/src/hello.txt {CASE}/s12/dst/future.txt",
        f"python main.py cat {CASE}/s12/dst/future.txt",
    ]),
    ("第13步 -u 源更新才复制", [
        f"{PREP} s13",
        f"python main.py cp -u -v {CASE}/s13/src/hello.txt {CASE}/s13/dst/old.txt",
        f"python main.py cat {CASE}/s13/dst/old.txt",
    ]),
    ("第14步 -i 覆盖前询问", [
        f"{PREP} s14",
        f"python main.py cp -i {CASE}/s14/src/hello.txt {CASE}/s14/dst/old.txt",
        f"python main.py cat {CASE}/s14/dst/old.txt",
    ]),
    ("第15步 -p 保住时间戳", [
        f"{PREP} s15",
        f"python main.py cp -p {CASE}/s15/src/hello.txt {CASE}/s15/dst/hello.new.txt",
        f"{MTIME} --cmp {CASE}/s15/src/hello.txt {CASE}/s15/dst/hello.new.txt",
    ]),
    ("第16步 不加-p 时间戳就是复制时刻", [
        f"{PREP} s16",
        f"python main.py cp {CASE}/s16/src/hello.txt {CASE}/s16/dst/hello.new.txt",
        f"{MTIME} --cmp {CASE}/s16/src/hello.txt {CASE}/s16/dst/hello.new.txt",
    ]),
    ("第17步 -S 覆盖前先改名", [
        f"{PREP} s17",
        f"python main.py cp -v -S .bak {CASE}/s17/src/hello.txt {CASE}/s17/dst/old.txt",
        f"python main.py ls {CASE}/s17/dst",
    ]),
    ("第18步 --parents 保留路径层级", [
        f"{PREP} s18",
        f"python main.py cp -v --parents {CASE}/s18/src/project/src/main.py {CASE}/s18/dst",
        f"python main.py find {CASE}/s18/dst -type f",
    ]),
    ("第19步 -t 指定目标目录", [
        f"{PREP} s19",
        f"python main.py cp -v -t {CASE}/s19/dst {CASE}/s19/src/hello.txt {CASE}/s19/src/legacy.txt",
        f"python main.py ls {CASE}/s19/dst",
    ]),
    ("第20步 -T 把目标当普通文件", [
        f"{PREP} s20",
        f"python main.py cp -v -T -r {CASE}/s20/src/project {CASE}/s20/dst/flat",
        f"python main.py find {CASE}/s20/dst/flat -type f",
    ]),
    ("第21步 --remove-destination 先删目标", [
        f"{PREP} s21",
        f"python main.py cp -v --remove-destination {CASE}/s21/src/hello.txt {CASE}/s21/dst/old.txt",
        f"python main.py cat {CASE}/s21/dst/old.txt",
    ]),
    ("第22步 同一个文件", [
        f"{PREP} s22",
        f"python main.py cp {CASE}/s22/src/hello.txt {CASE}/s22/src/hello.txt",
    ]),
    ("第23步 目标父目录不存在", [
        f"{PREP} s23",
        f"python main.py cp {CASE}/s23/src/hello.txt {CASE}/s23/dst/nodir/out.txt",
    ]),
    ("第24步 二进制逐字节保真", [
        f"{PREP} s24",
        f"python main.py cp {CASE}/s24/src/payload.bin {CASE}/s24/dst/payload.new.bin",
        f"python main.py wc -c {CASE}/s24/src/payload.bin {CASE}/s24/dst/payload.new.bin",
    ]),
    ("第25步 GBK 文件不被改写", [
        f"{PREP} s25",
        f"python main.py cp {CASE}/s25/src/legacy.txt {CASE}/s25/dst/legacy.new.txt",
        f"python main.py wc -c {CASE}/s25/src/legacy.txt {CASE}/s25/dst/legacy.new.txt",
    ]),
    ("第26步 --preserve 裸写会吃掉操作数", [
        f"{PREP} s26",
        f"python main.py cp --preserve {CASE}/s26/src/hello.txt {CASE}/s26/dst/hello.new.txt",
    ]),
    ("第27步 -n 与 -i 同时给", [
        f"{PREP} s27",
        f"python main.py cp -n -i {CASE}/s27/src/hello.txt {CASE}/s27/dst/old.txt",
        f"python main.py cat {CASE}/s27/dst/old.txt",
    ]),
    ("第28步 目标带尾部斜杠", [
        f"{PREP} s28",
        f"python main.py cp -v {CASE}/s28/src/hello.txt {CASE}/s28/dst/newname/",
        f"python main.py ls {CASE}/s28/dst",
    ]),
]


def run_block(lines: list[str]) -> str:
    payload = " && ".join(lines)
    full = 'cd "%s" && { %s ; } 2>&1' % (ROOT, payload)
    proc = subprocess.run(
        [BASH, "-c", full], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120
    )
    return proc.stdout.decode("utf-8", "replace").strip()


def main() -> int:
    chunks: list[str] = []
    for title, lines in BLOCKS:
        started = time.time()
        output = run_block(lines)
        chunks.append("=" * 70)
        chunks.append(f"### {title}")
        chunks.append(f"$ {' && '.join(lines)}")
        chunks.append(f"[耗时 {time.time() - started:.1f}s]")
        chunks.append(output if output else "(无输出)")
        chunks.append("")
        print(f"[OK] {title}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(chunks), encoding="utf-8")
    print("=" * 70)
    print("已写入:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
