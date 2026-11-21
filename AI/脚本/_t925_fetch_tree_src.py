"""下载 GNU tree 的上游源码，用来核对 -P / -x / 符号链接 / 统计行这几处语义。

本机没有 GNU tree 可执行文件（Git Bash 只带 cmd 的 tree.exe，格式完全不同），
所以行为基线只能从上游源码逐行推演——这是 tick #7 立下的规矩。

沿用 tick #7 已经验证过的取源地址（AI/脚本/_t121_fetch_tree_ref.py）：
- raw.githubusercontent.com/bminor/tree/master/（Debian 的 git 镜像，最稳）
- gitlab.com/OldManProgrammer/unix-tree/-/raw/master/
- raw.githubusercontent.com/tree/tree/master/

产出：AI/数据/tree_src/ 下的 tree.c / list.c / unix.c / color.c / tree.h

用法:
    python AI/脚本/_t925_fetch_tree_src.py
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEST = ROOT / "AI" / "数据" / "tree_src"

BASES = [
    "https://raw.githubusercontent.com/bminor/tree/master/",
    "https://gitlab.com/OldManProgrammer/unix-tree/-/raw/master/",
    "https://raw.githubusercontent.com/tree/tree/master/",
]

WANTED = ("tree.c", "list.c", "unix.c", "color.c", "tree.h")

TIMEOUT = 30


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    saved: set[str] = set()
    log: list[str] = []

    def note(text: str) -> None:
        log.append(text)
        print(text)

    for base in BASES:
        for name in WANTED:
            if name in saved:
                continue
            target = DEST / name
            if target.exists() and target.stat().st_size > 1000:
                note("  已存在，跳过：%s" % target)
                saved.add(name)
                continue
            try:
                data = fetch(base + name)
            except Exception as exc:  # noqa: BLE001 - 取不到就换下一个源
                note("  取不到 %s%s：%s" % (base, name, exc))
                continue
            if b"<html" in data[:200].lower():
                note("  %s%s 返回的是 HTML，不是源码" % (base, name))
                continue
            target.write_bytes(data)
            note("  已保存 %s（%d 字节）" % (name, len(data)))
            saved.add(name)
        if len(saved) == len(WANTED):
            break

    note("源码在 %s（%d/%d 个文件）" % (DEST, len(saved), len(WANTED)))
    (DEST / "fetch_log.txt").write_text("\n".join(log) + "\n", encoding="utf-8", newline="\n")

    if not saved:
        print("所有源都没取到，没有拿到上游源码")
        sys.exit(1)


if __name__ == "__main__":
    main()
