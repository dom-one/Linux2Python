#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""取 GNU sed 4.9 上游源码，用来查清 `~` 地址的真实语义。

地址选择：deb.debian.org 的 pool 静态 tarball。
（sources.debian.org 的 /data/ 路径会撞 Varnish PoW 挑战页，
  raw.githubusercontent / mirrors.kernel.org / gitlab 都连不通。）

用法：python AI/脚本/_t1007_fetch_sed_src.py
产物：AI/数据/gnu_sed_src/ 下的源码
"""
from __future__ import annotations

import io
import sys
import tarfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEST = ROOT / "AI" / "数据" / "gnu_sed_src"

URLS = [
    "http://deb.debian.org/debian/pool/main/s/sed/sed_4.9.orig.tar.xz",
    "https://deb.debian.org/debian/pool/main/s/sed/sed_4.9.orig.tar.xz",
    "http://deb.debian.org/debian/pool/main/s/sed/sed_4.9.orig.tar.gz",
]

# 真源码的特征串（不能只判「是不是 HTML」——挑战页也是 HTML）
SOURCE_MARKERS = (b"#include", b"int main", b"sed_cmd", b"regexec")


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    blob = None
    for url in URLS:
        try:
            print(f"[try] {url}")
            with urllib.request.urlopen(url, timeout=60) as resp:
                data = resp.read()
            print(f"[ok]  {len(data)} 字节")
            blob = data
            break
        except Exception as exc:  # noqa: BLE001
            print(f"[fail] {type(exc).__name__}: {exc}")

    if blob is None:
        print("[result] 全部地址都失败")
        return 1

    mode = "r:xz" if blob[:6] == b"\xfd7zXZ\x00" else "r:gz"
    print(f"[info] tar 模式 {mode}")

    # 特征串要查**解压后**的内容，不能查压缩包本身
    # （上一版就是查压缩包，把正常的 xz 压缩包误判成「不是源码」）
    with tarfile.open(fileobj=io.BytesIO(blob), mode=mode) as tar:
        members = [m for m in tar.getmembers()
                   if m.isfile() and m.name.endswith((".c", ".h"))
                   and "/" in m.name]
        if not members:
            print("[result] tar 里没有 .c/.h 源文件，弃用")
            return 1
        hits = 0
        for member in members:
            src = tar.extractfile(member)
            if src is None:
                continue
            data = src.read()
            if any(marker in data for marker in SOURCE_MARKERS):
                hits += 1
        if hits == 0:
            print("[result] 解压后的源文件里一个特征串都没命中，弃用")
            print("[result] 前 200 字节:", blob[:200])
            return 1
        print(f"[info] {hits} 个文件命中源码特征串")

    with tarfile.open(fileobj=io.BytesIO(blob), mode=mode) as tar:
        members = [m for m in tar.getmembers()
                   if m.isfile() and m.name.endswith((".c", ".h"))
                   and "/" in m.name]
        for member in members:
            rel = member.name.split("/", 1)[1]
            target = DEST / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            src = tar.extractfile(member)
            if src is None:
                continue
            target.write_bytes(src.read())

    files = sorted(p for p in DEST.rglob("*") if p.is_file())
    print(f"[result] 解出 {len(files)} 个源文件到 {DEST}")
    for path in files:
        print(f"  {path.relative_to(DEST)}  {path.stat().st_size} 字节")
    return 0


if __name__ == "__main__":
    sys.exit(main())
