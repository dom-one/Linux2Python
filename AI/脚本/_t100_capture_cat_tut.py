"""捕获 cat 教程里每条命令的真实输出，用来填「预期输出」块。

用法:
    python AI/脚本/_t100_capture_cat_tut.py

做法:
    教程里的命令在 Git Bash 里跑（读者看到的就是 bash 写法），
    抓下来的输出原样写进 teach/ 的「预期输出」围栏块。

产出:
    AI/数据/t100_cat_tut_capture.txt

注意:
    语料一律用 printf 现场造，不落盘。造出来的字节直接进管道，
    读者照抄就能跑。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASH = r"E:\software\Git\Git\bin\bash.exe"
OUT = ROOT / "AI" / "数据" / "t100_cat_tut_capture.txt"

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)
    print(text)


# (步骤标题, 命令)
STEPS: list[tuple[str, str]] = [
    ("1-1 文件规模", "python main.py cat w2l/commands/cat.py | wc -l"),
    ("1-2 选项列表", "python main.py cat --help"),
    ("2-1 默认原样输出", "python main.py cat w2l/errors.py"),
    ("3-1 多文件连接", "python main.py cat w2l/errors.py w2l/context.py"),
    ("3-2 行号跨文件累计", "python main.py cat -n w2l/errors.py w2l/context.py"),
    ("4-1 -b 只给非空行编号", "python main.py cat -b w2l/errors.py"),
    ("4-2 -n 给所有行编号", "python main.py cat -n w2l/errors.py"),
    ("4-3 -b 覆盖 -n", "python main.py cat -n -b w2l/errors.py"),
    ("4-4 -b 覆盖 -n 反序", "python main.py cat -b -n w2l/errors.py"),
    ("5-1 -s 压连续空行", "python main.py cat -s w2l/errors.py"),
    ("5-2 含空格行不算空行", "printf 'one\\n   \\ntwo\\n' | python main.py cat -s -"),
    ("5-3 含空格行照样编号", "printf 'one\\n   \\ntwo\\n' | python main.py cat -b -"),
    ("6-1 -E 行尾加 $", "python main.py cat -E w2l/errors.py"),
    ("6-2 末行无换行不补 $", "printf 'one\\ntwo' | python main.py cat -E -"),
    ("7-1 -T 制表符 ^I", "printf 'col1\\tcol2\\n' | python main.py cat -T -"),
    ("7-2 -v 不动制表符", "printf 'col1\\tcol2\\n' | python main.py cat -v -"),
    ("7-3 -vT 合起来", "printf 'col1\\tcol2\\n' | python main.py cat -vT -"),
    ("8-1 -v 控制字符记号", "printf 'bell\\a del\\177 esc\\033\\n' | python main.py cat -v -"),
    ("8-2 -v 高位字节记号", "printf '\\200\\240\\377\\n' | python main.py cat -v -"),
    ("8-3 高位字节 -v 的字节", "printf '\\200\\240\\377\\n' | python main.py cat -v - | od -c"),
    ("9-1 -e 等价 -vE", "printf 'bell\\a del\\177 esc\\033\\n' | python main.py cat -e -"),
    ("9-2 -t 等价 -vT", "printf 'col1\\tcol2\\n' | python main.py cat -t -"),
    ("9-3 -A 等价 -vET", "printf 'col1\\tcol2\\n' | python main.py cat -A -"),
    ("9-4 -A 遇 CRLF", "printf 'l1\\r\\nl2\\r\\n' | python main.py cat -A -"),
    ("10-1 CRLF 原样转交", "printf 'l1\\r\\nl2\\r\\n' | python main.py cat -"),
    ("10-2 CRLF 的字节", "printf 'l1\\r\\nl2\\r\\n' | python main.py cat - | od -c"),
    ("10-3 CRLF 空行不算空行", "printf 'a\\n\\r\\n\\r\\nb\\n' | python main.py cat -b -"),
    ("11-1 二进制原样转交", "printf 'a\\000b\\n' | python main.py cat - | od -c"),
    ("11-2 高位字节原样转交", "printf '\\200\\240\\377\\n' | python main.py cat - | od -c"),
    ("12-1 GBK 解码成 UTF-8", "printf '\\320\\220\\314\\304\\314\\332\\310\\335\\n' | python main.py cat -"),
    ("12-2 GBK 的字节", "printf '\\320\\220\\314\\304\\314\\332\\310\\335\\n' | python main.py cat - | od -c"),
    ("13-1 不给操作数读 stdin", "printf 'from stdin\\n' | python main.py cat"),
    ("13-2 - 表示 stdin", "printf 'from stdin\\n' | python main.py cat -"),
    ("13-3 文件与 - 混排", "printf 'tail\\n' | python main.py cat w2l/errors.py -"),
    ("13-4 stdin 的 CRLF", "printf 'l1\\r\\nl2\\r\\n' | python main.py cat - | od -c"),
    ("14-1 文件不存在", "python main.py cat nope.txt"),
    ("14-2 文件不存在不影响其余", "python main.py cat nope.txt w2l/errors.py"),
    ("14-3 目录当操作数", "python main.py cat w2l"),
]


def main() -> int:
    for title, cmd in STEPS:
        proc = subprocess.run(
            [BASH, "-c", cmd],
            capture_output=True,
            cwd=str(ROOT),
        )
        say("### %s" % title)
        say("$ %s" % cmd)
        say("--- 退出码 %d ---" % proc.returncode)
        say("--- stdout ---")
        for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
            say(line)
        if proc.stderr:
            say("--- stderr ---")
            for line in proc.stderr.decode("utf-8", errors="replace").splitlines():
                say(line)
        say()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes("\n".join(lines).encode("utf-8"))
    print()
    print("捕获已写到 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
