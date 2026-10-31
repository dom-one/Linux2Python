"""入口名称：让帮助文案跟着实际调用方式走。

同一个入口有两种走法：

- 直接跑项目：``python main.py grep ...``
- 通过全局启动器：``dmlinux grep ...``（bin/dmlinux.cmd 或 bin/dmlinux）

启动器会设置环境变量 ``DMLINUX=1``，据此决定帮助里显示哪个命令名，
这样 ``dmlinux grep --help`` 不会还打印 ``python main.py grep``。
"""

from __future__ import annotations

import os

ENV_FLAG = "DMLINUX"


def entry_name() -> str:
    """返回当前调用方式对应的入口名。"""
    return "dmlinux" if os.environ.get(ENV_FLAG) else "python main.py"


def command_prog(name: str) -> str:
    """返回某个指令在用法文案里的完整前缀，例如 ``dmlinux grep``。"""
    return f"{entry_name()} {name}"
