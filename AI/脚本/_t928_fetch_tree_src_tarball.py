"""下载 GNU tree 上游源码（2.1.0），用来核对 -P / -x / 链接的语义。

本机没有 GNU tree 可执行文件（Git Bash 只带 cmd 的 tree.exe，格式完全不同），
所以行为基线只能从上游源码逐行推演——这是 tick #7 立下的规矩。

地址说明（历轮踩过的坑）：
- raw.githubusercontent.com / gitlab.com / ftp.gnu.org：超时、404、Cloudflare 拦截
- sources.debian.org/data/：web_fetch 能读，但 urllib 直连会撞上 Varnish PoW 挑战页
- deb.debian.org 的 pool 是静态文件服务器，直接拿 orig tarball 最稳

校验：HTML 挑战页四个文件都是 3319 字节，所以不能只看「有没有 HTML」，
必须查真正源码里才有的特征串（#include / int main / make_directory）。

产出：AI/数据/tree_src/ 下的 tree.c / list.c / unix.c / tree.h + fetch_log.txt

用法:
    python AI/脚本/_t928_fetch_tree_src_tarball.py
"""

from __future__ import annotations

import io
import tarfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEST = ROOT / "AI" / "数据" / "tree_src"

TARBALLS = [
    "http://deb.debian.org/debian/pool/main/t/tree/tree_2.1.0.orig.tar.gz",
    "https://deb.debian.org/debian/pool/main/t/tree/tree_2.1.0.orig.tar.gz",
    "http://ftp.debian.org/debian/pool/main/t/tree/tree_2.1.0.orig.tar.gz",
]
# tarball 里源码在 tree-2.1.0/ 下
WANTED = ("tree.c", "list.c", "unix.c", "tree.h")
# 真源码里一定有的特征串，用来把 PoW 页 / 错误页挡掉
MARKERS = ("#include", "int main", "make_directory")
TIMEOUT = 60


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def looks_like_source(data: bytes) -> bool:
    head = data[:4000].decode("utf-8", "replace")
    if "<!DOCTYPE html" in head or "<html" in head.lower():
        return False
    return any(marker in head for marker in MARKERS)


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    log: list[str] = []
    # 先清掉上一轮留下的坏文件（PoW 挑战页），避免失败时留下假源码
    for name in WANTED:
        stale = DEST / name
        if stale.exists():
            stale.unlink()
            log.append("  清掉旧文件 %s" % name)

    blob = None
    for url in TARBALLS:
        try:
            blob = fetch(url)
        except Exception as exc:  # noqa: BLE001 - 换下一个源
            log.append("  取不到 %s：%r" % (url, exc))
            continue
        log.append("  拿到 %s（%d 字节）" % (url, len(blob)))
        if blob[:2] == b"\x1f\x8b":
            break
        blob = None

    if blob is None:
        log.append("所有 tarball 地址都没取到")
    else:
        try:
            with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
                for name in WANTED:
                    member = None
                    for candidate in tar.getmembers():
                        if candidate.name.endswith("/" + name) and candidate.isfile():
                            member = candidate
                            break
                    if member is None:
                        log.append("  tarball 里没有 %s" % name)
                        continue
                    data = tar.extractfile(member).read()
                    if not looks_like_source(data):
                        log.append("  %s 内容不像源码，丢弃" % name)
                        continue
                    (DEST / name).write_bytes(data)
                    log.append("  已保存 %s（%d 字节）" % (name, len(data)))
        except Exception as exc:  # noqa: BLE001
            log.append("  解包失败：%r" % (exc,))

    saved = sum(1 for name in WANTED if (DEST / name).exists() and (DEST / name).stat().st_size > 5000)
    log.append("源码在 %s（%d/%d 个文件）" % (DEST, saved, len(WANTED)))
    (DEST / "fetch_log.txt").write_text("\n".join(log) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(log))


if __name__ == "__main__":
    main()
