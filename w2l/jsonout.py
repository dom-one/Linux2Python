"""结构化输出：机器可读的 JSON 结果（`--json`）。

所有支持 `--json` 的指令共用这一份口径，规则只有四条：

- **只往 stdout 写 JSON**：报错照旧走 stderr，所以 stdout 永远是合法 JSON，
  重定向到文件后可以直接喂给 `json.loads` 或 `jq`，不会被一行报错毁掉。
- **不转义非 ASCII**（`ensure_ascii=False`）：中文直接可读，输出按 UTF-8 写。
- **缩进 2 空格、键序按构造顺序**（`sort_keys=False`）：一行一个字段，
  人眼能扫、diff 也能看。
- **类型名用英文小写单词**（`file` / `directory` / `symlink` ...）：
  这些值是给脚本分支判断用的，不要用会随语言环境变的词。

为什么要有这个模块：结构化输出是**跨指令**的口径（输出长什么样、错误走哪、
中文怎么转义），散在各指令里各写一遍必然漂。收在一处，改口径只改这一处。
"""

from __future__ import annotations

import json
import stat
from typing import Any

from .context import RunContext

__all__ = ["dumps", "write", "type_name"]

#: 缩进宽度。2 空格是 JSON 的常规写法，也便于人眼扫。
INDENT = 2


def dumps(payload: Any) -> str:
    """把对象序列化成 JSON 文本，末尾带一个换行。"""
    text = json.dumps(
        payload,
        ensure_ascii=False,
        indent=INDENT,
        sort_keys=False,
        allow_nan=False,
    )
    return text + "\n"


def write(ctx: RunContext, payload: Any) -> None:
    """把 JSON 文本写到标准输出。"""
    ctx.stdout.write(dumps(payload))


def type_name(mode: int) -> str:
    """st_mode 对应的类型名，给 JSON 的 `type` 字段用。

    Windows 上 Python 能拿到的类型只有目录、文件、符号链接三种，
    其余分支在别的平台上才有意义，留着是为了口径统一。
    """
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISBLK(mode):
        return "block"
    if stat.S_ISCHR(mode):
        return "character"
    return "other"
