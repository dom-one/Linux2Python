"""指令模块集合。

把新指令写成同目录下的 .py 文件即可，load_all 会自动导入并完成注册。
"""

import importlib
import pkgutil


def load_all() -> None:
    for module in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{module.name}")
