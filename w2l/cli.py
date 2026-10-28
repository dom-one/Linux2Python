"""命令行分发：解析指令名，交给注册表中的处理器。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .context import RunContext
from .errors import CommandError, UsageError
from .registry import REGISTRY, load_commands


def _print_help() -> None:
    print("用法: python main.py <指令> [参数]")
    print()
    print("可用指令:")
    width = max((len(name) for name in REGISTRY), default=4)
    for name in sorted(REGISTRY):
        print(f"  {name.ljust(width)}  {REGISTRY[name].summary}")
    print()
    print("查看具体用法: python main.py <指令> --help")


def _configure_streams() -> None:
    """统一以 UTF-8 读写，避免 Windows 下管道输出中文乱码。"""
    if os.name == "nt":
        _set_console_utf8()
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
    reconfigure = getattr(sys.stdin, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def _set_console_utf8() -> None:
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except (AttributeError, OSError):
        pass


def _silence_broken_pipe() -> None:
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, sys.stdout.fileno())


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    _configure_streams()
    load_commands()

    if not argv:
        _print_help()
        return 1
    if argv[0] in ("-h", "--help", "help"):
        _print_help()
        return 0

    name = argv[0]
    entry = REGISTRY.get(name)
    if entry is None:
        print(f"未知指令: {name}", file=sys.stderr)
        print(f"可用指令: {', '.join(sorted(REGISTRY))}", file=sys.stderr)
        return 2

    parser = entry.parser_factory()
    namespace = parser.parse_args(argv[1:])
    ctx = RunContext(cwd=Path.cwd(), stdout=sys.stdout, stderr=sys.stderr, stdin=sys.stdin)

    try:
        return entry.handler(namespace, ctx) or 0
    except UsageError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    except CommandError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        _silence_broken_pipe()
        return 0
    except KeyboardInterrupt:
        return 130
