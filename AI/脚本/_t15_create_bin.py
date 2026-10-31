"""生成 bin/ 目录下的 dmlinux 全局启动器。

产出：
  bin/dmlinux.cmd  —— Windows（cmd.exe / PowerShell）用，CRLF + 纯 ASCII
  bin/dmlinux      —— git-bash / Unix shell 用，LF + UTF-8，无扩展名

两个文件都从「脚本自身所在目录」反推项目根目录，不写死绝对路径，
因此 bin/ 整个目录可以随便挪位置、重新 clone，行为不变。

用法：python AI/脚本/_t15_create_bin.py
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "bin"

CMD_BODY = """\
@echo off
rem ------------------------------------------------------------------
rem  dmlinux - Windows launcher for the Windows-to-Linux project
rem  Usage: dmlinux <command> [args...]
rem
rem  The project root is derived from this script's own location
rem  (%~dp0..), so the whole bin folder can be moved anywhere.
rem
rem  Keep this file ASCII-only: cmd.exe reads batch files with the
rem  console OEM code page, so non-ASCII text here would be garbled.
rem ------------------------------------------------------------------
setlocal
set "DMLINUX_HOME=%~dp0.."
set "DMLINUX=1"

python -c "import sys" >nul 2>&1
if not errorlevel 1 goto run_python
py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 goto run_py

echo [dmlinux] No usable Python interpreter found. 1>&2
echo [dmlinux] Install Python 3.10+ and make sure "python" or "py" is on PATH. 1>&2
exit /b 2

:run_python
python "%DMLINUX_HOME%\\main.py" %*
exit /b %ERRORLEVEL%

:run_py
py -3 "%DMLINUX_HOME%\\main.py" %*
exit /b %ERRORLEVEL%
"""

SH_BODY = """\
#!/bin/sh
# ------------------------------------------------------------------
#  dmlinux - Unix shell launcher for the Windows-to-Linux project
#  Usage: dmlinux <command> [args...]
#
#  The project root is derived from this script's own location, so the
#  whole bin folder can be moved or re-cloned anywhere.
# ------------------------------------------------------------------

# Resolve this script through symlinks so $0 always points at a real file.
script="$0"
while [ -L "$script" ]; do
    link_dir=$(cd -P "$(dirname "$script")" >/dev/null 2>&1 && pwd)
    script=$(readlink "$script")
    case "$script" in
        /*) ;;
        *) script="$link_dir/$script" ;;
    esac
done

bin_dir=$(cd -P "$(dirname "$script")" >/dev/null 2>&1 && pwd)
project_dir=$(cd -P "$bin_dir/.." >/dev/null 2>&1 && pwd)
main_py="$project_dir/main.py"

# 告诉程序「当前是 dmlinux 调用」，帮助文案据此显示 dmlinux 而不是 python main.py
export DMLINUX=1

if [ ! -f "$main_py" ]; then
    echo "dmlinux: 找不到 $main_py，项目目录可能不完整" >&2
    exit 2
fi

# Prefer the interpreter that is already on PATH (honours venv/conda),
# then fall back to the Windows launcher and finally to python3.
if command -v python >/dev/null 2>&1 && python -c "import sys" >/dev/null 2>&1; then
    exec python "$main_py" "$@"
fi
if command -v python3 >/dev/null 2>&1 && python3 -c "import sys" >/dev/null 2>&1; then
    exec python3 "$main_py" "$@"
fi
if command -v py >/dev/null 2>&1; then
    exec py -3 "$main_py" "$@"
fi

echo "dmlinux: 找不到可用的 Python 解释器（需要 python / python3 / py 在 PATH 中）" >&2
exit 2
"""


def main() -> None:
    BIN.mkdir(parents=True, exist_ok=True)

    cmd_path = BIN / "dmlinux.cmd"
    cmd_path.write_bytes(CMD_BODY.replace("\n", "\r\n").encode("ascii"))
    print(f"wrote {cmd_path} ({cmd_path.stat().st_size}B, CRLF/ASCII)")

    sh_path = BIN / "dmlinux"
    sh_path.write_bytes(SH_BODY.encode("utf-8"))
    try:
        os.chmod(sh_path, 0o755)
    except OSError:
        pass  # NTFS 上权限位由 MSYS 模拟，失败不影响使用
    print(f"wrote {sh_path} ({sh_path.stat().st_size}B, LF/UTF-8)")

    for item in sorted(BIN.iterdir()):
        print(f"  - {item.name}")


if __name__ == "__main__":
    main()
