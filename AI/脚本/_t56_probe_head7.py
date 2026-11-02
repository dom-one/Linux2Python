"""探针第七轮：用 /dev/zero + wc -c 量大后缀，不往内存里灌 GB 级数据。

同时补测 mB / bB / PB / EB / ZB 等没测过的组合。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

GNU_HEAD = r"C:\Program Files\Git\usr\bin\head.exe"
GNU_WC = r"C:\Program Files\Git\usr\bin\wc.exe"
GNU_CAT = r"C:\Program Files\Git\usr\bin\cat.exe"


def locate(name: str, fallback: str) -> str:
    candidate = shutil.which(name)
    if candidate and "System32" not in candidate:
        return candidate
    return fallback


def measure(suffix: str) -> tuple[str, str]:
    """返回 (状态, 说明)。状态为「字节数」或错误原文。"""
    spec = f"1{suffix}"
    head = locate("head", GNU_HEAD)
    cat = locate("cat", GNU_CAT)
    wc = locate("wc", GNU_WC)
    # cat /dev/zero | head -c <spec> | wc -c
    p1 = subprocess.Popen([cat, "/dev/zero"], stdout=subprocess.PIPE)
    p2 = subprocess.Popen([head, "-c", spec], stdin=p1.stdout, stdout=subprocess.PIPE)
    p1.stdout.close()
    p3 = subprocess.Popen([wc, "-c"], stdin=p2.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p2.stdout.close()
    out, err = p3.communicate()
    if p2.wait() != 0:
        return "错误", err.decode("utf-8", "replace").strip() or f"head 退出码 {p2.returncode}"
    return "字节数", out.decode("ascii", "replace").strip()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"{'规格':<8}{'状态':<8}说明")
    for suffix in [
        "k", "K", "m", "M", "G", "T", "P", "E",
        "kB", "KB", "mB", "MB", "GB", "TB", "PB", "EB", "bB",
        "KiB", "MiB", "GiB", "TiB", "PiB", "EiB",
    ]:
        state, detail = measure(suffix)
        if state == "字节数":
            note = ""
            for label, value in (
                ("1000", 1000), ("1024", 1024),
                ("1000^2", 1000**2), ("1024^2", 1024**2),
                ("1000^3", 1000**3), ("1024^3", 1024**3),
                ("1000^4", 1000**4), ("1024^4", 1024**4),
                ("1000^5", 1000**5), ("1024^5", 1024**5),
                ("1000^6", 1000**6), ("1024^6", 1024**6),
            ):
                if detail == str(value):
                    note = f"= {label}"
                    break
            print(f"{'1'+suffix:<8}{state:<8}{detail}  {note}")
        else:
            print(f"{'1'+suffix:<8}{state:<8}{detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
