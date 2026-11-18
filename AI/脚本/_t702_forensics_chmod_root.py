"""取证：查 chmod -R 755 / 到底改到了哪些文件。

探针二里有一条 `chmod -R 755 /`，在 MSYS 上 / 指向 Git 安装根目录，
而 MSYS 的 chmod 只会「清只读属性 / 设只读属性」，755 带写位所以是清只读。
需要确认遍历范围：改到了 Git 安装目录？C:\\？更深的盘？

判据：改属性会更新 NTFS 的 ChangeTime（MFT 变更时间），
按 ChangeTime 落在探针窗口内的文件计数即可圈定范围。

结果写进 AI/数据/chmod_forensics_report.txt。
"""

from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
REPORT = AI_DIR / "数据" / "chmod_forensics_report.txt"

# 探针运行窗口（epoch 秒）：任务 02:03:30 起，02:04:57 被取消
WINDOW_START = 1795024950.0
WINDOW_END = 1795025200.0

FILETIME_EPOCH_DELTA = 11644473600.0  # 1601-01-01 到 1970-01-01 的秒差
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
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.c_void_p,
    wintypes.DWORD,
]
kernel32.GetFileInformationByHandleEx.restype = wintypes.BOOL


def change_time(path: str) -> tuple[float, int] | None:
    """取文件的 ChangeTime（秒）与属性位。失败返回 None。"""
    handle = kernel32.CreateFileW(
        path,
        0x80000000,  # FILE_READ_ATTRIBUTES
        0x7,  # FILE_SHARE_READ|WRITE|DELETE
        None,
        3,  # OPEN_EXISTING
        0x02000000,  # FILE_FLAG_BACKUP_SEMANTICS（目录也要）
        None,
    )
    if handle == INVALID_HANDLE_VALUE or handle is None:
        return None
    try:
        info = FILE_BASIC_INFO()
        ok = kernel32.GetFileInformationByHandleEx(
            handle, 0, ctypes.byref(info), ctypes.sizeof(info)
        )
        if not ok:
            return None
        seconds = info.ChangeTime / 10_000_000.0 - FILETIME_EPOCH_DELTA
        return seconds, info.FileAttributes
    finally:
        kernel32.CloseHandle(handle)


def scan(root: str, max_files: int = 200_000, max_seconds: float = 90.0) -> dict:
    """遍历 root，统计 ChangeTime 落在窗口内的文件。"""
    started = time.time()
    total = 0
    touched = 0
    readonly_cleared = 0
    samples: list[str] = []
    readonly_now = 0
    stack = [root]
    while stack:
        if total >= max_files or time.time() - started > max_seconds:
            break
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            if total >= max_files or time.time() - started > max_seconds:
                break
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                    continue
            except OSError:
                continue
            total += 1
            info = change_time(entry.path)
            if info is None:
                continue
            changed, attributes = info
            if attributes & 0x1:  # FILE_ATTRIBUTE_READONLY
                readonly_now += 1
            if WINDOW_START <= changed <= WINDOW_END:
                touched += 1
                if len(samples) < 12:
                    stamp = time.strftime("%H:%M:%S", time.localtime(changed))
                    samples.append(f"{entry.path} (change {stamp}, readonly={bool(attributes & 0x1)})")
    return {
        "root": root,
        "scanned": total,
        "touched": touched,
        "readonly_now": readonly_now,
        "samples": samples,
        "truncated": total >= max_files or time.time() - started > max_seconds,
    }


def main() -> int:
    out: list[str] = []
    out.append("=== 探针窗口 ===")
    out.append(
        f"  {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(WINDOW_START))}"
        f" ~ {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(WINDOW_END))}"
    )
    out.append("")

    out.append("=== MSYS 根目录下的盘符挂载点 ===")
    for name in ("c", "d", "e"):
        candidate = Path(rf"E:\software\Git\Git\{name}")
        out.append(f"  {candidate} 存在={candidate.exists()}")
    out.append("")

    out.append("=== 扫描 ===")
    targets = [
        (r"E:\software\Git\Git", 200_000, 90.0),
        (r"E:\software\Git\Git\mingw64\bin", 20_000, 20.0),
        (r"C:\Windows\System32", 20_000, 25.0),
        (r"C:\Program Files", 30_000, 30.0),
        (r"E:\1\NULL\Windows-to-Linux", 50_000, 25.0),
    ]
    for root, max_files, max_seconds in targets:
        result = scan(root, max_files, max_seconds)
        out.append(
            f"  {result['root']}: 扫描 {result['scanned']} 个文件，"
            f"窗口内被改 {result['touched']} 个，当前只读 {result['readonly_now']} 个"
            f"{'（扫描被截断）' if result['truncated'] else ''}"
        )
        for sample in result["samples"]:
            out.append(f"      {sample}")
        out.append("")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"报告已写入 {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
