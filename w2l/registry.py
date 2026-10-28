"""指令注册表。

新增指令只需在 w2l/commands/ 下放一个模块，用 @command 装饰处理函数，
commands 包在首次分发时自动导入全部子模块，因此无需改动 main.py。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Callable

from .context import RunContext


@dataclass(frozen=True)
class Command:
    name: str
    summary: str
    parser_factory: Callable[[], argparse.ArgumentParser]
    handler: Callable[[argparse.Namespace, RunContext], int]


REGISTRY: dict[str, Command] = {}

CommandHandler = Callable[[argparse.Namespace, RunContext], int]
ParserFactory = Callable[[], argparse.ArgumentParser]


def command(name: str, summary: str, parser_factory: ParserFactory):
    """把处理函数登记为可被 main.py 调用的指令。"""

    def decorator(func: CommandHandler) -> CommandHandler:
        if name in REGISTRY:
            raise RuntimeError(f"指令重复注册: {name}")
        REGISTRY[name] = Command(name, summary, parser_factory, func)
        return func

    return decorator


def load_commands() -> None:
    """导入 commands 包，触发所有指令模块完成注册。"""
    if REGISTRY:
        return
    from . import commands

    commands.load_all()
