"""探针：确认 argparse 里两件事的真实行为（本轮改 cp 要用）。

1. `--preserve` 必须只认 `--preserve=列表` 这种等号写法：
   GNU 的 --preserve 是「可选参数」形态，getopt 要求值必须用 `=` 附在后面；
   裸写 `--preserve` 等于 `--preserve=all`，**不吃后面的操作数**。
   而 `--no-preserve` 是「必需参数」形态，`--no-preserve mode` 会把 mode 吃掉。

2. 布尔选项要记录出现顺序（GNU 的 -i/-n 是后给的那个赢），
   `_FlagTracker` 这种自定义 Action 在 `-ni` / `-in` 合并写法上
   能不能保住「组内左到右」的顺序。

另外要验证：nargs=0 的自定义 Action 能不能吃下 `--preserve=mode` 的行内值。

用法:
    python AI/脚本/_t1302_probe_argparse_cp.py
"""

from __future__ import annotations

import argparse
import sys


class _FlagTracker(argparse.Action):
    """布尔选项的记录器：把出现的先后顺序记进 namespace。"""

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


class _InlineValue(argparse.Action):
    """只认 `--opt=value` 形态的选项。

    nargs=0 让 argparse 不去吃后面的操作数；值从 option_string 的 `=` 后面取。
    裸写 `--opt` 时取不到值，由调用方按「全量」处理。
    """

    def __init__(self, option_strings, dest, **kwargs):
        kwargs["nargs"] = 0
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        text = option_string or ""
        inline = ""
        if "=" in text:
            inline = text.split("=", 1)[1]
        setattr(namespace, self.dest, inline if inline else "all")
        order = getattr(namespace, "option_order", None)
        if order is None:
            order = []
            setattr(namespace, "option_order", order)
        order.append(self.dest)


def build_tracker() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="probe")
    parser.add_argument("-i", "--interactive", action=_FlagTracker, dest="interactive", default=False)
    parser.add_argument("-n", "--no-clobber", action=_FlagTracker, dest="no_clobber", default=False)
    parser.add_argument("operands", nargs="*", metavar="SOURCE... DEST")
    return parser


def build_inline() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="probe")
    parser.add_argument("--preserve", action=_InlineValue, dest="preserve", default=None)
    parser.add_argument("--no-preserve", action="append", dest="no_preserve", default=None)
    parser.add_argument("operands", nargs="*", metavar="SOURCE... DEST")
    return parser


def show(label: str, parser: argparse.ArgumentParser, argv: list[str]) -> None:
    try:
        ns = parser.parse_args(argv)
    except SystemExit as exc:
        print(f"{label}: argv={argv} -> SystemExit({exc.code})")
        return
    order = getattr(ns, "option_order", None)
    order_text = f" order={order}" if order is not None else ""
    print(f"{label}: argv={argv} -> {vars(ns)}{order_text}")


def main() -> int:
    print("=== 1. --preserve 只认等号写法 ===")
    inline = build_inline()
    show("裸写 + 两个操作数", inline, ["--preserve", "a.txt", "copy.txt"])
    show("等号形式", inline, ["--preserve=mode", "a.txt", "copy.txt"])
    show("等号 + 多模式", inline, ["--preserve=mode,timestamps", "a.txt", "copy.txt"])
    show("裸写 + 像模式的操作数", inline, ["--preserve", "mode", "a.txt", "copy.txt"])
    show("裸写在最后", inline, ["a.txt", "copy.txt", "--preserve"])
    show("no-preserve 裸写", inline, ["--no-preserve", "a.txt", "copy.txt"])
    show("no-preserve 等号", inline, ["--no-preserve=mode", "a.txt", "copy.txt"])
    show("no-preserve 空格写法", inline, ["--no-preserve", "mode", "a.txt", "copy.txt"])
    show("no-preserve 重复", inline, ["--no-preserve=mode", "--no-preserve=links", "a.txt", "copy.txt"])

    print()
    print("=== 2. 布尔选项的顺序记录 ===")
    t = build_tracker()
    show("n 后 i", t, ["-n", "-i", "a.txt", "b.txt"])
    show("i 后 n", t, ["-i", "-n", "a.txt", "b.txt"])
    show("合并 -ni", t, ["-ni", "a.txt", "b.txt"])
    show("合并 -in", t, ["-in", "a.txt", "b.txt"])
    show("只有 -n", t, ["-n", "a.txt", "b.txt"])
    show("只有 -i", t, ["-i", "a.txt", "b.txt"])
    show("长选项 --no-clobber 后 --interactive", t, ["--no-clobber", "--interactive", "a.txt", "b.txt"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
