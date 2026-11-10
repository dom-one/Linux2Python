"""拉取 GNU tree 上游源码，作为本轮实现 tree 指令的行为参考。

只下载、不改项目文件。产物落在 AI/数据/tree_ref/ 下，纯文本。

上游地址按顺序尝试，第一个能取到内容的就用它：
- gitlab.com/OldManProgrammer/unix-tree（现行上游，tree 2.3.x）
- github.com/tree/tree（老仓库，tree 2.0.x）

用法：python AI/脚本/_t121_fetch_tree_ref.py
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT_DIR = ROOT / "AI" / "数据" / "tree_ref"

SOURCES = [
    "https://gitlab.com/OldManProgrammer/unix-tree/-/raw/master/",
    "https://raw.githubusercontent.com/tree/tree/master/",
    "https://raw.githubusercontent.com/bminor/tree/master/",
]

FILES = ["tree.c", "tree.h", "indented.c", "list.c", "hash.c", "parse.c", "unix.c", "file.c", "color.c", "html.c"]

TIMEOUT = 30


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    saved: set[str] = set()
    for base in SOURCES:
        for name in FILES:
            if name in saved:
                continue
            target = OUT_DIR / name
            if target.exists() and target.stat().st_size > 1000:
                print(f"已存在，跳过：{target}")
                saved.add(name)
                continue
            try:
                data = fetch(base + name)
            except Exception as exc:  # noqa: BLE001 - 取不到就换下一个源
                print(f"取不到 {base}{name}：{exc}")
                continue
            if b"<html" in data[:200].lower():
                print(f"{base}{name} 返回的是 HTML，不是源码")
                continue
            target.write_bytes(data)
            print(f"已保存 {target}（{len(data)} 字节）")
            saved.add(name)
        if len(saved) >= len(FILES):
            break

    if not saved:
        print("全部源都没取到源码")
        return 1
    print(f"共取到 {len(saved)} 个文件：{sorted(saved)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
