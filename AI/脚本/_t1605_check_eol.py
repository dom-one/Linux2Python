"""检查相关文件的行尾风格与 HEAD 里的 blob 是否一致。

拆分提交要用 git show 取出 HEAD 版本再写回工作区，Windows 上
Path.write_text 默认把 \\n 翻成 \\r���，一写整份文件就变成一次全文件改动。
所以动手前先确认：HEAD 里的 blob 是什么行尾，工作区现在是什么行尾。

用法：python AI/脚本/_t1605_check_eol.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = (
    "w2l/commands/ls.py",
    "tests/test_ls.py",
    "README.md",
    "w2l/jsonout.py",
    "tests/test_jsonout.py",
)


def eol_of(data: bytes) -> str:
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    if crlf and lf:
        return f"混合（CRLF {crlf} / LF {lf}）"
    if crlf:
        return f"CRLF（{crlf}）"
    if lf:
        return f"LF（{lf}）"
    return "无换行"


def main() -> int:
    print(f"{'文件':<28}{'HEAD blob':<24}{'工作区':<24}")
    print("-" * 76)
    for rel in TARGETS:
        try:
            blob = subprocess.run(
                ["git", "show", f"HEAD:{rel}"],
                cwd=str(ROOT),
                capture_output=True,
                check=True,
            ).stdout
            head_eol = eol_of(blob)
        except subprocess.CalledProcessError:
            head_eol = "（新文件，HEAD 没有）"
        path = ROOT / rel
        work_eol = eol_of(path.read_bytes()) if path.exists() else "（文件不存在）"
        print(f"{rel:<28}{head_eol:<24}{work_eol:<24}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
