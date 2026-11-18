"""取证二：把 C:\\ 与 E:\\ 上「窗口内被改属性」的文件全量扫出来。

_t702 只抽样了 System32 / Program Files 的顶层，这轮做全量：
MSYS 的 chmod 755 唯一的副作用是把只读属性清掉，
所以只要找出 ChangeTime 落在探针窗口内的文件，就能圈定影响面。

结果写进 AI/数据/chmod_forensics2_report.txt。
"""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
REPORT = AI_DIR / "数据" / "chmod_forensics2_report.txt"

WINDOW_START = 1795024950.0
WINDOW_END = 1795025200.0
FILETIME_EPOCH_DELTA = 11644473600.0
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class FILE_BASIC_INFO(ctypes.Structure):
    _fields_ = [
        ("CreationTime", wintypes.LARGE_INTEGER),
        ("LastAccessTime", wintypes.LARGE_INTEGER),
        ("LastWriteTime", wintypes.LARGE_INTEGER),
        ("ChangeTime", wintypes.LARGE_INTEGER),
        ("FileAttributes", wintypes.DWORD),
    ]


kernel32.GetFileInformationByHandleEx.argtypes = [
    wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
]
kernel32.GetFileInformationByHandleEx.restype = wintypes.BOOL


def change_time(path: str) -> float | None:
    handle = kernel32.CreateFileW(path, 0x80000000, 0x7, None, 3, 0x02000000, None)
    if handle == INVALID_HANDLE_VALUE or handle is None:
        return None
    try:
        info = FILE_BASIC_INFO()
        if not kernel32.GetFileInformationByHandleEx(handle, 0, ctypes.byref(info), ctypes.sizeof(info)):
            return None
        return info.ChangeTime / 10_000_000.0 - FILETIME_EPOCH_DELTA
    finally:
        kernel32.CloseHandle(handle)


def scan(root: str, budget: float) -> tuple[int, list[str], bool]:
    started = time.time()
    total = 0
    touched: list[str] = []
    stack = [root]
    while stack:
        if time.time() - started > budget:
            return total, touched, True
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                    continue
            except OSError:
                continue
            total += 1
            changed = change_time(entry.path)
            if changed is not None and WINDOW_START <= changed <= WINDOW_END:
                touched.append(entry.path)
    return total, touched, False


def main() -> int:
    out: list[str] = []
    targets = [
        (r"C:\Windows", 150.0),
        (r"C:\Program Files (x86)", 60.0),
        (r"C:\Users", 60.0),
        (r"E:\software", 60.0),
    ]
    for root, budget in targets:
        started = time.time()
        total, touched, truncated = scan(root, budget)
        out.append(
            f"{root}: 扫描 {total} 个文件，用时 {time.time() - started:.0f}s，"
            f"窗口内被改 {len(touched)} 个{'（超时截断）' if truncated else ''}"
        )
        for item in touched[:40]:
            out.append(f"    {item}")
        out.append("")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"报告已写入 {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
