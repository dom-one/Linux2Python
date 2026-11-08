"""复算 teach/21 草稿里那些「只有正文、没有命令块佐证」的数字。

用法:
    python AI/脚本/_t104_verify_cat_tut_claims.py

产出:
    AI/数据/t104_cat_tut_claims.txt

这些数字核对器查不到——核对器只比对命令块与预期输出块，
正文里的表格和断言得单独复算：

1. 草稿说纯 ASCII 文件的文本得分是 0.9583，得确认是哪个样本算出来的
2. 草稿说 b"\\x80\\xa0\\xff\\n" 只有 latin-1 能解，gb18030 也解不出
3. 草稿说全 256 字节二进制文件透传后仍是 256 字节、首尾一致
4. 草稿说 printf 'a\\n\\r\\n\\r\\nb\\n' 走 cat -b - 给出 4 个行号
5. 草稿说 GBK 演示文件是「4 个汉字 + 2 个汉字 = 6 个汉字」，得数一遍真实汉字数
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "main.py"
BASH = Path(r"E:\software\Git\Git\bin\bash.exe")
OUT = ROOT / "AI" / "数据" / "t104_cat_tut_claims.txt"

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)
    print(text)


def run_bash(command: str) -> bytes:
    proc = subprocess.run([str(BASH), "-c", command],
                          capture_output=True, cwd=str(ROOT))
    return proc.stdout + proc.stderr


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from w2l.commands.cat import (  # noqa: E402
        _candidate_encodings,
        _detect_encoding,
        _is_text,
        _pick_encoding,
        _text_score,
    )

    say("=== 1. 纯 ASCII 样本的文本得分 ===")
    say("  候选编码: %r" % (_candidate_encodings(),))
    for sample in (b"hello world\n", b"hello\n", b"abc\n", b"a\n"):
        scores = {}
        for enc in _candidate_encodings():
            try:
                text = sample.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
            scores[enc] = _text_score(text)
        say("  样本 %r" % sample)
        for enc, score in scores.items():
            say("    %-10s 得分 %.6f" % (enc, score))
        say("    判定编码: %s" % _detect_encoding(sample))
    say()

    say("=== 2. 高位字节样本 b'\\x80\\xa0\\xff\\n' ===")
    sample = b"\x80\xa0\xff\n"
    for enc in _candidate_encodings():
        try:
            text = sample.decode(enc)
        except (UnicodeDecodeError, LookupError) as exc:
            say("  %-10s 解不出: %s" % (enc, type(exc).__name__))
            continue
        say("  %-10s 解出 %r（得分 %.4f）" % (enc, text, _text_score(text)))
    say("  _is_text 判定: %s" % _is_text(sample))
    say("  _pick_encoding 判定: %s" % _pick_encoding(sample))
    say()

    say("=== 3. 全 256 字节二进制文件透传 ===")
    blob = bytes(range(256))
    proc = subprocess.run([sys.executable, str(MAIN), "cat", "-"],
                          input=blob, capture_output=True, cwd=str(ROOT))
    say("  源文件 %d 字节，输出 %d 字节" % (len(blob), len(proc.stdout)))
    say("  逐字节相同: %s" % (proc.stdout == blob))
    say("  首字节 %r / 末字节 %r" % (proc.stdout[:1], proc.stdout[-1:]))
    say("  源文件首字节 %r / 末字节 %r" % (blob[:1], blob[-1:]))
    say()

    say("=== 4. cat -b - 对 CRLF 空行的编号 ===")
    payload = b"a\n\r\n\r\nb\n"
    proc = subprocess.run([sys.executable, str(MAIN), "cat", "-b", "-"],
                          input=payload, capture_output=True, cwd=str(ROOT))
    say("  输入字节: %r" % payload)
    say("  输出: %r" % proc.stdout)
    say("  输出行数: %d" % len(proc.stdout.splitlines()))
    say()

    say("=== 5. GBK 演示文件的真实汉字数 ===")
    gbk = ROOT / "AI" / "数据" / "gbk_demo.txt"
    if gbk.is_file():
        raw = gbk.read_bytes()
        say("  原始 %d 字节" % len(raw))
        try:
            text = raw.decode("gb18030")
            say("  gb18030 解码: %r" % text)
            han = [c for c in text if c.strip()]
            say("  非空白字符数: %d" % len(han))
            say("  逐字: %s" % " ".join(han))
            say("  换行数: %d" % text.count("\n"))
            say("  汉字字节数 = %d，总字节 = %d" % (len(han) * 2, len(raw)))
        except UnicodeDecodeError as exc:
            say("  gb18030 解不出: %s" % exc)
        say("  走文件路径后的输出字节数: %d"
            % len(subprocess.run([sys.executable, str(MAIN), "cat", str(gbk)],
                                  capture_output=True, cwd=str(ROOT)).stdout))
    else:
        say("  演示文件不存在")
    say()

    say("=== 6. 与 GNU cat 对照：源文件原样透传 ===")
    if gbk.is_file():
        say("  GNU cat 直接读文件:")
        for row in run_bash("cat AI/数据/gbk_demo.txt | od -c").decode(
                "utf-8", errors="replace").splitlines():
            say("    %s" % row)
    say()

    OUT.write_bytes("\n".join(lines).encode("utf-8"))
    print()
    print("报告已写到 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
