"""探针五：查 -n 与 -i 同时给时的先后顺序影响（mv 与 cp 各测一遍）。

上一轮探针发现 GNU mv 里 `-n -i` 会提示并照搬、`-i -n` 不提示也不搬，
看着像「最后一个选项生效」。但本项目的 cp 实现写的是「-n 压过 -i」，
两边必须对齐，所以把 cp 与 mv 的四种组合都实测一遍。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GNU_MV = shutil.which("mv")
GNU_CP = shutil.which("cp")


def run(tool: str, argv: list[str], stdin_text: str) -> dict:
    sandbox = Path(tempfile.mkdtemp(prefix="ni_"))
    (sandbox / "a.txt").write_bytes(b"NEW")
    (sandbox / "b.txt").write_bytes(b"OLD")
    proc = subprocess.run(
        [tool, *argv],
        cwd=str(sandbox),
        input=stdin_text.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    result = {
        "rc": proc.returncode,
        "out": proc.stdout.decode("utf-8", "replace"),
        "err": proc.stderr.decode("utf-8", "replace"),
        "a": (sandbox / "a.txt").read_bytes().decode() if (sandbox / "a.txt").exists() else "<gone>",
        "b": (sandbox / "b.txt").read_bytes().decode() if (sandbox / "b.txt").exists() else "<gone>",
    }
    shutil.rmtree(sandbox, ignore_errors=True)
    return result


def main() -> int:
    combos = [
        (["-n", "-i"], "先 -n 后 -i"),
        (["-i", "-n"], "先 -i 后 -n"),
        (["-n"], "只有 -n"),
        (["-i"], "只有 -i"),
    ]
    for tool_name, tool in (("mv", GNU_MV), ("cp", GNU_CP)):
        print("#" * 60)
        print("工具:", tool_name)
        for flags, label in combos:
            result = run(tool, [*flags, "a.txt", "b.txt"], "y\n")
            moved = result["b"] == "NEW"
            print(f"  {label:12s} 提示={'有' if result['err'].strip() else '无'} "
                  f"落地={'搬/拷过去了' if moved else '没动'} "
                  f"rc={result['rc']} a={result['a']!r} b={result['b']!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
