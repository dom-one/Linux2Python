"""下载 GNU tree 上游源码（Debian 打包版 2.1.0-1），用来核对 -P / -x / 链接的语义。

本机没有 GNU tree 可执行文件（Git Bash 只带 cmd 的 tree.exe，格式完全不同），
所以行为基线只能从上游源码逐行推演——这是 tick #7 立下的规矩。

地址说明（上一轮踩过的坑）：
- raw.githubusercontent.com / gitlab.com / ftp.gnu.org 都取不到（超时、404、Cloudflare 拦截）
- sources.debian.org 的 /data/ 路径可用，能直接拿到打包版源文件

产出：AI/数据/tree_src/ 下的 tree.c / list.c / unix.c / tree.h + fetch_log.txt

用法:
    python AI/脚本/_t927_fetch_tree_src_debian.py
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEST = ROOT / "AI" / "数据" / "tree_src"

BASE = "https://sources.debian.org/data/main/t/tree/2.1.0-1/"
WANTED = ("tree.c", "list.c", "unix.c", "tree.h")
TIMEOUT = 40


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    log: list[str] = []
    saved = 0
    for name in WANTED:
        url = BASE + name
        try:
            data = fetch(url)
        except Exception as exc:  # noqa: BLE001 - 取不到就记下来
            log.append("  取不到 %s：%r" % (url, exc))
            continue
        if b"<html" in data[:400].lower():
            log.append("  %s 返回的是 HTML，不是源码" % url)
            continue
        (DEST / name).write_bytes(data)
        log.append("  已保存 %s（%d 字节）" % (name, len(data)))
        saved += 1
    log.append("源码在 %s（%d/%d 个文件）" % (DEST, saved, len(WANTED)))
    (DEST / "fetch_log.txt").write_text("\n".join(log) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(log))


if __name__ == "__main__":
    main()
