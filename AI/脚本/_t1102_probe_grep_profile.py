"""并行搜索：串行耗时到底花在哪。

基线探针测出本项目 grep -r 在 912 个小文件上要 24.4 秒，而 GNU grep 只要 0.11 秒。
这一轮把 24.4 秒拆开：目录遍历、读字节、编码判定、正则匹配各占多少。

判据用现算的耗时占比，不靠猜。
"""

from __future__ import annotations

import io
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "AI" / "数据" / "grep_parallel"
REPORT = DATA / "profile.txt"

sys.path.insert(0, str(ROOT))

from w2l.commands.grep import _candidate_encodings, _decode_sample, _detect_encoding, _text_score  # noqa: E402


def main() -> int:
    tree = DATA / "tree"
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(tree):
        dirnames.sort()
        for name in sorted(filenames):
            files.append(os.path.join(dirpath, name))

    lines: list[str] = []

    def say(text: str) -> None:
        lines.append(text)
        print(text)

    say(f"files={len(files)}")

    # ① 纯遍历（不读内容）
    start = time.perf_counter()
    for _ in files:
        pass
    say(f"01 遍历骨架        : {time.perf_counter() - start:.3f}s")

    # ② 只读字节
    start = time.perf_counter()
    samples = []
    for path in files:
        with open(path, "rb") as handle:
            samples.append(handle.read(8192))
    say(f"02 读字节          : {time.perf_counter() - start:.3f}s")

    # ③ 只做编码判定
    start = time.perf_counter()
    encodings = []
    for sample in samples:
        encodings.append(_detect_encoding(sample))
    say(f"03 编码判定        : {time.perf_counter() - start:.3f}s")

    # ④ 编码判定内部：候选表 / 解码 / 打分 各占多少
    start = time.perf_counter()
    for _ in files:
        _candidate_encodings()
    say(f"04 候选表          : {time.perf_counter() - start:.3f}s")

    sample = samples[0]
    start = time.perf_counter()
    for _ in range(len(files)):
        for enc in ("utf-8", "cp1252", "gb18030", "latin-1"):
            _decode_sample(sample, enc)
    say(f"05 解码 4 候选     : {time.perf_counter() - start:.3f}s")

    text = _decode_sample(sample, "utf-8") or ""
    start = time.perf_counter()
    for _ in range(len(files)):
        _text_score(text)
    say(f"06 文本打分(单候选): {time.perf_counter() - start:.3f}s  样本文本长度={len(text)}")

    # ⑤ 正则匹配（全部行）
    regex = re.compile("ERROR")
    start = time.perf_counter()
    hits = 0
    for sample in samples:
        hits += len(regex.findall(sample.decode("utf-8", errors="replace")))
    say(f"07 正则匹配        : {time.perf_counter() - start:.3f}s  hits={hits}")

    DATA.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"\nreport -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
