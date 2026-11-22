"""w2l/parallel.py 的单元测试：分片规则与进程数解析。"""

import os

import pytest

from w2l.parallel import map_ordered, resolve_jobs, split_evenly


def test_resolve_jobs_keeps_positive_value():
    assert resolve_jobs(1) == 1
    assert resolve_jobs(4) == 4


def test_resolve_jobs_zero_means_cpu_count():
    assert resolve_jobs(0) == (os.cpu_count() or 1)


def test_resolve_jobs_rejects_negative():
    with pytest.raises(ValueError):
        resolve_jobs(-1)


def test_split_evenly_covers_all_items():
    items = list(range(10))
    chunks = split_evenly(items, 3)
    assert [item for chunk in chunks for item in chunk] == items
    assert len(chunks) == 3


def test_split_evenly_keeps_chunks_contiguous():
    items = list(range(10))
    chunks = split_evenly(items, 3)
    assert chunks[0] == [0, 1, 2, 3]
    assert chunks[1] == [4, 5, 6]
    assert chunks[2] == [7, 8, 9]


def test_split_evenly_sizes_differ_by_at_most_one():
    chunks = split_evenly(list(range(10)), 3)
    sizes = [len(chunk) for chunk in chunks]
    assert max(sizes) - min(sizes) <= 1
    assert sum(sizes) == 10


def test_split_evenly_drops_empty_chunks():
    chunks = split_evenly([1, 2], 8)
    assert chunks == [[1], [2]]


def test_split_evenly_handles_empty_input():
    assert split_evenly([], 4) == []


def _double(item):
    return item * 2


def test_map_ordered_serial_matches_parallel():
    items = list(range(20))
    assert map_ordered(_double, items, 1) == [item * 2 for item in items]
    assert map_ordered(_double, items, 4) == [item * 2 for item in items]


def test_map_ordered_preserves_input_order():
    """乱序耗时也要按输入顺序返回，否则并行输出无法与串行一致。"""
    items = list(range(30))
    assert map_ordered(_double, items, 8) == [item * 2 for item in items]


def test_map_ordered_with_single_item_stays_in_process():
    assert map_ordered(_double, [5], 4) == [10]
