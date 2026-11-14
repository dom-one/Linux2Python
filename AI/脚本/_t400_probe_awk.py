"""探针：实测 GNU awk 5.3.2 在本机的行为，作为 awk-lite 的对照基线。

只读探查，不改项目源码。产物落在 AI/数据/ 下。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "awk_probe"

AWK = shutil.which("awk") or shutil.which("gawk")
if AWK is None:
    raise SystemExit("本机找不到 awk 可执行文件")

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
    (tmp / "crlf.log").write_bytes(b"a b\r\nc d\r\n")
    (tmp / "blank.log").write_text("\n\nx y\n", encoding="utf-8")
    (tmp / "semi.log").write_text("a;b;c\nd;e;f\n", encoding="utf-8")


def run(cmd: list[str], cwd: Path, stdin_text: str | None = None) -> dict:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        input=stdin_text.encode("utf-8") if stdin_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "cmd": cmd,
        "rc": proc.returncode,
        "out": proc.stdout.decode("utf-8", "replace"),
        "err": proc.stderr.decode("utf-8", "replace"),
    }


CASES: list[list[str]] = [
    # 字段取值
    ["{print $1}"],
    ["{print $2}"],
    ["{print $NF}"],
    ["{print $0}"],
    ["{print}"],
    ["{print $1, $2}"],
    ["{print $1,$2}"],
    ["{print $3}"],
    # 变量
    ["{print NR}"],
    ["{print NF}"],
    ["{print FNR}"],
    ["{print NR, NF}"],
    ["{print NR, $0}"],
    # 模式
    ["/ERROR/"],
    ["/ERROR/ {print $1}"],
    ["/^ERROR/ {print $2}"],
    ["/ERROR/ {print}"],
    ["/nomatch/"],
    # 分隔符
    ["-F,", "{print $1}"],
    ["-F,", "{print $2}"],
    ["-F;", "{print $3}"],
    ["-F,", "{print $NF}"],
    ["-F:", "{print $1}"],
    # -v
    ["-v", "x=3", "{print $x}"],
    ["-v", "OFS=;", "{print $1, $2}"],
    ["-v", "s=ERROR", "{print $s}"],
    ["-v", "x=2", "-F,", "{print $x}"],
]

FILE_CASES: list[list[str]] = [
    ["{print $1}", "a.log"],
    ["{print $1}", "a.log", "b.log"],
    ["{print NR}", "a.log", "b.log"],
    ["{print FNR}", "a.log", "b.log"],
    ["{print $1}", "empty.log"],
    ["{print NF}", "blank.log"],
    ["{print $1}", "blank.log"],
    ["{print $1}", "crlf.log"],
    ["{print $1}", "nonexistent.log"],
    ["{print $1}", "a.log", "nonexistent.log"],
    ["{print $1}"],
]

ERROR_CASES: list[list[str]] = [
    [],
    ["{print $1"],
    ["{print"],
    ["{print $}"],
    ["{print $1+}"],
    ["{print 1 +}"],
    ["{foo}"],
    ["{print $1}"],  # 正常，作为对照
]


def main() -> int:
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)

    tmp = Path(tempfile.mkdtemp(prefix="awkprobe_", dir=str(DATA)))
    build_fixture(tmp)

    report: dict = {"cwd": str(tmp), "cases": []}

    for case in CASES:
        report["cases"].append(
            {"kind": "stdin", **run([AWK, *case], tmp, SAMPLE)}
        )

    for case in FILE_CASES:
        report["cases"].append({"kind": "file", **run([AWK, *case], tmp)})

    for case in ERROR_CASES:
        report["cases"].append({"kind": "error", **run([AWK, *case], tmp)})

    # stdin 显式传入
    report["cases"].append(
        {"kind": "stdin-explicit", **run([AWK], tmp, SAMPLE)}
    )

    out_path = DATA / "probe_awk.json"
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 人看的摘要
    for item in report["cases"]:
        print("=" * 60)
        print("CMD:", " ".join(item["cmd"]))
        print("RC :", item["rc"])
        if item["out"]:
            print("OUT:", repr(item["out"]))
        if item["err"]:
            print("ERR:", repr(item["err"]))

    print("\n完整结果:", out_path)
    print("临时目录:", tmp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
