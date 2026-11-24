"""布尔选项的先后顺序：GNU 的互斥选项是「后给的那个赢」。

`-i`（交互）与 `-n`（不覆盖）互斥：给 `-i` 会清掉 `-n`，给 `-n` 会清掉 `-i`，
谁最后出现谁生效（GNU coreutils 8.32 的 cp 与 mv 实测一致）：

    cp -n -i a b   -> 提问并照搬
    cp -i -n a b   -> 不提问也不搬
    cp -n -i -n a b -> 不搬（取**最后一次**出现的 -n，不是第一次）

argparse 默认不记录选项出现的先后，所以这里用一个自定义 Action 把顺序
攒进 namespace.option_order，再由 resolve_exclusive 判定谁赢。

判据取「最后一次出现」而不是「第一次」：重复给同一组选项时 GNU 以最后一个为准，
只看第一次出现会把 `-n -i -n` 判成 -i 赢。
"""

from __future__ import annotations

import argparse

__all__ = ["FlagTracker", "last_of", "resolve_exclusive"]


class FlagTracker(argparse.Action):
    """布尔选项的记录器：把出现的先后顺序记进 namespace.option_order。"""

    def __init__(self, option_strings, dest, **kwargs):
        kwargs["nargs"] = 0
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        order = getattr(namespace, "option_order", None)
        if order is None:
            order = []
            setattr(namespace, "option_order", order)
        order.append(self.dest)
        setattr(namespace, self.dest, True)


def last_of(order: list[str], names) -> str | None:
    """order 里 names 中**最后一次**出现的那个；一个都没出现返回 None。"""
    winner = None
    for name in order:
        if name in names:
            winner = name
    return winner


def resolve_exclusive(order: list[str], flags: dict[str, bool]) -> dict[str, bool]:
    """互斥选项的裁决：后给的那个赢，其余的被清掉。

    flags 是 {选项名: 是否给出}，返回同样形状的字典，只有赢的那个为真。
    都没给出时原样返回。
    """
    result = dict(flags)
    winner = last_of(order, tuple(flags))
    if winner is None:
        return result
    for name in flags:
        result[name] = name == winner
    return result
