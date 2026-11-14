"""探针 2：查清 Windows Python 调 MSYS awk.exe 时程序参数的变形，以及 Git Bash 里的路径改写。

只读探查。产物落在 AI/数据/awk_probe/ 下。
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

PROGRAMS = [
    "{print}",
    "{ print }",
    "{print $0}",
    "{print;}",
    "{print $1}",
    "{$0=$0; print}",
    "/ERROR/ {print}",
    "/ERROR/{print}",
    "{print \"brace\"}",
    "{print $1} {print $2}",
]


def run(cmd: list[str]) -> dict:
    proc = subprocess.run(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "cmd": cmd[1:],
        "rc": proc.returncode,
        "out": proc.stdout.decode("utf-8", "replace"),
        "err": proc.stderr.decode("utf-8", "replace"),
    }


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    report = {"awk": AWK, "from_windows_python": []}

    for program in PROGRAMS:
        report["from_windows_python"].append(run([AWK, program]))

    for item in report["from_windows_python"]:
        print("=" * 60)
        print("PROG:", item["cmd"][0])
        print("RC  :", item["rc"])
        print("OUT :", repr(item["out"]))
        print("ERR :", repr(item["err"]))

    out_path = DATA / "probe_awk_argv.json"
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n完整结果:", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
