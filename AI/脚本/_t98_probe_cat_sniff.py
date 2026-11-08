"""cat 教程第四轮探针：python -c 演示命令、8192 嗅探上限、候选编码的机器差异。

用法:
    python AI/脚本/_t98_probe_cat_sniff.py

产出:
    AI/数据/t98_cat_sniff_report.txt

要确认三件事:
1. 教程里要用的 python -c 演示命令能真跑通（核对器会在 Git Bash 里跑它）
2. _SNIFF_SIZE=8192 的真实后果：NUL 出现在 8192 字节之后会怎样
3. _candidate_encodings 在不同 locale 下的差别（源码注释提到 cp1252）
"""

from __future__ import annotations

import locale
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "main.py"
OUT = ROOT / "AI" / "数据" / "t98_cat_sniff_report.txt"
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
    from w2l.commands.cat import _SNIFF_SIZE, _candidate_encodings, _pick_encoding

    say("=== 1. 本机 locale ===")
    say("  locale.getpreferredencoding(False) = %r" % locale.getpreferredencoding(False))
    say("  _candidate_encodings() = %r" % (_candidate_encodings(),))
    say("  _SNIFF_SIZE = %d" % _SNIFF_SIZE)
    say()

    say("=== 2. 8192 嗅探上限 ===")
    say("  读文件头 8192 字节判断是否含 NUL。NUL 在 8192 之后 → 判成文本。")
    # 前 8192 字节全是 ASCII，第 8193 字节放 NUL
    payload = b"A" * _SNIFF_SIZE + b"\x00" + b"B" * 16 + b"\n"
    say("  构造文件：8192 个 'A' + NUL + 16 个 'B'")
    say("  _pick_encoding(样本) = %r" % _pick_encoding(payload[:_SNIFF_SIZE]))
    say("  → 判成文本，会按 utf-8 严格解码")
    code, out, err = run(["cat", "-"], stdin=payload)
    say("  实际输出长度 = %d" % len(out))
    say("  输出里含 NUL = %s" % (b"\x00" in out))
    say("  输出后 20 字节 = %r" % out[-20:])
    say("  exit=%d" % code)
    say()

    say("=== 3. NUL 在样本内 → 二进制 ===")
    payload2 = b"A" * 100 + b"\x00" + b"B" * 16 + b"\n"
    say("  _pick_encoding = %r" % _pick_encoding(payload2[:_SNIFF_SIZE]))
    code, out, err = run(["cat", "-"], stdin=payload2)
    say("  输出长度 = %d（与输入同长）" % len(out))
    say("  逐字节相同 = %s" % (out == payload2))
    say()

    say("=== 4. 教程要用的 python -c 演示命令（在 Git Bash 里跑）===")
    demos = [
        (
            "看候选编码",
            'python -c "from w2l.commands.cat import _candidate_encodings;print(_candidate_encodings())"',
        ),
        (
            "看 GBK 字节的评分对比",
            'python -c "from w2l.commands.cat import _text_score;print(_text_score(\'中文内容\'), _text_score(\'ÖÐÎÄÄÚÈÝ\'))"',
        ),
        (
            "看 _pick_encoding 的判定",
            'python -c "from w2l.commands.cat import _pick_encoding;print(_pick_encoding(\'中文内容\'.encode(\'gb18030\')))"',
        ),
        (
            "看 NUL 判定",
            'python -c "from w2l.commands.cat import _pick_encoding;print(_pick_encoding(b\'a\\x00b\'))"',
        ),
    ]
    for title, cmd in demos:
        proc = subprocess.run([BASH, "-c", cmd], capture_output=True, cwd=str(ROOT))
        say("  %s" % title)
        say("    $ %s" % cmd)
        say("    -> %r (exit=%d)" % (proc.stdout, proc.returncode))
        if proc.stderr:
            say("    stderr=%r" % proc.stderr)
    say()

    say("=== 5. 候选编码在别的 locale 下会变 ===")
    say("  源码注释说「英文 Windows 上首选编码是 cp1252」，")
    say("  那时候候选列表会多一个 cp1252。本机开了 PYTHONUTF8=1，所以首选是 utf-8。")
    for env_val in ("0", "1"):
        env = {"PYTHONUTF8": env_val, "PATH": "/usr/bin:/bin:/mingw64/bin"}
        proc = subprocess.run(
            [sys.executable, "-c",
             "import locale;print(locale.getpreferredencoding(False))"],
            capture_output=True,
            env={**dict(__import__("os").environ), **env},
        )
        say("  PYTHONUTF8=%s -> preferred=%r" % (env_val, proc.stdout.strip()))
    say()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes("\n".join(lines).encode("utf-8"))
    print()
    print("报告已写到 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
