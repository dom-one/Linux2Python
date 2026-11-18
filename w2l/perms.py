"""权限口径：把 Windows 合成出来的 st_mode 折算成 POSIX 常见口径。

Windows 没有 POSIX 权限位，Python 的 os.stat 只能合成出 0666/0777/0444
这种「位全开」的值；MSYS 的 stat 报出来的是另一套固定口径（实测 Git Bash
的 stat 就是这套值）：

- 可写文件 0644
- 只读文件 0444
- 目录 0755（哪怕目录被设成只读，MSYS 仍报 0755）
- 可执行文件 0755（.exe / .com / .bat / .cmd，Python 用 S_IEXEC 标识）
- 符号链接 0777

本项目统一按 MSYS 的口径折算，ls -l / tree -p 的权限列与 chmod 的报数
才自洽，跟 GNU 的输出也才对得上。
"""

from __future__ import annotations

import stat

DIR_MODE = 0o755
EXEC_MODE = 0o755
LINK_MODE = 0o777
FILE_MODE = 0o644
READONLY_FILE_MODE = 0o444

# GNU 的 chmod 打不开某个文件时，报的「原模式」就是这个默认值（实测 0644）。
MISSING_MODE = 0o644

# 每个权限类对应的位掩码，以及它带的特殊位（setuid / setgid / sticky）。
_CLASS_BITS = {"u": 0o600, "g": 0o060, "o": 0o006}
_CLASS_SPECIAL = {"u": 0o4000, "g": 0o2000, "o": 0o1000}


def canonical_mode(mode: int) -> int:
    """把 Windows 合成的 st_mode 折算成 MSYS 口径的权限位。"""
    if stat.S_ISLNK(mode):
        return LINK_MODE
    if stat.S_ISDIR(mode):
        return DIR_MODE
    if stat.S_ISREG(mode):
        if mode & stat.S_IEXEC:
            return EXEC_MODE
        if mode & stat.S_IWRITE:
            return FILE_MODE
        return READONLY_FILE_MODE
    return FILE_MODE


def perm_bits(mode: int) -> str:
    """把权限位渲染成 rwx rwx rwx，特殊位用 s / S / t / T 表示。"""
    out = []
    for name in ("u", "g", "o"):
        shift = {"u": 6, "g": 3, "o": 0}[name]
        bits = (mode >> shift) & 0o7
        special = bool(mode & _CLASS_SPECIAL[name])
        out.append("r" if bits & 0o4 else "-")
        out.append("w" if bits & 0o2 else "-")
        if bits & 0o1:
            if not special:
                out.append("x")
            elif name == "o":
                out.append("t")
            else:
                out.append("s")
        else:
            out.append("T" if (special and name == "o") else ("S" if special else "-"))
    return "".join(out)


def type_char(mode: int) -> str:
    """权限列的类型字符。"""
    if stat.S_ISLNK(mode):
        return "l"
    if stat.S_ISDIR(mode):
        return "d"
    if stat.S_ISFIFO(mode):
        return "p"
    if stat.S_ISSOCK(mode):
        return "s"
    return "-"


def format_perms(mode: int) -> str:
    """权限列：类型字符 + rwx rwx rwx（按 MSYS 口径）。"""
    return type_char(mode) + perm_bits(canonical_mode(mode))


def mode_octal(mode: int) -> str:
    """权限位的四位八进制写法（GNU 的 %04o）。"""
    return f"{mode & 0o7777:04o}"
