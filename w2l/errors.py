"""指令执行过程中使用的两类异常。"""


class UsageError(Exception):
    """用法错误，退出码 2。"""


class CommandError(Exception):
    """指令执行失败，退出码 1。"""
