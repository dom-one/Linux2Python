"""cat 教程第五轮探针：8192 嗅探上限的真实后果、GNU 退出码差异。

用法:
    python AI/脚本/_t99_probe_cat_tail.py

要钉死两件事:
1. 8192 嗅探上限：文件头是纯 ASCII、GBK 中文在尾部时会发生什么
2. GNU cat 与本项目在错误路径上的退出码差��（GNU 1 / 本项目 2）
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "main.py"
OUT = ROOT / "AI" / "数据" / "t99_cat_tail_report.txt"
BASH = r"E:\software\Git\Git\bin\bash.exe"

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
    sys.path.insert(0, str(ROOT))
    from w2l.commands.cat import _SNIFF_SIZE, _pick_encoding

    tmp = Path(tempfile.mkdtemp(prefix="t99cat_"))

    say("=== 1. 嗅探上限的真实后果 ===")
    say("  构造：8192 字节纯 ASCII 头 + GBK 中文尾")
    head = b"A" * _SNIFF_SIZE + b"\n"
    tail = "中文\n".encode("gb18030")
    payload = head + tail
    say("  样本（前 8192 字节）判成 %r" % _pick_encoding(payload[:_SNIFF_SIZE]))
    say("  → 整份文件按 utf-8 解，尾部的 GBK 字节解不出，走 surrogateescape")
    code, out, err = run(["cat", "-"], stdin=payload)
    say("  输出长度 = %d，输入长度 = %d" % (len(out), len(payload)))
    say("  输出末 12 字节 = %r" % out[-12:])
    say("  字节数守恒 = %s" % (len(out) == len(payload)))
    say()

    say("  对照：同样的 GBK 中文放在文件头（样本里就能看到）")
    payload2 = tail + b"A" * _SNIFF_SIZE + b"\n"
    say("  样本判成 %r" % _pick_encoding(payload2[:_SNIFF_SIZE]))
    code, out, err = run(["cat", "-"], stdin=payload2)
    say("  输出长度 = %d（UTF-8 编码变长）" % len(out))
    say("  输出前 12 字节 = %r" % out[:12])
    say("  → 中文被正确解码成 UTF-8，字节数从 6 变 9")
    say()

    say("=== 2. 错误路径的退出码：GNU 1 / 本项目 2 ===")
    missing = tmp / "nope.txt"
    (tmp / "ok.txt").write_bytes(b"fine\n")
    for argv in (["cat", str(missing)], ["cat", str(tmp)]):
        gnu = subprocess.run(
            [BASH, "-c", "cd %s && cat %s" % (tmp.as_posix(), argv[1].replace("\\", "/"))],
            capture_output=True,
        )
        ours = run(argv, cwd=tmp)
        say("  $ cat %s" % argv[1])
        say("    GNU    exit=%d stderr=%r" % (gnu.returncode, gnu.stderr))
        say("    本项目 exit=%d stderr=%r" % (ours[0], ours[2]))
        say()

    say("=== 3. 存在文件时 GNU 的退出码 ===")
    gnu = subprocess.run(
        [BASH, "-c", "cd %s && cat ok.txt" % tmp.as_posix()],
        capture_output=True,
    )
    ours = run(["cat", str(tmp / "ok.txt")], cwd=tmp)
    say("  GNU exit=%d  本项目 exit=%d" % (gnu.returncode, ours[0]))
    say()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes("\n".join(lines).encode("utf-8"))
    print()
    print("报告已写到 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
