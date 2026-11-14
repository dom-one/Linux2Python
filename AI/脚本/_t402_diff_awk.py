"""差分对照：把 awk-lite 的输出跟 GNU awk 5.3.2 逐条比对。

GNU awk 用 -f 传程序（MSYS 运行时会把命令行里的 {} 吃掉，-f 最稳），
本实现用 `python main.py awk-lite` 直接跑。

比的是文本内容：Windows 文本模式把换行写成 CRLF，先归一；
GBK 用例里 GNU awk 按字节输出（按 GBK 解），本实现统一输出 UTF-8。

产物落在 AI/数据/awk_probe/ 下。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "awk_probe"

AWK = shutil.which("awk") or shutil.which("gawk")
PYTHON = sys.executable

CRLF = b"\r\n"
LF = b"\n"

SAMPLE = (
    "INFO start app\n"
    "ERROR failed db\n"
    "warn  retry queue\n"
    "ERROR again db\n"
)


def build_fixture(tmp: Path) -> None:
    (tmp / "a.log").write_text(SAMPLE, encoding="utf-8")
    (tmp / "b.log").write_text("INFO second file\nERROR tail error\n", encoding="utf-8")
    (tmp / "empty.log").write_text("", encoding="utf-8")
    (tmp / "blank.log").write_text("\n\nx y\n", encoding="utf-8")
    (tmp / "crlf.log").write_bytes(b"a b\r\nc d\r\n")
    (tmp / "semi.log").write_text("a;b;c\nd;e;f\n", encoding="utf-8")
    (tmp / "space.log").write_text("a  b   c\n", encoding="utf-8")
    (tmp / "colon.log").write_text("a:b:c\nd:e:f\n", encoding="utf-8")
    (tmp / "tabs.log").write_text("a\t\tb\n", encoding="utf-8")
    (tmp / "gap.log").write_text("a;;c\nd;e;f\n", encoding="utf-8")
    (tmp / "gbk.log").write_bytes("INFO 开始\nERROR 失败\n".encode("gb18030"))
    (tmp / "one.log").write_text("only\n", encoding="utf-8")
    (tmp / "dot.log").write_text("a.b.c\n", encoding="utf-8")


# (说明, awk 选项, 程序, 文件列表, 比较模式)
CASES: list[tuple] = [
    ("第一列", [], "{print $1}", ["a.log"], "bytes"),
    ("第二列", [], "{print $2}", ["a.log"], "bytes"),
    ("第三列", [], "{print $3}", ["a.log"], "bytes"),
    ("最后一列", [], "{print $NF}", ["a.log"], "bytes"),
    ("整行 $0", [], "{print $0}", ["a.log"], "bytes"),
    ("裸 print", [], "{print}", ["a.log"], "bytes"),
    ("两列逗号分隔", [], "{print $1, $2}", ["a.log"], "bytes"),
    ("两列无空格", [], "{print $1,$2}", ["a.log"], "bytes"),
    ("超范围字段", [], "{print $9}", ["a.log"], "bytes"),
    ("行号", [], "{print NR}", ["a.log"], "bytes"),
    ("字段数", [], "{print NF}", ["a.log"], "bytes"),
    ("文件内行号", [], "{print FNR}", ["a.log"], "bytes"),
    ("行号加字段数", [], "{print NR, NF}", ["a.log"], "bytes"),
    ("行号加整行", [], "{print NR, $0}", ["a.log"], "bytes"),
    ("文件名", [], "{print FILENAME}", ["a.log"], "bytes"),
    ("模式筛行", [], "/ERROR/", ["a.log"], "bytes"),
    ("模式加动作", [], "/ERROR/ {print $1}", ["a.log"], "bytes"),
    ("模式加整行", [], "/ERROR/ {print}", ["a.log"], "bytes"),
    ("行首模式", [], "/^ERROR/ {print $2}", ["a.log"], "bytes"),
    ("模式不命中", [], "/nomatch/", ["a.log"], "bytes"),
    ("模式加行号", [], "/ERROR/ {print NR, $2}", ["a.log"], "bytes"),
    ("逗号分隔第一列", ["-F,"], "{print $1}", ["semi.log"], "bytes"),
    ("逗号分隔第三列", ["-F,"], "{print $3}", ["semi.log"], "bytes"),
    ("逗号分隔最后一列", ["-F,"], "{print $NF}", ["semi.log"], "bytes"),
    ("逗号分隔字段数", ["-F,"], "{print NF}", ["semi.log"], "bytes"),
    ("冒号分隔", ["-F:"], "{print $2}", ["colon.log"], "bytes"),
    ("分号分隔", ["-F;"], "{print $2}", ["semi.log"], "bytes"),
    ("制表符分隔", ["-F\\t"], "{print $2}", ["tabs.log"], "bytes"),
    ("空白串切分", [], "{print NF}", ["space.log"], "bytes"),
    ("空白串切分取值", [], "{print $2}", ["space.log"], "bytes"),
    ("多文件行号", [], "{print NR}", ["a.log", "b.log"], "bytes"),
    ("多文件文件内行号", [], "{print FNR}", ["a.log", "b.log"], "bytes"),
    ("多文件取值", [], "{print $1}", ["a.log", "b.log"], "bytes"),
    ("多文件文件名", [], "{print FILENAME}", ["a.log", "b.log"], "bytes"),
    ("空文件", [], "{print $1}", ["empty.log"], "bytes"),
    ("空行文件字段数", [], "{print NF}", ["blank.log"], "bytes"),
    ("空行文件取值", [], "{print $1}", ["blank.log"], "bytes"),
    ("CRLF 文件", [], "{print $1}", ["crlf.log"], "bytes"),
    ("CRLF 文件字段数", [], "{print NF}", ["crlf.log"], "bytes"),
    ("变量当字段号", ["-v", "x=3"], "{print $x}", ["a.log"], "bytes"),
    ("变量当字段号加逗号分隔", ["-v", "x=2", "-F,"], "{print $x}", ["semi.log"], "bytes"),
    ("变量字符串值", ["-v", "s=INFO"], "{print s}", ["a.log"], "bytes"),
    ("变量当字段名", ["-v", "s=b"], "{print $s}", ["a.log"], "bytes"),
    ("OFS 改写", ["-v", "OFS=;"], "{print $1, $2}", ["a.log"], "bytes"),
    ("OFS 改写三列", ["-v", "OFS=-"], "{print $1, $2, $3}", ["a.log"], "bytes"),
    ("数字字面量", [], "{print 42}", ["a.log"], "bytes"),
    ("小数字面量", [], "{print 3.5}", ["a.log"], "bytes"),
    ("字符串字面量", [], '{print "hello"}', ["a.log"], "bytes"),
    ("字符串加字段", [], '{print "x", $1}', ["a.log"], "bytes"),
    ("多文件加模式", [], "/ERROR/ {print $1}", ["a.log", "b.log"], "bytes"),
    ("单文件加分隔符加模式", ["-F,"], "/b/ {print $1}", ["semi.log"], "bytes"),
    ("空字段", ["-F,"], "{print $1, $2}", ["gap.log"], "bytes"),
    ("空字段加第三列", ["-F,"], "{print $1, $2, $3}", ["gap.log"], "bytes"),
    ("单列文件字段数", [], "{print NF}", ["one.log"], "bytes"),
    ("单列文件最后一列", [], "{print $NF}", ["one.log"], "bytes"),
    ("多字符分隔符", ["-F::"], "{print $2}", ["gap.log"], "bytes"),
    ("多字符分隔符取整行", ["-F::"], "{print $0}", ["gap.log"], "bytes"),
    ("单字符点号是字面量", ["-F."], "{print $2}", ["dot.log"], "bytes"),
    ("多字符正则分隔符", ["-F[X;]+"], "{print $2}", ["semi.log"], "bytes"),
    ("显式单空格分隔符", ["-F "], "{print NF}", ["space.log"], "bytes"),
    ("GBK 文件取第一列", [], "{print $1}", ["gbk.log"], "text"),
    ("GBK 文件取整行", [], "{print $0}", ["gbk.log"], "text"),
    ("GBK 文件按模式筛", [], "/ERROR/ {print $1}", ["gbk.log"], "text"),
]


def run(cmd: list[str], cwd: Path, stdin_bytes: bytes | None) -> tuple[int, bytes]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        input=stdin_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.returncode, proc.stdout


def normalize(raw: bytes, mode: str) -> str:
    """归一换行；mode=text 时 GNU awk 的输出按 GBK 解。"""
    if mode == "text":
        text = raw.decode("gb18030", "replace")
    else:
        text = raw.decode("utf-8", "replace")
    return text.replace(CRLF.decode(), LF.decode())


def main() -> int:
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)
    tmp = DATA / "fixture"
    tmp.mkdir()
    build_fixture(tmp)

    report: list[dict] = []
    mismatches = 0

    for label, options, program, files, mode in CASES:
        prog_file = tmp / "_prog.awk"
        prog_file.write_text(program, encoding="utf-8")

        gawk_cmd = [AWK, *options, "-f", str(prog_file), *files]
        ours_cmd = [
            PYTHON,
            str(ROOT / "main.py"),
            "awk-lite",
            *options,
            program,
            *files,
        ]

        g_rc, g_raw = run(gawk_cmd, tmp, None)
        o_rc, o_raw = run(ours_cmd, tmp, None)

        g_text = normalize(g_raw, mode)
        o_text = normalize(o_raw, "bytes")

        same = g_text == o_text and g_rc == o_rc
        if not same:
            mismatches += 1
        report.append(
            {
                "label": label,
                "options": options,
                "program": program,
                "files": files,
                "mode": mode,
                "gawk_rc": g_rc,
                "ours_rc": o_rc,
                "gawk_out": g_text,
                "ours_out": o_text,
                "same": same,
            }
        )

    # 标准输入一条
    prog_file = tmp / "_prog.awk"
    prog_file.write_text("{print $1}", encoding="utf-8")
    g_rc, g_raw = run([AWK, "-f", str(prog_file)], tmp, SAMPLE.encode("utf-8"))
    o_rc, o_raw = run(
        [PYTHON, str(ROOT / "main.py"), "awk-lite", "{print $1}"],
        tmp,
        SAMPLE.encode("utf-8"),
    )
    g_text = normalize(g_raw, "bytes")
    o_text = normalize(o_raw, "bytes")
    same = g_text == o_text and g_rc == o_rc
    if not same:
        mismatches += 1
    report.append(
        {
            "label": "标准输入",
            "options": [],
            "program": "{print $1}",
            "files": [],
            "mode": "bytes",
            "gawk_rc": g_rc,
            "ours_rc": o_rc,
            "gawk_out": g_text,
            "ours_out": o_text,
            "same": same,
        }
    )

    for item in report:
        flag = "OK  " if item["same"] else "DIFF"
        print(f"[{flag}] {item['label']}  选项={item['options']} 程序={item['program']}")
        if not item["same"]:
            print(f"        gawk rc={item['gawk_rc']} out={item['gawk_out']!r}")
            print(f"        ours rc={item['ours_rc']} out={item['ours_out']!r}")

    print(f"\n共 {len(report)} 组用例，不一致 {mismatches} 组")

    out_path = DATA / "diff_awk.json"
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("完整结果:", out_path)
    return 0 if mismatches == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
