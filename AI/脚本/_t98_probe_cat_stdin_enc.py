"""cat 教程第六轮探针：stdin 与文件路径的编码判定差异。

用法:
    python AI/脚本/_t98_probe_cat_stdin_enc.py

要确认的事:
    源码里 stdin 走的是 _emit_stream(_stdin_chunks(ctx), "utf-8", ...)，
    编码写死 utf-8；文件路径才走 _pick_encoding 的编码判定。
    所以同一份 GBK 内容，走文件会被解码成 UTF-8，走 stdin 不会。
    这是教程里必须写清的一条，写之前先实测。

产出:
    AI/数据/t98_cat_stdin_enc_report.txt
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "main.py"
OUT = ROOT / "AI" / "数据" / "t98_cat_stdin_enc_report.txt"

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)
    print(text)


def run(args: list[str], stdin: bytes = b"", cwd: Path | None = None) -> tuple[int, bytes, bytes]:
    proc = subprocess.run(
        [sys.executable, str(MAIN), *args],
        input=stdin,
        capture_output=True,
        cwd=str(cwd or ROOT),
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="t98stdin_"))
    gbk = "中文内容\n".encode("gb18030")
    gbk_file = tmp / "gbk.txt"
    gbk_file.write_bytes(gbk)

    say("=== 1. 同一份 GBK 字节，文件路径 vs stdin ===")
    say("  GBK 字节 = %r（%d 字节）" % (gbk, len(gbk)))

    code, out, err = run(["cat", str(gbk_file)])
    say("  走文件：")
    say("    exit=%d" % code)
    say("    stdout=%r" % out)
    say("    长度=%d（GBK 解码成 UTF-8，4 个汉字 = 12 字节 + 换行）" % len(out))

    code, out, err = run(["cat", "-"], stdin=gbk)
    say("  走 stdin：")
    say("    exit=%d" % code)
    say("    stdout=%r" % out)
    say("    长度=%d（编码写死 utf-8，解不出的字节用 surrogateescape 占位）" % len(out))
    say()

    say("=== 2. 源码依据 ===")
    say("  cat.py 里 stdin 分支：")
    say("    _emit_stream(_stdin_chunks(ctx), 'utf-8', options, state, ctx)")
    say("  文件分支：")
    say("    encoding = _pick_encoding(sample)")
    say("    _emit_stream(_chunks(handle), encoding, options, state, ctx)")
    say()

    say("=== 3. 走 stdin 时输出能否还原成原字节 ===")
    say("  stdout 按 utf-8 + surrogateescape 写回，字节守恒 = %s" % (out == gbk))
    say()

    say("=== 4. 走文件时字节数会变 ===")
    code, fout, err = run(["cat", str(gbk_file)])
    say("  文件路径输出长度 = %d" % len(fout))
    say("  stdin 输出长度   = %d" % len(out))
    say("  两者不同 = %s" % (len(fout) != len(out)))
    say()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes("\n".join(lines).encode("utf-8"))
    print()
    print("报告已写到 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
