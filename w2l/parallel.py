"""分片并行执行：把一批任务分给多个工作进程，按输入顺序拿回结果。

设计取舍（写在这里，免得每个指令各想一遍）：

- **用 spawn 不用 fork**：Windows 上没有 fork；用默认上下文在部分平台上会
  走 fork，跨平台行为不一致，所以显式指定 spawn。spawn 的子进程要重新
  import 主模块，因此主入口必须有 `if __name__ == "__main__":` 守卫。
- **按输入顺序返回**：用 `imap` 而不是 `imap_unordered`，保证第 i 个任务的
  结果对应第 i 个输入。这样并行结果可以直接按顺序打印，输出与串行逐字节一致。
- **任务函数必须能 pickle**：只传路径、模式这类可 pickle 的数据，
  不要把文件句柄、打开的流塞进任务里。
- **jobs<=1 时不起进程**：直接在当前进程跑，避免无谓的进程启动开销。
"""

from __future__ import annotations

import multiprocessing
import os
from typing import Callable, Iterable, Sequence, TypeVar

T = TypeVar("T")
R = TypeVar("R")

__all__ = ["resolve_jobs", "map_ordered", "split_evenly"]


def resolve_jobs(value: int) -> int:
    """把 `--jobs` 的取值解析成实际进程数。

    `0` 表示按 CPU 核数自动决定；负数是用法错误。
    """
    if value < 0:
        raise ValueError("进程数不能为负数")
    if value == 0:
        return os.cpu_count() or 1
    return value


def split_evenly(items: Sequence[T], jobs: int) -> list[list[T]]:
    """把序列切成不超过 jobs 段、长度尽量相等的连续片段。

    用连续片段而不是交错分配，是为了保留遍历顺序：调用方按片段顺序输出，
    结果就与串行逐字节一致。各段长度相差不超过 1（余数分给靠前的段），
    片段数不超过 items 数，空片段直接丢掉。
    """
    total = len(items)
    if total == 0 or jobs <= 0:
        return []
    count = min(jobs, total)
    base, remainder = divmod(total, count)
    chunks: list[list[T]] = []
    start = 0
    for index in range(count):
        size = base + (1 if index < remainder else 0)
        chunks.append(list(items[start : start + size]))
        start += size
    return [chunk for chunk in chunks if chunk]


def map_ordered(
    func: Callable[[T], R],
    items: Iterable[T],
    jobs: int,
) -> list[R]:
    """并发执行 func，返回结果列表，顺序与 items 一致。

    jobs<=1 时就地串行执行（不起进程），结果与并发路径完全相同。
    """
    payload = list(items)
    if jobs <= 1 or len(payload) <= 1:
        return [func(item) for item in payload]

    context = multiprocessing.get_context("spawn")
    workers = min(jobs, len(payload))
    pool = context.Pool(processes=workers)
    try:
        return list(pool.imap(func, payload))
    finally:
        pool.terminate()
        pool.join()
