"""指令运行上下文：把当前目录与标准流传给指令实现。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


@dataclass
class RunContext:
    cwd: Path
    stdout: TextIO
    stderr: TextIO
    stdin: TextIO
